"""Stand-in payment gateway client (the example never reaches a real service)."""


class GatewayError(Exception):
    pass


class Gateway:
    def __init__(self, url):
        self.url = url

    def charge(self, amount, token):
        raise NotImplementedError("example only")

    def authorize(self, amount, token):
        raise NotImplementedError("example only")

    def refund(self, payment_id, amount):
        raise NotImplementedError("example only")
