"""Tests for the asynchronous Instapaper client."""

import pytest
from pytest_httpx import HTTPXMock

from instapyper import (
    AsyncInstapaper,
    AuthenticationError,
    InstapaperError,
    User,
)
from instapyper.async_client import AsyncBookmark, AsyncFolder

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
                "sync_to_mobile": "1",
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
