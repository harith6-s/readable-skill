> ฉบับแปลไว้ให้คนอ่าน ตัวที่ AI ใช้จริงคือ `../references/style.md` (อังกฤษ) ถ้าสองฉบับไม่ตรงกัน ให้ยึดฉบับอังกฤษ

# โค้ดที่อ่านง่ายหน้าตาเป็นอย่างไร

ทุก mode ใช้ไฟล์นี้ เนื้อหาครอบคลุมแค่ flow และโครงสร้าง **เรื่องที่ไฟล์นี้ไม่ได้พูดถึง ให้ทำตาม convention ของภาษาและของโปรเจกต์นั้น** คือ formatter, linter และโค้ดรอบ ๆ ห้ามจัด format โค้ดที่ไม่ได้จัดโครงใหม่

เพดานที่โปรเจกต์ตั้งเองและบังคับจริง (กฎ lint, การเช็กใน CI ที่ทำให้ fail) เช่นความยาวฟังก์ชันสูงสุด ชนะไฟล์นี้ ส่วนค่าเริ่มต้นของเครื่องมือที่โปรเจกต์ไม่เคยตั้งไม่นับ SKILL.md (ขั้น Map) บอกว่าต้องทำอย่างไรเมื่อเรื่องเล่าจะเกินเพดานที่บังคับ

## เป้าหมาย

คนอ่านไล่ request หรือ task หนึ่งตัวได้ตั้งแต่ entrypoint จนจบ จากบนลงล่าง โดยไม่ต้องจำอะไรค้างไว้เกินไม่กี่อย่าง คนจำได้พร้อมกันประมาณ 4-7 อย่าง ทุกครั้งที่กระโดดเข้า helper ที่กระโดดต่อไปอีก ภาระจะเพิ่มอีกชั้น จนลืมว่าออกมาจากบรรทัด 74 เพราะอะไร ความอ่านง่ายจึงวัดจาก:

- **ความลึกของการกระโดด** จาก entrypoint ผ่านโค้ดใน unit (เป้าหมาย: ≤ 1)
- **การตัดสินใจทุกจุดเห็นได้**ใน entrypoint หรือไม่
- **payload ขาออกทุกตัวอ่านได้ทั้งก้อน**ตรงจุดที่ส่งหรือไม่

## เมื่อกฎชนกัน

1. พฤติกรรมถูกต้อง (ถ้า refactor = พฤติกรรมเท่าเดิม)
2. อ่านจากบนลงล่างได้: ลึก ≤ 1 และการตัดสินใจอยู่ในเรื่องเล่า
3. ไม่มี logic ซ้ำ
4. สั้น
5. เร็ว ยอมเสียความเร็วได้เฉพาะงานในหน่วยความจำ ห้ามเพิ่ม query, การเรียก API หรือการอ่านไฟล์ เช่น query ใน loop

## รูปร่าง

