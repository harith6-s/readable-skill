"""Record what a unit does at its boundary, with everything outside it stubbed, and compare two recordings.

    python parity.py record --unit PATH[=MODULE] [--unit ...] --root ROOT --scenarios scenarios.py --out run.json
                            [--allow MODULE ...] [--now 2026-01-01T09:00:00] [--keep-tracebacks]
    python parity.py diff OLD.json NEW.json
    python parity.py coverage --recording run.json --map map.json        (map.json: jump_depth.py ... --json)

record
  Run one side per command, so each side gets its own process. The unit is a file, or a folder loaded as a package,
  imported as MODULE (default: its dotted path under ROOT). Load a V2 or a copy under the original's MODULE so its
  relative imports resolve the same way. Every other import becomes a recording stub unless it is the standard library
  or an --allow module (pure computation only): other project files, Django and its ORM, HTTP sessions, storage,
  Celery, settings. The network and database parts of the standard library are stubbed as well (socket, ssl,
  http.client, urllib.request, smtplib, sqlite3, subprocess ...), so nothing reaches a real service or database.
  datetime.now()/today(), time.time(), uuid4() and random are frozen. Each scenario imports a fresh copy of the unit.

scenarios.py
  Every function named scenario_* is one scenario, run in file order. It gets a harness `h`, sets the stubs up,
  calls one entry point and returns its result. An exception it lets out is recorded as the outcome.

      def scenario_send_invoice_success(h):
          h.stub("billing.client.ApiSession().post").returns(h.response(json={"ok": True, "data": {}}))
          invoice = h.obj("invoice", id=7, number="INV-7")
          return h.unit.send_invoice(h.obj("user", username="u1"), h.obj("customer"), invoice)

  h.unit               the unit's names wherever they live: every --unit module is searched in order, and the one
                       that defines a name wins over one that only imports it. So one scenarios.py drives the original
                       and a rewrite split into task files (give each file as its own --unit). h.modules["dotted.name"]
                       is one module. Imported on first use
  h.stub(path)         configure what a stub does. A path is the import path, then attribute and call steps:
                       "requests.post", "billing.client.ApiSession().post", "billing.models.Invoice.objects.get",
                       "obj:contract.save". fnmatch wildcards work ("*.objects.filter().first").
                         .returns(v1, v2, ...)   successive calls get successive values; the last one repeats
                         .raises(error)          an exception instance, e.g. h.timeout() or ValueError("bad")
                         .answers(fn)            fn(*args, **kwargs) decides
                         .iterates([...])        what `for x in stub` yields (default: nothing)
                         .pure()                 its calls are not recorded: pure computation such as formatting
                                                 a date, where calling it once more or less is not behavior. It
                                                 still returns what is set above (default: a stub)
  h.const(path, value) what an imported name or attribute *is*, e.g. a settings dict; set it before h.unit is used
  h.obj(label, **attrs) a stand-in object; attribute writes and calls on it are recorded ("obj:label.attr").
                       Any attribute it was not given is a stub, so hasattr() is always true.
  h.row(label, **attrs) the same, but strict like a real model row: an attribute it was not given raises
                       AttributeError (only .save() .delete() .refresh_from_db() are always there, recorded)
  h.response(status=200, json=None, content=b"", text=None, headers=None)
  h.timeout()          an exception named Timeout; h.error(path, *args) an instance of the stubbed class at path
  h.now                the frozen time (naive datetime)

  How stubs behave:
  - A stubbed name in CapWords is a class: it can be raised and caught (`except CustomException`), subclassed, and
    calling it returns an instance whose attributes are the keyword arguments given. A module-level name in
    ALL_CAPS takes its literal value from the project's source when it has one (read with ast; the module never
    runs), so turning a literal into a named constant changes nothing. Otherwise, such as a value from settings or
    the environment, it is text ("<billing.client.BASE_URL>") that can also be called. Real values end up in the
    recording, so keep recordings out of public places. Anything else is a callable stub.
  - An unconfigured call returns another stub, so chains such as Model.objects.filter(...).first() work.
    A stub never raises unless told: give a helper that always raises (a fail() helper) .raises(...).
  - A scenario that breaks outside the unit (a typo, a wrong harness call) stops the recording. Only an error the
    unit's own code was running is recorded as an outcome. A scenario with no outbound call prints a warning.
  - A stub called with one function only (a decorator such as @shared_task) returns that function wrapped, so it
    still runs; .delay(...) and .apply_async(...) on it are recorded. transaction.on_commit(fn) runs fn at once.
    django.utils.timezone.now() returns the frozen time in UTC.

recording (JSON)
  per scenario: outcome {"return": value} or {"raise": type, "message": text}, and the events in order:
  {"call": path, "args": [...], "kwargs": {...}, "site": "file:line"}, {"set": "obj:name.attr", "value": ...},
  {"enter": path} and {"exit": path, "error": type or null} around `with` blocks. Dicts keep their key order.
  Tracebacks inside strings are cut to their last line, because file paths and line numbers always change
  (--keep-tracebacks keeps them).

diff      compares outcomes and events in order, ignoring sites. Exit 1 when anything differs.
coverage  lists the outbound call sites of the map that no scenario reached. Exit 1 when any is left.
"""

