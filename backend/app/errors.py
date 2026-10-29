class AppError(Exception):
    """A business-rule failure that maps to a JSON error response.

    `code` is a stable machine-readable string the frontend maps to plain-language text.
    """

    status_code = 400
    default_code = "bad_request"

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code


class ValidationFailed(AppError):
    status_code = 422
    default_code = "validation_error"


class Unauthenticated(AppError):
    status_code = 401
    default_code = "unauthenticated"


class Forbidden(AppError):
    status_code = 403
    default_code = "forbidden"


class NotFound(AppError):
    status_code = 404
    default_code = "not_found"
