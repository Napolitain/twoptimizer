"""Application failures and their small, portable worker envelope."""

from collections.abc import Mapping
from typing import Any


class ApplicationError(ValueError):
    """A rejected request, independent of the interface used to submit it."""

    def __init__(self, message: str, *, code: str = "invalid_request") -> None:
        super().__init__(message)
        self.code = code


def serialize_error(error: Exception) -> dict[str, str]:
    """Keep the original error text while distinguishing invalid input from failure."""
    invalid = isinstance(error, ValueError)
    return {
        "error": str(error),
        "error_type": "ApplicationError" if invalid else "RuntimeError",
        "code": getattr(error, "code", "invalid_request" if invalid else "execution_failed"),
    }


def deserialize_error(payload: Mapping[str, Any]) -> Exception:
    """Restore application semantics after crossing the execution boundary."""
    message = str(payload["error"])
    if payload.get("error_type") in {"ApplicationError", "ValueError"}:
        return ApplicationError(message, code=str(payload.get("code", "invalid_request")))
    return RuntimeError(message)