import argparse
import ast
import copy
import datetime as _datetime
import fnmatch
import hashlib
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import random
import re
import sys
import time
import types
import uuid
from decimal import Decimal
from pathlib import Path

STUBBED_STDLIB = ("socket", "ssl", "http.client", "http.server", "urllib.request", "smtplib", "ftplib", "imaplib",
                  "poplib", "xmlrpc", "sqlite3", "subprocess", "multiprocessing")
TRACEBACK = re.compile(r"Traceback \(most recent call last\):\n(?:[ \t].*(?:\n|$))*")
ADDRESS = re.compile(r" at 0x[0-9a-fA-F]+")
TIME_TYPES = (_datetime.date, _datetime.time, _datetime.timedelta)    # the real classes, kept before freeze()
dumps = json.dumps
NO_VALUE = object()
TREES = {}


def is_constant_name(name):
    return name.isupper() and (len(name) >= 4 or "_" in name)


def source_constant(root, path):
    """The literal value of a module-level constant in a project file ("pkg.module.NAME"), or NO_VALUE."""
    module, _, name = path.rpartition(".")
    base = root.joinpath(*module.split("."))
    file = next((candidate for candidate in (base.with_suffix(".py"), base / "__init__.py") if candidate.is_file()),
                None)
    if file is None:
        return NO_VALUE
    if file not in TREES:
        try:
            TREES[file] = ast.parse(file.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, ValueError):
            TREES[file] = ast.Module(body=[], type_ignores=[])
    value = NO_VALUE
    for node in TREES[file].body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(target, ast.Name) and target.id == name for target in targets) and node.value is not None:
            try:
                value = ast.literal_eval(node.value)                 # the last assignment wins, as at import
            except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                value = NO_VALUE
    return value


def dunder(name):
    return name.startswith("__") and name.endswith("__")


# ---- the recorder: every stub reports here ----

