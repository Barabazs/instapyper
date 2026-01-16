"""Shared test fixtures."""

import pytest

# Test credentials (fake)
CONSUMER_KEY = "test_consumer_key"
CONSUMER_SECRET = "test_consumer_secret"
USERNAME = "test@example.com"
PASSWORD = "test_password"
OAUTH_TOKEN = "test_oauth_token"
OAUTH_TOKEN_SECRET = "test_oauth_token_secret"

# API URLs
BASE_URL = "https://www.instapaper.com/api/1.1"


@pytest.fixture
def consumer_key() -> str:
    return CONSUMER_KEY


@pytest.fixture
def consumer_secret() -> str:
    return CONSUMER_SECRET


@pytest.fixture
def oauth_token() -> str:
    return OAUTH_TOKEN


@pytest.fixture
def oauth_token_secret() -> str:
    return OAUTH_TOKEN_SECRET


@pytest.fixture
def login_response() -> str:
    """OAuth token response from login."""
    return f"oauth_token={OAUTH_TOKEN}&oauth_token_secret={OAUTH_TOKEN_SECRET}"


@pytest.fixture
def user_response() -> list[dict]:
    """User verification response."""
    return [
        {
            "type": "user",
            "user_id": 12345,
            "username": USERNAME,
            "subscription_is_active": "1",
        }
    ]


@pytest.fixture
def bookmarks_response() -> dict:
    """Bookmarks list response."""
    return {
        "bookmarks": [
            {
                "type": "bookmark",
                "bookmark_id": 100001,
                "url": "https://example.com/article1",
                "title": "Test Article 1",
                "description": "Description 1",
                "time": 1700000000,
                "progress": 0.5,
                "progress_timestamp": 1700000100,
                "starred": "0",
                "hash": "abc123",
                "private_source": "",
            },
            {
                "type": "bookmark",
                "bookmark_id": 100002,
                "url": "https://example.com/article2",
                "title": "Test Article 2",
                "description": "Description 2",
                "time": 1700000200,
                "progress": 0.0,
                "progress_timestamp": 0,
                "starred": "1",
                "hash": "def456",
                "private_source": "",
            },
        ],
        "user": {"type": "user", "user_id": 12345, "username": USERNAME},
    }


@pytest.fixture
def single_bookmark_response() -> list[dict]:
    """Single bookmark response (e.g., after add/star)."""
    return [
        {
            "type": "bookmark",
            "bookmark_id": 100003,
            "url": "https://example.com/new-article",
            "title": "New Article",
            "description": "",
            "time": 1700001000,
            "progress": 0.0,
            "progress_timestamp": 0,
            "starred": "0",
            "hash": "ghi789",
            "private_source": "",
        }
    ]


@pytest.fixture
def folders_response() -> list[dict]:
    """Folders list response."""
    return [
        {
            "type": "folder",
            "folder_id": 5001,
            "title": "Tech",
            "slug": "tech",
            "display_title": "Tech",
            "sync_to_mobile": "1",
            "position": 0,
        },
        {
            "type": "folder",
            "folder_id": 5002,
            "title": "News",
            "slug": "news",
            "display_title": "News",
            "sync_to_mobile": "1",
            "position": 1,
        },
    ]


@pytest.fixture
def highlights_response() -> list[dict]:
    """Highlights list response."""
    return [
        {
            "type": "highlight",
            "highlight_id": 9001,
            "text": "This is highlighted text",
            "position": 100,
            "time": 1700002000,
            "bookmark_id": 100001,
        },
        {
            "type": "highlight",
            "highlight_id": 9002,
            "text": "Another highlight",
            "position": 200,
            "time": 1700002100,
            "bookmark_id": 100001,
        },
    ]


@pytest.fixture
def error_response() -> list[dict]:
    """Error response."""
    return [{"type": "error", "error_code": 1500, "message": "Something went wrong"}]