1. **entrypoint คือเรื่องเล่า** entrypoint คือสิ่งที่โค้ดข้างนอกเรียก เช่น HTTP handler, task, command, event handler ต้องอ่านเป็นขั้นตอนที่มีเลข เรียงตามลำดับที่ทำงานจริง หัวข้อหน้าตาแบบ `# --- 3. ลงนามหน้าคำขอ (was: request_signing) ---` ส่วน `was:` มีเฉพาะตอน refactor
2. **กระโดดได้ไม่เกิน 1 ชั้น** เรื่องเล่าเรียก helper ใน unit ได้ helper ใน unit ต้องเป็น**ปลายทาง**: เรียก library, framework และ helper ที่ใช้ร่วมกับนอก unit ได้ แต่ห้ามเรียก helper ใน unit ตัวอื่น
3. **การตัดสินใจอยู่ในเรื่องเล่า** ทุก branch ที่เปลี่ยนทิศทาง, ทุก raise หรือ fail, ทุกการเรียกออกไปข้างนอก, การเขียน database และการเปลี่ยน status ต้องเห็นได้ใน entrypoint helper ทำได้แค่คำนวณ จัดรูปแบบ หรือดึงข้อมูล ห้ามตัดสินใจ *ทดสอบด้วยชื่อ:* เก็บ helper ไว้ได้ก็ต่อเมื่อคนอ่านรู้ว่า flow จะไปทางไหนต่อโดยไม่ต้องเปิดเข้าไปดู
4. **payload ต้องเห็นทั้งก้อน** payload ทุกตัวที่ส่งออกไป (HTTP, PDF, queue, email) เป็น literal ก้อนเดียวตรงจุดที่เรียก อ่านได้ลึกถึง `depth` ชั้น (ค่าเริ่มต้น 3) ส่วนที่ลึกกว่านั้นสร้างเป็นตัวแปรมีชื่อไว้เหนือ literal ได้ ห้ามประกอบ payload ด้วย `**` จากหลายฟังก์ชัน และต้องคงลำดับ key
5. **เงื่อนไขยาวเป็นตัวแปรมีชื่อ**ไว้เหนือ literal ไม่ใช่ฟังก์ชันใหม่
6. **ไม่มี logic ซ้ำ ดูเป็นก้อน ไม่ได้นับบรรทัด** ก้อนโค้ดที่ทำงานชิ้นหนึ่งได้ในตัวเอง เช่น เรียก service แล้วแปลงรหัส error และซ้ำทั้งก้อนตั้งแต่ 2 ที่ขึ้นไป ให้รวมเป็น helper ปลายทางตัวเดียว นิพจน์เล็ก ๆ ที่บังเอิญเหมือนกันอยู่ในโค้ดที่ต่างกันไม่นับว่าซ้ำ รวมเฉพาะส่วนที่ทำงานเหมือนกันจริง: เทียบทีละบรรทัด ส่วนที่ต่างให้คงไว้ที่ผู้เรียกหรือส่งเข้าไปเป็น argument ความต่างที่ดูเหมือนไม่ได้ตั้งใจให้ปักหมุด (`PIN(behavior)`) ห้ามทำให้เหมือนกันเอง helper ที่รวมแล้วคืนผลลัพธ์ออกมา แล้วเรื่องเล่าเป็นคน raise (กฎข้อ 3) payload ที่แค่หน้าตาคล้ายกันไม่ต้องรวม (กฎข้อ 4)
7. **ค่าคงที่และรหัส status หรือ step** มีชื่อเดียวอยู่ที่เดียว ห้าม inline เป็น literal
8. **import อยู่หัวไฟล์** ยกเว้น import ที่ตัด circular import ให้คงไว้ที่เดิม พร้อมเหตุผล 1 บรรทัด
9. **แผนที่หัวไฟล์** ไฟล์เรื่องเล่าทุกไฟล์เริ่มด้วย docstring สั้น ๆ: มี entrypoint อะไร, แต่ละตัวมีขั้นตอนอะไร และเรียกออกไปข้างนอกอะไรตามลำดับ ต้องระบุ hook ที่ framework เรียกเองด้วย เพราะคนอ่านมองไม่เห็นบรรทัดที่เรียก
10. **visibility** ทุกอย่างที่ไม่อยู่ใน public surface ให้เป็น private ด้วยกลไกของภาษานั้น: Python `_name`, TypeScript ไม่ `export`, Go ตัวพิมพ์เล็ก ตอน refactor นี่คือการเปลี่ยนชื่อแบบเดียวที่ทำได้

## การจัดไฟล์ (`layout`)

- `A` (ค่าเริ่มต้น): 1 ไฟล์ต่อ 1 งาน งาน (task) คือขั้นหนึ่งของ flow ทางธุรกิจ รวมทุก entrypoint ที่มีหน้าที่แค่เริ่มหรือส่งขั้นนั้นเข้าคิว (ดูขั้น Map ใน `SKILL.md`) unit ที่มีงานเดียวใช้ชื่อไฟล์เดิมเป็นที่อยู่ของเรื่องเล่า ในไฟล์งาน public entrypoint อยู่บนสุด helper ที่มีผู้เรียกในไฟล์ตัวเดียวอยู่ใต้ผู้เรียกนั้นทันที คนอ่านจะกระโดดลงไปไม่กี่บรรทัดแล้วกลับมา ปลายทางที่มีผู้เรียกหลายตัวและทุกตัวอยู่ในไฟล์นี้ อยู่ท้ายไฟล์ ใต้ผู้เรียกทุกตัว
- `B`: 1 ไฟล์ต่อ 1 ผลผลิต (เอกสาร, ข้อความ, ชนิด payload) เก็บตัวสร้างของมัน
- `AB`: ไฟล์ task แบบ A ที่แต่ละขั้นเรียกตัวสร้างผลผลิตแบบ B ลึก 1 ชั้น

