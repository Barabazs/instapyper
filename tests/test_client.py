"""Tests for the synchronous Instapaper client."""

import json
from urllib.parse import parse_qs

import pytest
import responses

from instapyper import (
    AuthenticationError,
    Bookmark,
    BookmarksResponse,
    Folder,
    Highlight,
    Instapaper,
    InstapaperError,
    Tag,
    User,
)

from .conftest import BASE_URL, CONSUMER_KEY, CONSUMER_SECRET, PASSWORD, USERNAME


class TestInstapaperInit:
    """Tests for client initialization."""

    def test_init_with_credentials(self, consumer_key: str, consumer_secret: str) -> None:
        client = Instapaper(consumer_key, consumer_secret)
        assert client._consumer_key == consumer_key
        assert client._consumer_secret == consumer_secret
        assert client._session is None

    def test_init_without_key_raises(self) -> None:
        with pytest.raises(AuthenticationError, match="Consumer key and secret are required"):
            Instapaper("", CONSUMER_SECRET)

    def test_init_without_secret_raises(self) -> None:
        with pytest.raises(AuthenticationError, match="Consumer key and secret are required"):
            Instapaper(CONSUMER_KEY, "")


class TestLogin:
    """Tests for authentication."""

    @responses.activate
    def test_login_success(
        self,
        consumer_key: str,
        consumer_secret: str,
        login_response: str,
        user_response: list[dict],
    ) -> None:
        # Mock OAuth token endpoint
        responses.add(
            responses.POST,
            f"{BASE_URL}/oauth/access_token",
            body=login_response,
            status=200,
        )
        # Mock verify credentials endpoint
        responses.add(
            responses.POST,
            f"{BASE_URL}/account/verify_credentials",
            json=user_response,
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        user = client.login(USERNAME, PASSWORD)

        assert isinstance(user, User)
        assert user.username == USERNAME
        assert client.oauth_token is not None
        assert client.oauth_token_secret is not None

    @responses.activate
    def test_login_invalid_credentials(self, consumer_key: str, consumer_secret: str) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/oauth/access_token",
            body="Invalid credentials",
            status=401,
        )

        client = Instapaper(consumer_key, consumer_secret)
        with pytest.raises(AuthenticationError, match="Invalid username or password"):
            client.login(USERNAME, "wrong_password")

    def test_login_with_token(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)

        assert client.oauth_token == oauth_token
        assert client.oauth_token_secret == oauth_token_secret
        assert client._session is not None