class Recorder:
    def __init__(self, unit_files, root, keep_tracebacks):
        self.unit_files = unit_files
        self.root = root
        self.keep_tracebacks = keep_tracebacks
        self.reset()

    def reset(self):
        self.events = []
        self.active = False
        self.rules = {}
        self.consts = {}
        self.objects = {}

    def record(self, event):
        if self.active:
            self.events.append(event)

    def site(self):
        frame = sys._getframe(2)
        while frame is not None:
            name = frame.f_code.co_filename
            if name in self.unit_files:
                path = Path(name)
                try:
                    shown = path.relative_to(self.root)
                except ValueError:
                    shown = path
                return f"{shown}:{frame.f_lineno}"
            frame = frame.f_back
        return None

    def rule(self, path):
        if path in self.rules:
            return self.rules[path]
        for pattern, behaviour in self.rules.items():
            if any(mark in pattern for mark in "*?[") and fnmatch.fnmatchcase(path, pattern):
                return behaviour
        return None

    def attr(self, path):
        """The object at an import path or attribute path: a configured constant, or a stub shaped by its name."""
        if path in self.consts:
            return self.consts[path]
        if path not in self.objects:
            name = path.rsplit(".", 1)[-1].rstrip("()")
            if is_constant_name(name):
                plain = not any(mark in path for mark in "()[:")
                value = source_constant(self.root, path) if plain else NO_VALUE
                self.objects[path] = StubText(path, self) if value is NO_VALUE else value
            elif name[:1].isupper():
                self.objects[path] = stub_class(path, self)
            else:
                self.objects[path] = Stub(path, self)
        return self.objects[path]

    def call(self, path, args, kwargs, make=None):
        behaviour = self.rule(path)
        if behaviour is None or not behaviour.quiet:
            self.record({"call": path, "args": self.value(list(args)), "kwargs": self.value(kwargs),
                         "site": self.site()})
        if behaviour is not None and (behaviour.configured or not behaviour.quiet):
            return behaviour.run(args, kwargs)
        if path.endswith(".on_commit") and args and callable(args[0]):
            args[0]()
            return None
        if path == "django.utils.timezone.now":
            return FROZEN["now"].replace(tzinfo=_datetime.timezone.utc)
        if make is not None:
            return make()
        if len(args) == 1 and not kwargs and isinstance(args[0], (types.FunctionType, type)):
            return args[0] if isinstance(args[0], type) else Decorated(args[0], self)
        return self.attr(f"{path}()")

    def iteration(self, path):
        behaviour = self.rule(path)
        return list(behaviour.items) if behaviour is not None and behaviour.items is not None else []

    def value(self, value, depth=0):
        """A JSON-ready copy of a value, keeping dict key order."""
        if depth > 8:
            return "<deep>"
        if isinstance(value, StubText):
            return {"__stub__": value.path}
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            value = ADDRESS.sub("", value)
            return value if self.keep_tracebacks else TRACEBACK.sub("Traceback (most recent call last): ...\n", value)
        if isinstance(value, Stub):
            return {"__stub__": object.__getattribute__(value, "_path")}
        if isinstance(value, StubMeta):
            return {"__stub__": value._path}
        if isinstance(value, StubBase) and "_path" in type(value).__dict__:
            return {"__stub__": type(value)._path + "()", "kwargs": self.value(value.__dict__, depth + 1)}
        if isinstance(value, Obj):
            return {"__obj__": object.__getattribute__(value, "_name")}
        if isinstance(value, dict):
            return {key if isinstance(key, str) else repr(key): self.value(item, depth + 1)
                    for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.value(item, depth + 1) for item in value]
        if isinstance(value, (set, frozenset)):
            return sorted((self.value(item, depth + 1) for item in value), key=repr)
        if isinstance(value, (bytes, bytearray)):
            return {"__bytes__": len(value), "sha256": hashlib.sha256(value).hexdigest()[:16]}
        if isinstance(value, Decimal):
            return {"__decimal__": str(value)}
        if isinstance(value, TIME_TYPES):
            return {"__time__": str(value)}
        if isinstance(value, uuid.UUID):
            return {"__uuid__": str(value)}
        if isinstance(value, Response):
            return {"__response__": value.status_code}
        if isinstance(value, BaseException):
            return {"__error__": type(value).__name__, "message": self.value(str(value))}
        if isinstance(value, Path):
            return str(value)
        if callable(value):
            return "<callable>"
        attrs = getattr(value, "__dict__", None)
        if isinstance(attrs, dict):
            return {"__object__": type(value).__name__, "attrs": self.value(attrs, depth + 1)}
        return {"__object__": type(value).__name__, "repr": ADDRESS.sub("", repr(value))}


