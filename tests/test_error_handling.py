import pytest
from unittest.mock import MagicMock
from aiogram.types import ErrorEvent, Update
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError
from bot.handlers import global_error_handler

@pytest.mark.asyncio
async def test_global_error_handler_forbidden():
    # Mock ErrorEvent with TelegramForbiddenError
    mock_update = MagicMock(spec=Update)
    mock_exception = TelegramForbiddenError(method="sendMessage", message="bot was blocked by the user")

    event = ErrorEvent(update=mock_update, exception=mock_exception)

    # Run error handler
    result = await global_error_handler(event)

    # The handler should return True (handled)
    assert result is True

@pytest.mark.asyncio
async def test_global_error_handler_api_error_403():
    mock_update = MagicMock(spec=Update)

    # Mock TelegramAPIError with code 403
    mock_exception = MagicMock(spec=TelegramAPIError)
    mock_exception.code = 403
    mock_exception.message = "Forbidden: bot was blocked by the user"

    event = ErrorEvent(update=mock_update, exception=mock_exception)

    result = await global_error_handler(event)

    assert result is True

@pytest.mark.asyncio
async def test_global_error_handler_other_exception():
    mock_update = MagicMock(spec=Update)
    mock_exception = ValueError("Random error")

    event = ErrorEvent(update=mock_update, exception=mock_exception)

    result = await global_error_handler(event)

    assert result is True
