"""Consistent JSON envelope: {success, data, error[, meta]}."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


def ok(data: Any, meta: dict | None = None) -> dict:
    body = {"success": True, "data": data, "error": None}
    if meta is not None:
        body["meta"] = meta
    return body


def _error(
    request: Request, status: int, code: str, message: str, details: Any = None
) -> JSONResponse:
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    ref = getattr(request.state, "ref", None)  # set by stats19.api.request_log
    if ref is not None:
        error["ref"] = ref
    return JSONResponse(
        status_code=status, content={"success": False, "data": None, "error": error}
    )


class NotFound(HTTPException):
    def __init__(self, message: str):
        super().__init__(status_code=404, detail=message)


class ApiError(Exception):
    """An error with an explicit status and machine-readable code."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]
        return _error(request, 422, "validation_error", "Invalid request parameters", details)

    @app.exception_handler(ApiError)
    async def _api(request: Request, exc: ApiError) -> JSONResponse:
        return _error(request, exc.status, exc.code, exc.message)

    @app.exception_handler(HTTPException)
    async def _http(request: Request, exc: HTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        return _error(request, exc.status_code, code, str(exc.detail))