class Behaviour:
    def __init__(self):
        self.values, self.error, self.function, self.items = None, None, None, None
        self.configured, self.quiet = False, False

    def returns(self, *values):
        self.values, self.configured = list(values), True
        return self

    def raises(self, error):
        self.error, self.configured = error, True
        return self

    def answers(self, function):
        self.function, self.configured = function, True
        return self

    def iterates(self, items):
        self.items, self.configured = list(items), True
        return self

    def pure(self):
        self.quiet = True
        return self

    def run(self, args, kwargs):
        if self.error is not None:
            raise self.error
        if self.function is not None:
            return self.function(*args, **kwargs)
        if self.values:
            return self.values.pop(0) if len(self.values) > 1 else self.values[0]
        return None


# ---- the stubs ----

class Stub:
    __slots__ = ("_path", "_rec")

    def __init__(self, path, rec):
        object.__setattr__(self, "_path", path)
        object.__setattr__(self, "_rec", rec)

    def __getattr__(self, name):
        if dunder(name):
            raise AttributeError(name)
        return self._rec.attr(f"{self._path}.{name}")

    def __setattr__(self, name, value):
        self._rec.record({"set": f"{self._path}.{name}", "value": self._rec.value(value)})

    def __call__(self, *args, **kwargs):
        return self._rec.call(self._path, args, kwargs)

    def __getitem__(self, key):
        return self._rec.attr(f"{self._path}[{key!r}]")

    def __iter__(self):
        return iter(self._rec.iteration(self._path))

    def __len__(self):
        return len(self._rec.iteration(self._path))

    def __bool__(self):
        return True

    def __enter__(self):
        self._rec.record({"enter": self._path})
        return self

    def __exit__(self, kind, error, trace):
        self._rec.record({"exit": self._path, "error": kind.__name__ if kind else None})
        return False

    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return id(self)

    def __repr__(self):
        return f"<stub {self._path}>"

    __str__ = __repr__

    def __format__(self, spec):
        return repr(self)


class StubText(str):
    """An ALL_CAPS import (a URL, a key): text a payload can carry, and still a stub when called."""

    def __new__(cls, path, rec):
        text = super().__new__(cls, f"<{path}>")
        text.path, text.rec = path, rec
        return text

    def __getattr__(self, name):
        if dunder(name):
            raise AttributeError(name)
        return self.rec.attr(f"{self.path}.{name}")

    def __call__(self, *args, **kwargs):
        return self.rec.call(self.path, args, kwargs)


class StubMeta(type):
    def __getattr__(cls, name):
        if dunder(name) or name in ("_path", "_rec"):
            raise AttributeError(name)
        return cls._rec.attr(f"{cls._path}.{name}")

    def __call__(cls, *args, **kwargs):
        if "_path" not in cls.__dict__:                      # a class of the unit that subclasses a stub
            return super().__call__(*args, **kwargs)
        return cls._rec.call(cls._path, args, kwargs, make=lambda: make_instance(cls, args, kwargs))

    def __repr__(cls):
        return f"<stub {cls.__dict__.get('_path', cls.__name__)}>"


class StubBase(Exception, metaclass=StubMeta):
    def __getattr__(self, name):
        if dunder(name) or name in ("_path", "_rec"):
            raise AttributeError(name)
        return type(self)._rec.attr(f"{type(self)._path}().{name}")

    def _combine(self, op, other):
        return make_instance(type(self), (), {"op": op, "left": self, "right": other})

    def __or__(self, other):                                 # Q(a=1) | Q(b=2)
        return self._combine("|", other)

    def __and__(self, other):
        return self._combine("&", other)

    def __invert__(self):
        return self._combine("~", None)

    def __setattr__(self, name, value):
        if "_path" in type(self).__dict__:
            type(self)._rec.record({"set": f"{type(self)._path}().{name}", "value": type(self)._rec.value(value)})
        object.__setattr__(self, name, value)

    def __str__(self):
        shown = [repr(arg) for arg in self.args] + [f"{key}={item!r}" for key, item in self.__dict__.items()]
        return f"{type(self).__name__}({', '.join(shown)})"

    def __bool__(self):
        return True


