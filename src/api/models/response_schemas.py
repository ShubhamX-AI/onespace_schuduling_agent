# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
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
