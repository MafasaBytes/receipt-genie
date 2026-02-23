"""
Standard API response utilities.
"""
from typing import Any, Optional
from fastapi.responses import JSONResponse
from fastapi import status


def success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = status.HTTP_200_OK
) -> JSONResponse:
    """Create a standard success response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": message,
            "data": data
        }
    )


def error_response(
    message: str = "An error occurred",
    status_code: int = status.HTTP_400_BAD_REQUEST,
    details: Optional[Any] = None
) -> JSONResponse:
    """Create a standard error response."""
    content = {
        "success": False,
        "message": message,
    }
    if details:
        content["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=content
    )

