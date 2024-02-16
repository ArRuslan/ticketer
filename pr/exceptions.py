class CustomBodyException(Exception):
    def __init__(self, code: int, body: dict):
        self.code = code
        self.body = body


class UnauthorizedException(CustomBodyException):
    def __init__(self, message: str):
        super().__init__(401, {"error_message": message})
