from __future__ import annotations


class AppError(Exception):
    """Base for domain errors that the API layer translates to HTTP responses."""

    status_code: int = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class UnauthorizedError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class ValidationAppError(AppError):
    status_code = 422


class UnprocessableIngestionError(AppError):
    status_code = 422
