from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from app.middleware.request_context import request_id_var


def get_request_id() -> str:
    return request_id_var.get()


def success_response(
    message: str,
    data: Optional[Any] = None,
    meta: Optional[Dict[str, Any]] = None,
    status_code: int = 200
) -> JSONResponse:
    content = {
        "success": True,
        "message": message,
        "data": jsonable_encoder(data) if data is not None else {},
        "meta": jsonable_encoder(meta) if meta is not None else {}
    }
    return JSONResponse(status_code=status_code, content=content)


def error_response(
    code: str,
    message: str,
    details: Optional[Any] = None,
    status_code: int = 400,
    request_id: Optional[str] = None
) -> JSONResponse:
    resolved_request_id = request_id or get_request_id()
    content = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": jsonable_encoder(details) if details is not None else {}
        },
        "request_id": resolved_request_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    return JSONResponse(status_code=status_code, content=content)


def paginated_response(
    message: str,
    data: List[Any],
    page: int,
    limit: int,
    total: int,
    status_code: int = 200
) -> JSONResponse:
    content = {
        "success": True,
        "message": message,
        "data": jsonable_encoder(data),
        "meta": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if limit > 0 else 1
        }
    }
    return JSONResponse(status_code=status_code, content=content)
