"""Standard API response envelope used by every endpoint.

Every response — success or error — has the same shape:

    {"success": true/false, "message": "...", "data": <payload or null>}

Actual payloads always live under ``data``; ``message`` explains the outcome.
"""

from pydantic import BaseModel


class ApiResponse[T](BaseModel):
    success: bool = True
    message: str = ""
    data: T | None = None

    @classmethod
    def ok(cls, data: T | None = None, message: str = "") -> "ApiResponse[T]":
        return cls(success=True, message=message, data=data)
