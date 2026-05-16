import pytest
from unittest.mock import AsyncMock, MagicMock
from utils.publisher import publish_post, perform_copy_to_channel
from database.models import Post
import json

@pytest.mark.asyncio
async def test_publish_post_sends_preview(monkeypatch):
    # Mock database
    mock_post = Post(
        id=1,
        creator_id=123,
        text="Hello 🦆",
        entities_json=json.dumps([{"type": "custom_emoji", "offset": 6, "length": 2, "custom_emoji_id": "12345"}]),
        channel_id=999
    )

    # Mock bot
    bot = AsyncMock()
    # Ensure send_message returns an object with message_id and chat.id
    msg_mock = MagicMock()
    msg_mock.message_id = 456
    msg_mock.chat.id = 123
    bot.send_message.return_value = msg_mock

    # Mock DB session
    mock_session = AsyncMock()

    # Correct way to mock scalar_one_or_none in async session
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = mock_post
    mock_session.execute.return_value = execute_result

    # We need to mock AsyncSessionLocal
    session_factory = MagicMock()
    session_factory.return_value.__aenter__.return_value = mock_session
    monkeypatch.setattr("utils.publisher.AsyncSessionLocal", session_factory)

    success = await publish_post(bot, 1)

    assert success is True
    bot.send_message.assert_called_once()
    assert bot.send_message.call_args.kwargs['chat_id'] == 123
    assert "reply_markup" in bot.send_message.call_args.kwargs
    assert mock_post.preview_message_id == 456

@pytest.mark.asyncio
async def test_perform_copy_to_channel(monkeypatch):
    mock_post = Post(
        id=1,
        creator_id=123,
        text="Hello 🦆",
        preview_message_id=456,
        preview_chat_id=123,
        channel_id=999
    )

    bot = AsyncMock()
    mock_session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = mock_post
    mock_session.execute.return_value = execute_result

    session_factory = MagicMock()
    session_factory.return_value.__aenter__.return_value = mock_session
    monkeypatch.setattr("utils.publisher.AsyncSessionLocal", session_factory)

    success = await perform_copy_to_channel(bot, 1)

    assert success is True
    bot.copy_message.assert_called_once_with(
        chat_id=999,
        from_chat_id=123,
        message_id=456
    )
    assert mock_post.is_published is True
