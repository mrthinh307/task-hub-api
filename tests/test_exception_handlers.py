from unittest.mock import Mock

import pytest
from starlette.requests import Request

from app.api import exception_handlers


@pytest.mark.asyncio
async def test_unhandled_exception_handler_sanitizes_request_log_values(
    monkeypatch,
) -> None:
    request = Mock(spec=Request)
    request.method = "GE\nT"
    request.url.path = "/café\r\nadmin\x00\x7f"
    error = RuntimeError("unexpected")
    log_error = Mock()
    monkeypatch.setattr(exception_handlers.logger, "error", log_error)

    response = await exception_handlers.unhandled_exception_handler(request, error)

    assert response.status_code == 500
    log_error.assert_called_once_with(
        "Unhandled exception while processing %s %s",
        "GE\\x0aT",
        "/café\\x0d\\x0aadmin\\x00\\x7f",
        exc_info=(RuntimeError, error, error.__traceback__),
    )
