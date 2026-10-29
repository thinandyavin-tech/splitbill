from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.config import settings
from app.errors import AppError
from app.routes import router

app = FastAPI(title="SplitBill")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


# Every error response has the shape {"error": {"code": ..., "message": ...}}.
def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


@app.exception_handler(AppError)
def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0]
    location = ".".join(str(p) for p in first["loc"] if p != "body")
    message = f"{location}: {first['msg']}" if location else first["msg"]
    return error_response(422, "validation_error", message)


@app.exception_handler(HTTPException)
def handle_http_error(_: Request, exc: HTTPException) -> JSONResponse:
    return error_response(exc.status_code, "http_error", str(exc.detail))
