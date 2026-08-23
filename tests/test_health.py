import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from webapp.router import health_check, app, STATIC_DIR, TEMPLATES_DIR
from fastapi import HTTPException
import os

def test_app_mount_static_and_templates():
    assert app is not None
    assert os.path.exists(STATIC_DIR)
    assert os.path.exists(TEMPLATES_DIR)
    # Check that static mount is present on FastAPI app
    routes = [r.path for r in app.routes]
    assert "/static" in routes

@pytest.mark.asyncio
async def test_health_check_ok():
    # Mock DB session
    mock_db = AsyncMock()
    mock_db.execute.return_value = AsyncMock()

    # Mock Bot
    mock_bot = AsyncMock()

    # Mock bot.get_me() returning a mock user
    mock_me = MagicMock()
    mock_me.username = "my_test_bot"
    mock_bot.get_me.return_value = mock_me

    # Mock bot.get_webhook_info()
    mock_webhook = MagicMock()
    mock_webhook.url = "https://test.com/webhook/bot"
    mock_webhook.pending_update_count = 0
    mock_webhook.last_error_date = None
    mock_webhook.last_error_message = None
    mock_bot.get_webhook_info.return_value = mock_webhook

    with patch("webapp.router.get_bot", return_value=mock_bot), \
         patch("os.getenv", side_effect=lambda key, default=None: "https://test.com" if key == "WEBAPP_URL" else None):

        response = await health_check(db=mock_db)

        assert response["database"] == "ok"
        assert response["bot_connectivity"] == "ok"
        assert response["bot_username"] == "my_test_bot"
        assert response["webhook"]["enabled"] is True
        assert response["webhook"]["url"] == "https://test.com/webhook/bot"

@pytest.mark.asyncio
async def test_health_check_database_error():
    # Mock DB that raises an error
    mock_db = AsyncMock()
    mock_db.execute.side_effect = Exception("DB Connection Lost")

    # Mock Bot
    mock_bot = AsyncMock()
    mock_me = MagicMock()
    mock_me.username = "my_test_bot"
    mock_bot.get_me.return_value = mock_me

    with patch("webapp.router.get_bot", return_value=mock_bot):
        with pytest.raises(HTTPException) as exc_info:
            await health_check(db=mock_db)

        assert exc_info.value.status_code == 500
        assert "error" in exc_info.value.detail["database"]