def stub_class(path, rec):
    return StubMeta(path.rsplit(".", 1)[-1], (StubBase,), {"_path": path, "_rec": rec,
                                                           "__module__": path.rsplit(".", 1)[0]})


def make_instance(cls, args, kwargs):
    instance = Exception.__new__(cls, *args)
    Exception.__init__(instance, *args)
    for key, item in kwargs.items():
        object.__setattr__(instance, key, item)
    return instance


class Decorated:
    """A function wrapped by a stubbed decorator (@shared_task, @receiver): calling it runs the function."""

    def __init__(self, function, rec):
        self._function, self._rec = function, rec

    def __call__(self, *args, **kwargs):
        return self._function(*args, **kwargs)

    def __get__(self, instance, owner=None):
        return self if instance is None else types.MethodType(self._function, instance)

    def __getattr__(self, name):
        if dunder(name):
            return getattr(self._function, name)
        return self._rec.attr(f"task:{self._function.__name__}.{name}")


class Obj:
    """A stand-in object made by a scenario. Reads come from its attributes, anything else is a recorded stub.
    A strict one (h.row) has only the attributes it was given, plus recorded .save()/.delete()/.refresh_from_db()."""
    __slots__ = ("_name", "_rec", "_attrs", "_strict")

    def __init__(self, rec, name, attrs, strict=False):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_rec", rec)
        object.__setattr__(self, "_attrs", dict(attrs))
        object.__setattr__(self, "_strict", strict)

    def __getattr__(self, attr):
        if dunder(attr):
            raise AttributeError(attr)
        attrs = object.__getattribute__(self, "_attrs")
        if attr in attrs:
            return attrs[attr]
        if self._strict and attr not in ("save", "delete", "refresh_from_db"):
            raise AttributeError(f"{self._name} has no attribute {attr!r}")
        return self._rec.attr(f"obj:{self._name}.{attr}")

    def __setattr__(self, attr, value):
        self._rec.record({"set": f"obj:{self._name}.{attr}", "value": self._rec.value(value)})
        object.__getattribute__(self, "_attrs")[attr] = value

    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return id(self)

    def __bool__(self):
        return True

    def __repr__(self):
        return f"<obj {self._name}>"

    __str__ = __repr__


class Response:
    def __init__(self, status=200, json=None, content=b"", text=None, headers=None):
        self.status_code = status
        self.ok = 200 <= status < 400
        self._json = json
        self.content = content
        self.text = text if text is not None else ("" if json is None else dumps(json))
        self.headers = headers or {"Content-Type": "application/json" if json is not None else "application/pdf"}

    def json(self):
        if self._json is None:
            raise ValueError("no JSON body")
        return copy.deepcopy(self._json)

    def raise_for_status(self):
        if not self.ok:
            raise type("HTTPError", (Exception,), {})(f"{self.status_code} Error")


# ---- loading the unit with everything else stubbed ----

class StubModule(types.ModuleType):
    def __getattr__(self, name):
        if dunder(name):
            raise AttributeError(name)
        return RECORDER.attr(f"{self.__name__}.{name}")


class StubLoader(importlib.abc.Loader):
    def create_module(self, spec):
        return StubModule(spec.name)

    def exec_module(self, module):
        module.__path__ = []