ใช้กับทุก layout:
- **`shared.py`** 1 ไฟล์ต่อ package เก็บปลายทางที่ถูกเรียกจาก 2 ไฟล์ขึ้นไป ฟังก์ชันในไฟล์นี้ไม่เรียกกันเอง คนอ่านที่กระโดดมาจะเจอโค้ดที่ไม่มีอะไรต่อข้างหลัง ภาษาอื่นใช้ชื่อเดียวกัน (`shared.ts`, `shared.go`)
- **สั้นไม่ได้แปลว่าเป็นของส่วนรวม** ฟังก์ชันที่ตัดสินใจ (raise, เลือกขั้นต่อไป, เขียนข้อมูล) คือเรื่องเล่า ต้องอยู่ในไฟล์งานของมันไม่ว่าจะสั้นแค่ไหน `shared.py` เก็บแค่ปลายทาง
- **ไม่มี facade** `__init__.py` (หรือ `index.ts`) ไม่มีโค้ดและไม่ re-export อะไร คนเรียก import แต่ละชื่อจากไฟล์ของมันเอง "go to definition" จะได้ไปถึงโค้ดจริง
- **แยกไฟล์เมื่อช่วยลดการกระโดดเท่านั้น** การให้แต่ละงานมีไฟล์ของตัวเองช่วยลดสิ่งที่คนอ่านต้องข้าม แต่การหั่นงานเดียวไปหลายไฟล์ทำให้กระโดดมากขึ้น ทำได้เฉพาะตัวสร้างผลผลิตของ `B` และ `AB`
- **โค้ดที่ไม่มีใครเรียก** อยู่ในไฟล์งานของมัน หรือใน `shared.py` ถ้าไม่มีงานไหนเป็นเจ้าของ ปักไว้ว่า `PIN(behavior): no caller found`

## Class หรือ function (`style=auto`)

class เพิ่มการกระโดด 3 แบบที่คนอ่านไม่เห็นเป็นการเรียก: ไล่ inheritance และ mixin, hook ที่ framework เรียกเอง และข้อมูลที่ส่งจาก method หนึ่งไปอีก method ผ่าน `self`

1. **framework มาก่อน** ที่ไหน framework หรือโปรเจกต์บังคับให้เป็น class (Django class-based view, DRF serializer, NestJS controller) ก็ใช้ class ห้ามสู้กับ framework
2. **นอกนั้นค่าเริ่มต้นเป็น function** เรื่องเล่าคือฟังก์ชันตัวเดียว หรือ method ตัวเดียวที่ framework เรียก ข้อมูลส่งผ่าน argument และตัวแปร local
3. **ใช้ class เมื่อมี state ที่ใช้ร่วมกันจริงเท่านั้น** เช่น context (user, คำขอหลัก) ที่หลาย entrypoint ใช้ร่วมกัน method ข้างในต้องทำตามกฎความลึก กำหนด `self.x` ได้เฉพาะใน `__init__` ห้ามกำหนดใน method หนึ่งเพื่อให้อีก method อ่าน
4. **inheritance ของโปรเจกต์ไม่เกิน 1 ชั้นต่อเรื่องเล่า** base class ของ framework ไม่นับ mixin ที่เป็น public อยู่แล้วให้คงไว้ แต่ห้ามสร้าง mixin ใหม่
5. **ห้ามแปลง class ที่เป็น public เป็น function หรือกลับกัน** แปลงได้เฉพาะของภายใน
6. **hook ที่ framework เรียกเองต้องอยู่ในแผนที่หัวไฟล์** เช่น "DRF เรียก `get_queryset` → … → `get_serializer`"

ภาษาที่ไม่มี class ใช้หลักเดียวกัน ใน Go ใช้ method บน struct เฉพาะเมื่อมี state จริง (client, config) และ embedding นับเป็น inheritance

## เก็บ, inline หรือรวม (refactor)

