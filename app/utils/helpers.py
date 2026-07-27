from typing import Any


def format_api_response(
    data: Any, message: str = "Success", success: bool = True
) -> dict[str, Any]:
    """Standardized API response wrapper helper."""
    return {"success": success, "message": message, "data": data}