class Finder(importlib.abc.MetaPathFinder):
    def __init__(self, units, allow, root):
        self.units = units            # module name -> Path (file, or folder for a package)
        self.allow = allow
        self.root = root

    def unit_path(self, fullname):
        for module, path in self.units.items():
            if fullname == module:
                return path
            if fullname.startswith(module + ".") and path.is_dir():
                inner = path.joinpath(*fullname[len(module) + 1:].split("."))
                for candidate in (inner.with_suffix(".py"), inner / "__init__.py", inner):
                    if candidate.exists():
                        return candidate
        return None

    def real(self, fullname):
        if any(fullname == name or fullname.startswith(name + ".") for name in STUBBED_STDLIB):
            return False
        if fullname.split(".")[0] in sys.stdlib_module_names:
            return True
        return any(fullname == name or fullname.startswith(name + ".") for name in self.allow)

    def find_spec(self, fullname, path=None, target=None):
        found = self.unit_path(fullname)
        if found is not None:
            if found.is_dir():
                init = found / "__init__.py"
                if init.exists():
                    return importlib.util.spec_from_file_location(fullname, init,
                                                                  submodule_search_locations=[str(found)])
                spec = importlib.machinery.ModuleSpec(fullname, None, is_package=True)
                spec.submodule_search_locations = [str(found)]
                return spec
            return importlib.util.spec_from_file_location(fullname, found)
        if self.real(fullname):
            if fullname.split(".")[0] in sys.stdlib_module_names:
                return None
            # an allowed project module can sit under a stubbed package, whose empty __path__ finds nothing
            inner = self.root.joinpath(*fullname.split("."))
            for candidate, package in ((inner.with_suffix(".py"), False), (inner / "__init__.py", True)):
                if candidate.exists():
                    return importlib.util.spec_from_file_location(
                        fullname, candidate, submodule_search_locations=[str(inner)] if package else None)
            return None
        return importlib.util.spec_from_loader(fullname, StubLoader(), is_package=True)


# ---- frozen clock and randomness ----

FROZEN = {"now": _datetime.datetime(2026, 1, 1, 9, 0, 0), "uuid": 0}