| ฟังก์ชันหน้าตาแบบนี้ | ทำแบบนี้ |
|---|---|
| ใช้ครั้งเดียว ห่อโค้ดไม่กี่บรรทัด | inline เป็นขั้นตอนที่มีเลข |
| เรียก helper ใน unit ตัวอื่นต่อ | inline หรือยุบตัวที่มันเรียกเข้าไป |
| รับ flag หรือ mode แล้วแตก branch ตามค่านั้น | inline เข้าไปในผู้เรียกแต่ละตัวพร้อมทุก branch: flag ที่ผู้เรียกนั้นไม่เคยส่ง ให้เป็นตัวแปร local ที่ตั้งค่าเริ่มต้น และคง branch ของมันไว้พร้อมปัก PIN |
| คำนวณหรือจัดรูปแบบล้วน, ผู้เรียก 2 ตัวขึ้นไป, ชื่อบอกครบ | เก็บไว้เป็นปลายทาง: ไว้ท้ายไฟล์ถ้าผู้เรียกทุกตัวอยู่ในไฟล์นั้น ไม่อย่างนั้นไว้ใน `shared.py` |
| ก้อนเดียวกันถูกคัดลอกไว้ 2 ที่ขึ้นไป | รวมส่วนที่ทำงานเหมือนกันเป็นปลายทางตัวเดียวที่คืนผลลัพธ์: ไว้ใต้ผู้เรียกทันทีถ้าทุกก้อนอยู่ในฟังก์ชันเดียว ไว้ท้ายไฟล์ถ้าทุกก้อนอยู่ในไฟล์เดียว ไม่อย่างนั้นไว้ใน `shared.py` เรื่องเล่ายังเป็นคน raise |
| สร้างแค่ส่วนหนึ่งของ payload | inline เข้าไปใน literal ของ payload |
| ฟังก์ชันเงื่อนไขที่ถูกส่งเป็น argument (`publish(..., waiting)`) | ส่งค่าแทน หรือ inline การเช็ก |

## จุดที่ skill นี้ไม่เห็นด้วยกับคำแนะนำทั่วไป

คำแนะนำ "clean code" ส่วนใหญ่ที่ AI รู้อยู่แล้วดึงไปทางแตกเป็นฟังก์ชันเล็ก ๆ จำนวนมาก ถ้าขัดกับเป้าหมายข้างบน ให้ยึดไฟล์นี้

| คำแนะนำทั่วไป | ในงานนี้ |
|---|---|
| ตั้งชื่อให้สื่อความหมาย | ใช้ |
| DRY | ใช้กับ logic: ก้อนที่ซ้ำทั้งก้อนตั้งแต่ 2 ที่ขึ้นไปรวมเป็น helper ปลายทางตัวเดียว payload ที่แค่หน้าตาคล้ายกันไม่ต้องรวม |
| YAGNI | ใช้ ห้ามสร้าง class, mixin หรือฟังก์ชัน "เผื่อไว้" |
| Single responsibility | ใช้ที่ระดับงาน: 1 entrypoint เล่า 1 เรื่อง ไม่ใช่ทุก 5 บรรทัด |
| ฟังก์ชันต้องสั้น, "extract till you drop" | **ไม่ใช้** ฟังก์ชันยาวได้ ถ้าอ่านเป็นขั้นตอนมีเลข |
| Stepdown rule | ใช้ครึ่งเดียว เอาการเรียงจากบนลงล่าง แต่ไม่แตกทุกระดับ abstraction เป็นฟังก์ชัน |
| "comment คือความล้มเหลวที่เขียนโค้ดให้สื่อเองไม่ได้" | **ไม่ใช้** หัวข้อขั้นตอนคือ comment ที่ต้องมี |
| สืบทอด class เพื่อ reuse | **ไม่ใช้** ส่ง argument แทน เว้นแต่ framework บังคับให้เป็น class |

### Red flags (เจอจริงตอนรันแบบไม่มี skill)

