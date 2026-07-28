"""Tests for the asynchronous Instapaper client."""

import json
from urllib.parse import parse_qs

import pytest
from pytest_httpx import HTTPXMock

from instapyper import (
    AsyncInstapaper,
    AuthenticationError,
    BookmarksResponse,
    InstapaperError,
    Tag,
    User,
)
from instapyper.async_client import AsyncBookmark, AsyncFolder, AsyncHighlight

from .conftest import BASE_URL, CONSUMER_KEY, CONSUMER_SECRET, PASSWORD, USERNAME


class TestAsyncInstapaperInit:
    """Tests for async client initialization."""

    def test_init_with_credentials(self, consumer_key: str, consumer_secret: str) -> None:
        client = AsyncInstapaper(consumer_key, consumer_secret)
        assert client._consumer_key == consumer_key
        assert client._consumer_secret == consumer_secret
        assert client._client is None

    def test_init_without_key_raises(self) -> None:
        with pytest.raises(AuthenticationError, match="Consumer key and secret are required"):
            AsyncInstapaper("", CONSUMER_SECRET)

    def test_init_without_secret_raises(self) -> None:
        with pytest.raises(AuthenticationError, match="Consumer key and secret are required"):
            AsyncInstapaper(CONSUMER_KEY, "")


class TestAsyncLogin:
    """Tests for async authentication."""

    async def test_login_success(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        login_response: str,
        user_response: list[dict],
    ) -> None:
        # Mock OAuth token endpoint
        httpx_mock.add_response(
            url=f"{BASE_URL}/oauth/access_token",
            method="POST",
            text=login_response,
        )
        # Mock verify credentials endpoint
        httpx_mock.add_response(
            url=f"{BASE_URL}/account/verify_credentials",
            method="POST",
            json=user_response,
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        user = await client.login(USERNAME, PASSWORD)

        assert isinstance(user, User)
        assert user.username == USERNAME
        assert client.oauth_token is not None
        assert client.oauth_token_secret is not None

    async def test_login_invalid_credentials(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/oauth/access_token",
            method="POST",
            text="Invalid credentials",
            status_code=401,
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        with pytest.raises(AuthenticationError, match="Invalid username or password"):
            await client.login(USERNAME, "wrong_password")

    def test_login_with_token(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)

        assert client.oauth_token == oauth_token
        assert client.oauth_token_secret == oauth_token_secret
        assert client._client is not None


class TestAsyncBookmarks:
    """Tests for async bookmark operations."""

    async def test_get_bookmarks(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        bookmarks_response: dict,
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/bookmarks/list",
            method="POST",
            json=bookmarks_response,
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        bookmarks = await client.get_bookmarks(limit=10)

        assert len(bookmarks) == 2
        assert all(isinstance(b, AsyncBookmark) for b in bookmarks)
        assert bookmarks[0].title == "Test Article 1"
        assert bookmarks[1].starred is True

    async def test_get_bookmarks_with_highlights(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        bookmarks_response: dict,
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/bookmarks/list",
            method="POST",
            json=bookmarks_response,
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        result = await client.get_bookmarks_with_highlights(limit=10)

        assert isinstance(result, BookmarksResponse)
        assert len(result.bookmarks) == 2
        assert all(isinstance(b, AsyncBookmark) for b in result.bookmarks)
        assert len(result.highlights) == 2
        assert all(isinstance(h, AsyncHighlight) for h in result.highlights)
        assert result.highlights[0].text == "Inline highlight text"

    async def test_add_bookmark(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        single_bookmark_response: dict,
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/bookmarks/add",
            method="POST",
            json=single_bookmark_response,
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        bookmark = await client.add_bookmark("https://example.com/new-article")

        assert isinstance(bookmark, AsyncBookmark)
        assert bookmark.url == "https://example.com/new-article"

    async def test_add_bookmark_serializes_str_and_tag_objects(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        single_bookmark_response: dict,
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/bookmarks/add",
            method="POST",
            json=single_bookmark_response,
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        await client.add_bookmark(
            "https://example.com/new-article",
            tags=["tech", Tag(name="python", id=42, count=3)],
        )

        body = parse_qs(httpx_mock.get_requests()[-1].read().decode())
        assert json.loads(body["tags"][0]) == [{"name": "tech"}, {"name": "python"}]

    async def test_delete_bookmark(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/bookmarks/delete",
            method="POST",
            json=[],
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        # Should not raise
        await client.delete_bookmark(100001)

    async def test_get_bookmarks_not_logged_in(
        self, consumer_key: str, consumer_secret: str
    ) -> None:
        client = AsyncInstapaper(consumer_key, consumer_secret)
        with pytest.raises(AuthenticationError, match="Not logged in"):
            await client.get_bookmarks()


class TestAsyncFolders:
    """Tests for async folder operations."""

    async def test_get_folders(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        folders_response: list[dict],
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/folders/list",
            method="POST",
            json=folders_response,
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        folders = await client.get_folders()

        assert len(folders) == 2
        assert all(isinstance(f, AsyncFolder) for f in folders)
        assert folders[0].title == "Tech"
        assert folders[1].folder_id == 5002

    async def test_create_folder(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        folder_response = [
            {
                "type": "folder",
                "folder_id": 5003,
                "title": "New Folder",
                "slug": "new-folder",
                "display_title": "New Folder",
                "sync_to_mobile": 1,
                "position": 2,
            }
        ]
        httpx_mock.add_response(
            url=f"{BASE_URL}/folders/add",
            method="POST",
            json=folder_response,
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        folder = await client.create_folder("New Folder")

        assert isinstance(folder, AsyncFolder)
        assert folder.title == "New Folder"


class TestAsyncHighlights:
    """Tests for async client-level highlight operations."""

    async def test_get_highlights(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        highlights_response: list[dict],
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/bookmarks/100001/highlights",
            method="POST",
            json=highlights_response,
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        highlights = await client.get_highlights(100001)

        assert len(highlights) == 2
        assert all(isinstance(h, AsyncHighlight) for h in highlights)
        assert highlights[0].highlight_id == 9001
        assert highlights[0].text == "This is highlighted text"

    async def test_create_highlight(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/bookmarks/100001/highlight",
            method="POST",
            json=[
                {
                    "type": "highlight",
                    "highlight_id": 9003,
                    "text": "New highlight",
                    "position": 5,
                    "time": 1700002200,
                    "bookmark_id": 100001,
                }
            ],
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        highlight = await client.create_highlight(100001, "New highlight", 5)

        assert isinstance(highlight, AsyncHighlight)
        assert highlight.highlight_id == 9003
        assert highlight.position == 5

    async def test_create_highlight_failure(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/bookmarks/100001/highlight",
            method="POST",
            json=[],
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        with pytest.raises(InstapaperError, match="Failed to create highlight"):
            await client.create_highlight(100001, "New highlight")


class TestAsyncBookmarkText:
    """Tests for async get_bookmark_text."""

    async def test_get_bookmark_text(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/bookmarks/get_text",
            method="POST",
            html="<p>Hello world</p>",
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        assert await client.get_bookmark_text(100001) == "<p>Hello world</p>"

    async def test_get_bookmark_text_invalid_id(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/bookmarks/get_text",
            method="POST",
            status_code=400,
            json=[
                {"type": "error", "error_code": 1241, "message": "Invalid or missing bookmark_id"}
            ],
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        with pytest.raises(InstapaperError, match="Invalid or missing bookmark_id"):
            await client.get_bookmark_text(999)

    async def test_private_get_bookmark_text_returns_empty_on_error(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/bookmarks/get_text",
            method="POST",
            status_code=400,
            json=[
                {"type": "error", "error_code": 1241, "message": "Invalid or missing bookmark_id"}
            ],
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        assert await client._get_bookmark_text(999) == ""


class TestAsyncContextManager:
    """Tests for async context manager."""

    async def test_context_manager(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        async with AsyncInstapaper(consumer_key, consumer_secret) as client:
            client.login_with_token(oauth_token, oauth_token_secret)
            assert client._client is not None

        # After exiting, client should be closed
        assert client._client is None


class TestAsyncErrorHandling:
    """Tests for async error handling."""

    async def test_api_error_response(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        error_response: list[dict],
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/bookmarks/list",
            method="POST",
            json=error_response,
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)

        with pytest.raises(InstapaperError, match="Something went wrong"):
            await client.get_bookmarks()

    async def test_401_raises_auth_error(
        self,
        httpx_mock: HTTPXMock,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/bookmarks/list",
            method="POST",
            text="Unauthorized",
            status_code=401,
        )

        client = AsyncInstapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)

        with pytest.raises(AuthenticationError, match="Invalid or expired OAuth token"):
            await client.get_bookmarks()