class FrozenDatetime(_datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        moment = FROZEN["now"]
        return cls.fromisoformat(moment.isoformat()) if tz is None else cls.fromisoformat(
            moment.replace(tzinfo=tz).isoformat())

    @classmethod
    def utcnow(cls):
        return cls.fromisoformat(FROZEN["now"].isoformat())

    @classmethod
    def today(cls):
        return cls.now()


class FrozenDate(_datetime.date):
    @classmethod
    def today(cls):
        return cls.fromisoformat(FROZEN["now"].date().isoformat())


def frozen_uuid4():
    FROZEN["uuid"] += 1
    return uuid.UUID(int=FROZEN["uuid"])


def freeze():
    _datetime.datetime = FrozenDatetime
    _datetime.date = FrozenDate
    time.time = lambda: FROZEN["now"].timestamp()
    uuid.uuid4 = frozen_uuid4


# ---- running scenarios ----

class UnitView:
    """h.unit: one name, looked up in every unit module; the module that defines it wins over one that imports it."""

    def __init__(self, modules):
        self._modules = modules

    def __getattr__(self, name):
        if dunder(name):
            return getattr(self._modules[0], name)
        holders = [module for module in self._modules if name in vars(module)]
        if not holders:
            raise AttributeError(f"no unit module has {name!r}")
        own = [module for module in holders
               if getattr(vars(module)[name], "__module__", None) == module.__name__]
        return getattr((own or holders)[0], name)


class Harness:
    def __init__(self, rec, units):
        self._rec = rec
        self._units = list(units)
        self._loaded = {}
        self.now = FROZEN["now"]

    @property
    def unit(self):
        return UnitView(list(self.modules.values()))

    @property
    def modules(self):
        if not self._loaded:
            was, self._rec.active = self._rec.active, False      # import-time calls are not part of the run
            try:
                self._loaded = {name: importlib.import_module(name) for name in self._units}
            except Exception as error:                           # a harness problem, not an outcome
                raise SystemExit(f"cannot import the unit: {error!r}")
            finally:
                self._rec.active = was
        return self._loaded

    def stub(self, path):
        return self._rec.rules.setdefault(path, Behaviour())

    def const(self, path, value):
        self._rec.consts[path] = value

    def obj(self, label, /, **attrs):
        return Obj(self._rec, label, attrs)

    def row(self, label, /, **attrs):
        return Obj(self._rec, label, attrs, strict=True)

    def response(self, status=200, json=None, content=b"", text=None, headers=None):
        return Response(status, json, content, text, headers)

    def timeout(self, message="timed out"):
        return type("Timeout", (Exception,), {})(message)

    def error(self, path, *args, **kwargs):
        cls = self._rec.attr(path)
        return make_instance(cls, args, kwargs) if isinstance(cls, StubMeta) else Exception(*args)


def load_scenarios(path):
    spec = importlib.util.spec_from_file_location("parity_scenarios", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return [(name, value) for name, value in vars(module).items()
            if name.startswith("scenario_") and callable(value)]


def fresh(units):
    for name, module in list(sys.modules.items()):
        if isinstance(module, StubModule) or any(name == unit or name.startswith(unit + ".") for unit in units):
            del sys.modules[name]
    RECORDER.reset()
    FROZEN["uuid"] = 0
    random.seed(0)


def raised_in_unit(trace, unit_files):
    """True when the unit's code was on the stack: the error is the unit's outcome, not a broken scenario."""
    while trace is not None:
        if trace.tb_frame.f_code.co_filename in unit_files:
            return True
        trace = trace.tb_next
    return False


RECORDER = None


def record(args):
    global RECORDER
    root = Path(args.root).resolve()
    units = {}
    for entry in args.unit:
        raw, _, module = entry.partition("=")
        path = Path(raw).resolve()
        if not module:
            rel = path.relative_to(root)
            module = ".".join((rel.with_suffix("") if path.is_file() else rel).parts)
        units[module] = path
    unit_files = set()
    for path in units.values():
        unit_files.update(str(p) for p in (path.rglob("*.py") if path.is_dir() else [path]))
    RECORDER = Recorder(unit_files, root, args.keep_tracebacks)
    FROZEN["now"] = _datetime.datetime.fromisoformat(args.now)
    for name in list(sys.modules):
        if any(name == stubbed or name.startswith(stubbed + ".") for stubbed in STUBBED_STDLIB):
            del sys.modules[name]
    sys.path.insert(0, str(root))
    sys.meta_path.insert(0, Finder(units, args.allow, root))
    freeze()

    results = []
    for name, scenario in load_scenarios(args.scenarios):
        fresh(units)
        harness = Harness(RECORDER, units)
        RECORDER.active = True
        try:
            outcome = {"return": RECORDER.value(scenario(harness))}
        except Exception as error:                           # the outcome is what we compare
            if not raised_in_unit(error.__traceback__, unit_files):
                raise SystemExit(f"{name}: the scenario itself failed, outside the unit: {error!r}")
            outcome = {"raise": type(error).__name__, "message": RECORDER.value(str(error))}
        RECORDER.active = False
        results.append({"name": name, "doc": (scenario.__doc__ or "").strip(), "outcome": outcome,
                        "events": RECORDER.events})
        shown = outcome.get("raise") or "return"
        calls = sum(1 for event in RECORDER.events if "call" in event)
        print(f"  {name}: {shown}, {calls} outbound calls" + ("  <- WARNING: nothing went out" if not calls else ""))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"units": {module: str(path) for module, path in units.items()},
                               "now": args.now, "scenarios": results}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    calls = sum(1 for result in results for event in result["events"] if "call" in event)
    print(f"recorded {len(results)} scenarios, {calls} outbound calls -> {out}")


def short(value, limit=300):
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + " ..."


def first_difference(old, new, path="$"):
    """Where two recorded values first differ, e.g. `$.kwargs.json.document.farmer_data.address.soi: "-" -> ""`."""
    if isinstance(old, dict) and isinstance(new, dict):
        if list(old) != list(new):
            if set(old) == set(new):
                return f"{path}: key order {list(old)} -> {list(new)}"
            return f"{path}: keys only in old {sorted(set(old) - set(new))}, only in new {sorted(set(new) - set(old))}"
        for key in old:
            found = first_difference(old[key], new[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(old, list) and isinstance(new, list):
        if len(old) != len(new):
            return f"{path}: {len(old)} items -> {len(new)} items"
        for index, (a, b) in enumerate(zip(old, new)):
            found = first_difference(a, b, f"{path}[{index}]")
            if found:
                return found
        return None
    if dumps(old) != dumps(new):
        return f"{path}: {short(old, 120)} -> {short(new, 120)}"
    return None


def diff(args):
    old = json.loads(Path(args.old).read_text(encoding="utf-8"))["scenarios"]
    new = json.loads(Path(args.new).read_text(encoding="utf-8"))["scenarios"]
    old_by, new_by = {s["name"]: s for s in old}, {s["name"]: s for s in new}
    problems = 0
    for name in list(old_by) + [name for name in new_by if name not in old_by]:
        a, b = old_by.get(name), new_by.get(name)
        if a is None or b is None:
            print(f"{name}: only in {'new' if a is None else 'old'}")
            problems += 1
            continue
        if json.dumps(a["outcome"]) != json.dumps(b["outcome"]):
            print(f"{name}: outcome differs\n  {first_difference(a['outcome'], b['outcome'])}")
            problems += 1
        strip = lambda events: [{k: v for k, v in event.items() if k != "site"} for event in events]
        ea, eb = strip(a["events"]), strip(b["events"])
        differing = [i for i in range(max(len(ea), len(eb)))
                     if i >= len(ea) or i >= len(eb) or json.dumps(ea[i]) != json.dumps(eb[i])]
        if differing:
            problems += 1
            print(f"{name}: {len(differing)} of {max(len(ea), len(eb))} events differ "
                  f"(old has {len(ea)}, new has {len(eb)})")
            for i in differing[:3]:
                if i < len(ea) and i < len(eb):
                    print(f"  event {i} ({ea[i].get('call') or ea[i].get('set') or ea[i].get('enter') or 'exit'}): "
                          f"{first_difference(ea[i], eb[i])}")
                else:
                    print(f"  event {i}: old {short(ea[i]) if i < len(ea) else '-'} | "
                          f"new {short(eb[i]) if i < len(eb) else '-'}")
    print("diff: empty" if not problems else f"diff: {problems} scenario problem(s)")
    sys.exit(1 if problems else 0)


def coverage(args):
    recording = json.loads(Path(args.recording).read_text(encoding="utf-8"))
    reached = {event["site"] for scenario in recording["scenarios"] for event in scenario["events"]
               if event.get("site")}
    outbound = json.loads(Path(args.map).read_text(encoding="utf-8"))["outbound"]
    missing = [item for item in outbound if item["site"] not in reached]
    print(f"outbound sites: {len(outbound)}, reached: {len(outbound) - len(missing)}")
    for item in missing:
        print(f"  not reached: {item['site']}  {item['call']}")
    sys.exit(1 if missing else 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    rec = commands.add_parser("record")
    rec.add_argument("--unit", action="append", required=True, metavar="PATH[=MODULE]")
    rec.add_argument("--root", required=True)
    rec.add_argument("--scenarios", required=True)
    rec.add_argument("--out", required=True)
    rec.add_argument("--allow", action="append", default=[], metavar="MODULE")
    rec.add_argument("--now", default="2026-01-01T09:00:00")
    rec.add_argument("--keep-tracebacks", action="store_true")
    dif = commands.add_parser("diff")
    dif.add_argument("old")
    dif.add_argument("new")
    cov = commands.add_parser("coverage")
    cov.add_argument("--recording", required=True)
    cov.add_argument("--map", required=True)
    args = parser.parse_args()
    {"record": record, "diff": diff, "coverage": coverage}[args.command](args)


if __name__ == "__main__":
    main()
