"""Application errors that map to the API error contract ``{"error": {code, message}}``."""

from __future__ import annotations


class AppError(Exception):
    status_code: int = 400
    code: str = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class UpstreamError(AppError):
    """A NASA/JPL endpoint failed or returned something unusable."""

    status_code = 502
    code = "upstream_unavailable"


class NoDataError(AppError):
    status_code = 503
    code = "no_data"


class InvalidRequestError(AppError):
    status_code = 422
    code = "invalid_request"