| ความคิด | ความจริง |
|---|---|
| "helper ยิ่งเล็กยิ่งชัด" | helper ทุกตัวคือการกระโดดเพิ่ม 1 ครั้ง novice อ่านโค้ดที่แยก method ได้ช้ากว่า แม้จะบอกว่าชอบมากกว่า |
| "เงื่อนไขยาวนี้ควรเป็นฟังก์ชัน" | ตั้งชื่อเป็นตัวแปรไว้เหนือ literal |
| "เขียน docstring ภาพรวมไว้แล้วก็พอ" | แผนที่ช่วยได้ แต่การกระโดดยังอยู่ ต้องแก้ด้วย |
| "รวม payload ด้วย `**` จะได้ไม่ซ้ำ key" | ซ่อนรูปร่าง payload และอาจทำให้ลำดับ key เปลี่ยน |
| "ทำเป็น class หรือ mixin จะได้ reuse" | inheritance ทุกชั้นคือการกระโดดที่ไม่มีใครเห็น ส่ง argument แทน |

## ตัวอย่าง

ตัวอย่างทั้งหมดแต่งขึ้น เพื่อให้แต่ละตัวเห็นหลักการเดียวชัด ๆ เขียนด้วย Python แต่หลักการใช้ได้กับทุกภาษา

### กระโดดไปทั่ว

```python
def send_contract(contract_id):
    contract = Contract.objects.get(id=contract_id)
    document = build_document(contract)
    return render_and_store(contract, document)


def build_document(contract):
    return {"customer": customer_block(contract.customer), **signing_block(contract)}


def customer_block(customer):
    return {"name": full_name(customer), **address_block(customer)}


def full_name(customer):
    return f"{customer.first_name} {customer.last_name}"


def address_block(customer):
    return {"city": customer.city or "", "zip": customer.zip_code}


def signing_block(contract):
    if needs_manager(contract):
        return {"signer": contract.manager.name, "signed_at": format_date(contract.signed_at)}
    return {"signer": contract.officer.name}


def needs_manager(contract):
    return contract.amount > 100_000 and not contract.is_renewal


def render_and_store(contract, document):
    res = pdf_api.post("/render", json={"file_name": f"{contract.code}.pdf", **document})
    if res.status_code != 200:
        raise RenderError(res.text)
    contract.file_url = storage.upload(res.content)
    contract.save()
    return contract.file_url
```

ถ้าอยากรู้ว่า `/render` ได้รับอะไร คนอ่านต้องเปิด 7 ฟังก์ชัน ลึกลงไป 3 ชั้น และไล่ `**` อีก 3 จุด การเลือกคนลงนาม การ raise และการเขียน database ซ่อนอยู่ใน helper ทั้งหมด

### พฤติกรรมเดิม เขียนเป็นเรื่องเล่า

```python
"""เอกสารสัญญา

send_contract(contract_id)
  1. โหลดสัญญา
  2. เลือกคนลงนาม
  3. สร้าง PDF     → pdf_api POST /render
  4. เก็บไฟล์      → storage.upload, contract.save()
"""


def send_contract(contract_id):
    # --- 1. โหลดสัญญา ---
    contract = Contract.objects.get(id=contract_id)
    customer = contract.customer

    # --- 2. เลือกคนลงนาม (was: signing_block, needs_manager) ---
    needs_manager = contract.amount > 100_000 and not contract.is_renewal
    signer = contract.manager if needs_manager else contract.officer

    # --- 3. สร้าง PDF (was: build_document, customer_block, full_name, address_block) ---
    body = {
        "file_name": f"{contract.code}.pdf",
        "customer": {
            "name": f"{customer.first_name} {customer.last_name}",
            "city": customer.city or "",
            "zip": customer.zip_code,
        },
        "signer": signer.name,
    }
    if needs_manager:
        body["signed_at"] = format_date(contract.signed_at)
    res = pdf_api.post("/render", json=body)
    if res.status_code != 200:
        raise RenderError(res.text)

    # --- 4. เก็บไฟล์ (was: render_and_store) ---
    contract.file_url = storage.upload(res.content)
    contract.save()
    return contract.file_url
```

- การตัดสินใจทุกจุดเห็นได้ในเรื่องเล่า: ใครลงนาม, ล้มเหลวเมื่อไร, บันทึกอะไร
- payload เป็น literal ก้อนเดียว `signed_at` ถูกเติมต่อท้ายทันที จึงยังเป็น key สุดท้ายเหมือนเดิม
- ชื่อเดิมยังอยู่ในหัวข้อขั้นตอน ไม่เหลือ helper ใน unit เลย `format_date` เป็นของที่โค้ดอื่นใช้ร่วมด้วย จึงนับเหมือนเรียก library

