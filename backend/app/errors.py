class AppError(Exception):
    """A business-rule failure that maps to a JSON error response."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_error"


class Unauthenticated(AppError):
    status_code = 401
    code = "unauthenticated"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class NotFound(AppError):
    status_code = 404
    code = "not_found"
