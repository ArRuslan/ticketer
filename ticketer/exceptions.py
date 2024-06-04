from __future__ import annotations


class CustomBodyException(Exception):
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self.body = body


class ErrorMessageException(CustomBodyException):
    def __init__(self, status_code: int, error_code: int, message: str):
        super().__init__(status_code, {"error_message": message, "error_code": error_code})

        self.error_code = error_code
        self.error_message = message

    def format(self, *args, **kwargs) -> ErrorMessageException:
        return ErrorMessageException(self.status_code, self.error_code, self.error_message.format(*args, **kwargs))