### โค้ดซ้ำที่ไม่ได้ซ้ำจริง

entrypoint 2 ตัวดูเหมือนคัดลอกการเช็กลายเซ็นมาเหมือนกัน:

```python
def sign_contract(contract):
    code = "80"
    try:
        res = signature_api.post("/signature", json={"email": contract.officer.email})
        if res.json()["ok"] != True:
            if res.json()["errors"][0]["message"] == "Not found":
                code = "81"
                raise Exception("User has no signature.")
            code = "82"
            raise Exception("Signature service error.")
        signature = res.json()["image"]
        ...
    except Exception as e:
        return {"status": "error", "code": code, "data": str(e)}


def sign_receipt(receipt):
    code = "80"
    try:
        res = signature_api.post("/signature", json={"email": receipt.cashier.email})
        if res.json()["ok"] == False:
            if res.json()["errors"][0]["message"] == "Not found":
                code = "81"
                raise Exception("User has no signature.")
            code = "82"
            raise Exception("Signature service error.")
        signature = res.json().get("image")
        ...
    except Exception as e:
        return {"status": "error", "code": code, "data": str(e)}
```

แต่ 2 ชุดนี้ต่างกัน:
- เมื่อ `ok` เป็น `None` เงื่อนไข `!= True` เป็นจริง แต่ `== False` เป็นเท็จ `sign_contract` จึงล้มเหลวด้วยรหัส `82` ส่วน `sign_receipt` ทำงานต่อ
- เมื่อไม่มี `image` การเขียน `["image"]` จะ raise `KeyError` ส่วน `.get("image")` คืน `None`
- `code` เป็นตัวแปร local ที่ `except` อ่าน

ถ้ารวมทั้งบล็อกเป็น helper ตัวเดียว ทั้งสามเรื่องจะพัง:

```python
# ผิด
def _get_signature(email):
    res = signature_api.post("/signature", json={"email": email})
    if res.json()["ok"] != True:              # sign_receipt เช็กด้วย == False
        if res.json()["errors"][0]["message"] == "Not found":
            code = "81"                       # เป็นตัวแปรของ helper เอง ผู้เรียกยังคืน "80"
            raise Exception("User has no signature.")
        code = "82"
        raise Exception("Signature service error.")
    return res.json()["image"]                # sign_receipt ใช้ .get("image")
```

ส่วนที่ทำงานเหมือนกันจริงทั้ง 2 ชุดมีแค่การแปล error ให้รวมเฉพาะส่วนนั้นเป็นปลายทางที่คืนผลลัพธ์ ส่วนที่เหลือคงไว้ในแต่ละเรื่องเล่า:

```python
def _signature_error(data):
    if data["errors"][0]["message"] == "Not found":
        return "81", "User has no signature."
    return "82", "Signature service error."


def sign_contract(contract):
    code = "80"
    try:
        res = signature_api.post("/signature", json={"email": contract.officer.email})
        if res.json()["ok"] != True:
            code, message = _signature_error(res.json())
            raise Exception(message)
        signature = res.json()["image"]
        ...
    except Exception as e:
        return {"status": "error", "code": code, "data": str(e)}


def sign_receipt(receipt):
    code = "80"
    try:
        res = signature_api.post("/signature", json={"email": receipt.cashier.email})
        # PIN(behavior): เช็ก ok ด้วย == False และอ่าน image ด้วย .get() ส่วน sign_contract ใช้ != True และ ["image"]
        if res.json()["ok"] == False:
            code, message = _signature_error(res.json())
            raise Exception(message)
        signature = res.json().get("image")
        ...
    except Exception as e:
        return {"status": "error", "code": code, "data": str(e)}
```

เรื่องเล่ายังเป็นคน raise, `code` ยังถูกตั้งค่าในที่ที่ `except` อ่านเห็น และความต่างที่ดูเหมือนไม่ได้ตั้งใจถูกปักหมุดไว้ ไม่ได้ถูกแก้
