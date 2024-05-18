class CustomBodyException(Exception):
    def __init__(self, code: int, body: dict):
        self.code = code
        self.body = body


class ErrorMessageException(CustomBodyException):
    def __init__(self, code: int, message: str):
        super().__init__(code, {"error_message": message})


class BadRequestException(ErrorMessageException):
    def __init__(self, message: str):
        super().__init__(400, message)


class NotFoundException(ErrorMessageException):
    def __init__(self, message: str):
        super().__init__(404, message)


class UnauthorizedException(ErrorMessageException):
    def __init__(self, message: str):
        super().__init__(401, message)


class ForbiddenException(ErrorMessageException):
    def __init__(self, message: str):
        super().__init__(403, message)