class TestBookmarks:
    """Tests for bookmark operations."""

    @responses.activate
    def test_get_bookmarks(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        bookmarks_response: dict,
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/bookmarks/list",
            json=bookmarks_response,
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        bookmarks = client.get_bookmarks(limit=10)

        assert len(bookmarks) == 2
        assert all(isinstance(b, Bookmark) for b in bookmarks)
        assert bookmarks[0].title == "Test Article 1"
        assert bookmarks[1].starred is True

    @responses.activate
    def test_get_bookmarks_with_highlights(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        bookmarks_response: dict,
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/bookmarks/list",
            json=bookmarks_response,
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        result = client.get_bookmarks_with_highlights(limit=10)

        assert isinstance(result, BookmarksResponse)
        assert len(result.bookmarks) == 2
        assert all(isinstance(b, Bookmark) for b in result.bookmarks)
        assert result.bookmarks[0].title == "Test Article 1"
        assert len(result.highlights) == 2
        assert all(isinstance(h, Highlight) for h in result.highlights)
        assert result.highlights[0].text == "Inline highlight text"
        assert result.highlights[0].bookmark_id == 100001
        assert result.highlights[1].bookmark_id == 100002

    @responses.activate
    def test_get_bookmarks_with_highlights_empty(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/bookmarks/list",
            json={"bookmarks": [], "user": {"type": "user"}},
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        result = client.get_bookmarks_with_highlights()

        assert isinstance(result, BookmarksResponse)
        assert result.bookmarks == []
        assert result.highlights == []

    @responses.activate
    def test_add_bookmark(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        single_bookmark_response: dict,
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/bookmarks/add",
            json=single_bookmark_response,
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        bookmark = client.add_bookmark("https://example.com/new-article")

        assert isinstance(bookmark, Bookmark)
        assert bookmark.url == "https://example.com/new-article"

    @responses.activate
    def test_add_bookmark_serializes_str_and_tag_objects(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        single_bookmark_response: dict,
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/bookmarks/add",
            json=single_bookmark_response,
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        client.add_bookmark(
            "https://example.com/new-article",
            tags=["tech", Tag(name="python", id=42, count=3)],
        )

        raw_body = responses.calls[-1].request.body
        assert isinstance(raw_body, bytes)
        body = parse_qs(raw_body.decode())
        assert json.loads(body["tags"][0]) == [{"name": "tech"}, {"name": "python"}]

    @responses.activate
    def test_delete_bookmark(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/bookmarks/delete",
            json=[],
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        # Should not raise
        client.delete_bookmark(100001)

    def test_get_bookmarks_not_logged_in(self, consumer_key: str, consumer_secret: str) -> None:
        client = Instapaper(consumer_key, consumer_secret)
        with pytest.raises(AuthenticationError, match="Not logged in"):
            client.get_bookmarks()


class TestFolders:
    """Tests for folder operations."""

    @responses.activate
    def test_get_folders(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        folders_response: list[dict],
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/folders/list",
            json=folders_response,
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        folders = client.get_folders()

        assert len(folders) == 2
        assert all(isinstance(f, Folder) for f in folders)
        assert folders[0].title == "Tech"
        assert folders[1].folder_id == 5002

    @responses.activate
    def test_create_folder(
        self,
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
        responses.add(
            responses.POST,
            f"{BASE_URL}/folders/add",
            json=folder_response,
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        folder = client.create_folder("New Folder")

        assert isinstance(folder, Folder)
        assert folder.title == "New Folder"

    @responses.activate
    def test_delete_folder(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/folders/delete",
            json=[],
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        # Should not raise
        client.delete_folder(5001)

    @responses.activate
    def test_set_folder_order(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/folders/set_order",
            json=[],
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        # Should not raise
        client.set_folder_order({5001: 1, 5002: 0})


class TestHighlights:
    """Tests for client-level highlight operations."""

    @responses.activate
    def test_get_highlights(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        highlights_response: list[dict],
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/bookmarks/100001/highlights",
            json=highlights_response,
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        highlights = client.get_highlights(100001)

        assert len(highlights) == 2
        assert all(isinstance(h, Highlight) for h in highlights)
        assert highlights[0].highlight_id == 9001
        assert highlights[0].text == "This is highlighted text"

    @responses.activate
    def test_create_highlight(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/bookmarks/100001/highlight",
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
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        highlight = client.create_highlight(100001, "New highlight", 5)

        assert isinstance(highlight, Highlight)
        assert highlight.highlight_id == 9003
        assert highlight.position == 5
        raw_body = responses.calls[-1].request.body
        assert isinstance(raw_body, bytes)
        body = parse_qs(raw_body.decode())
        assert body["text"] == ["New highlight"]
        assert body["position"] == ["5"]

    @responses.activate
    def test_create_highlight_failure(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/bookmarks/100001/highlight",
            json=[],
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        with pytest.raises(InstapaperError, match="Failed to create highlight"):
            client.create_highlight(100001, "New highlight")


class TestBookmarkText:
    """Tests for get_bookmark_text."""

    @responses.activate
    def test_get_bookmark_text(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/bookmarks/get_text",
            body="<p>Hello world</p>",
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        assert client.get_bookmark_text(100001) == "<p>Hello world</p>"

    @responses.activate
    def test_get_bookmark_text_invalid_id(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/bookmarks/get_text",
            json=[
                {"type": "error", "error_code": 1241, "message": "Invalid or missing bookmark_id"}
            ],
            status=400,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        with pytest.raises(InstapaperError, match="Invalid or missing bookmark_id"):
            client.get_bookmark_text(999)

    @responses.activate
    def test_private_get_bookmark_text_returns_empty_on_error(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/bookmarks/get_text",
            json=[
                {"type": "error", "error_code": 1241, "message": "Invalid or missing bookmark_id"}
            ],
            status=400,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)
        assert client._get_bookmark_text(999) == ""


class TestErrorHandling:
    """Tests for error handling."""

    @responses.activate
    def test_api_error_response(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        error_response: list[dict],
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/bookmarks/list",
            json=error_response,
            status=200,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)

        with pytest.raises(InstapaperError, match="Something went wrong"):
            client.get_bookmarks()

    @responses.activate
    def test_401_raises_auth_error(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/bookmarks/list",
            body="Unauthorized",
            status=401,
        )

        client = Instapaper(consumer_key, consumer_secret)
        client.login_with_token(oauth_token, oauth_token_secret)

        with pytest.raises(AuthenticationError, match="Invalid or expired OAuth token"):
            client.get_bookmarks()
