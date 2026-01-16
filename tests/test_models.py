"""Tests for data models."""

from unittest.mock import MagicMock

import pytest

from instapyper import Bookmark, Folder, Highlight, User
from instapyper.models import html_to_text


class TestUser:
    """Tests for User model."""

    def test_from_api(self) -> None:
        data = {
            "type": "user",
            "user_id": 12345,
            "username": "test@example.com",
            "subscription_is_active": "1",
        }
        user = User.from_api(data)

        assert user.user_id == 12345
        assert user.username == "test@example.com"
        assert user.subscription_is_active is True

    def test_from_api_inactive_subscription(self) -> None:
        data = {
            "type": "user",
            "user_id": 12345,
            "username": "test@example.com",
            "subscription_is_active": "0",
        }
        user = User.from_api(data)
        assert user.subscription_is_active is False

    def test_from_api_missing_subscription(self) -> None:
        data = {
            "type": "user",
            "user_id": 12345,
            "username": "test@example.com",
        }
        user = User.from_api(data)
        assert user.subscription_is_active is False


class TestBookmark:
    """Tests for Bookmark model."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def bookmark_data(self) -> dict:
        return {
            "bookmark_id": 100001,
            "url": "https://example.com/article",
            "title": "Test Article",
            "description": "A test description",
            "time": 1700000000,
            "progress": 0.5,
            "progress_timestamp": 1700000100,
            "starred": "1",
            "hash": "abc123",
            "private_source": "",
        }

    def test_from_api(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        bookmark = Bookmark.from_api(bookmark_data, mock_client)

        assert bookmark.bookmark_id == 100001
        assert bookmark.url == "https://example.com/article"
        assert bookmark.title == "Test Article"
        assert bookmark.description == "A test description"
        assert bookmark.progress == 0.5
        assert bookmark.starred is True
        assert bookmark.hash == "abc123"

    def test_from_api_unstarred(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        bookmark_data["starred"] = "0"
        bookmark = Bookmark.from_api(bookmark_data, mock_client)
        assert bookmark.starred is False

    def test_from_api_missing_fields(self, mock_client: MagicMock) -> None:
        minimal_data = {
            "bookmark_id": 100001,
            "url": "https://example.com",
        }
        bookmark = Bookmark.from_api(minimal_data, mock_client)

        assert bookmark.bookmark_id == 100001
        assert bookmark.url == "https://example.com"
        assert bookmark.title == ""
        assert bookmark.description == ""
        assert bookmark.progress == 0.0
        assert bookmark.starred is False

    def test_star(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        mock_client._request.return_value = {"bookmarks": [bookmark_data]}
        bookmark = Bookmark.from_api(bookmark_data, mock_client)

        result = bookmark.star()

        mock_client._request.assert_called_once_with("bookmarks/star", bookmark_id=100001)
        assert isinstance(result, Bookmark)

    def test_delete(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        mock_client._request.return_value = {}
        bookmark = Bookmark.from_api(bookmark_data, mock_client)

        bookmark.delete()

        mock_client._request.assert_called_once_with("bookmarks/delete", bookmark_id=100001)

    def test_move(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        mock_client._request.return_value = {"bookmarks": [bookmark_data]}
        bookmark = Bookmark.from_api(bookmark_data, mock_client)

        result = bookmark.move(5001)

        mock_client._request.assert_called_once_with(
            "bookmarks/move", bookmark_id=100001, folder_id=5001
        )
        assert isinstance(result, Bookmark)

    def test_update_progress(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        mock_client._request.return_value = {"bookmarks": [bookmark_data]}
        bookmark = Bookmark.from_api(bookmark_data, mock_client)

        result = bookmark.update_progress(0.75)

        assert mock_client._request.called
        call_args = mock_client._request.call_args
        assert call_args[0][0] == "bookmarks/update_read_progress"
        assert call_args[1]["bookmark_id"] == 100001
        assert call_args[1]["progress"] == 0.75
        assert isinstance(result, Bookmark)

    def test_update_progress_invalid(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        bookmark = Bookmark.from_api(bookmark_data, mock_client)

        with pytest.raises(ValueError, match="Progress must be between"):
            bookmark.update_progress(1.5)

        with pytest.raises(ValueError, match="Progress must be between"):
            bookmark.update_progress(-0.1)

    def test_get_highlights(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        highlight_data = {
            "type": "highlight",
            "highlight_id": 9001,
            "text": "Highlighted text",
            "position": 100,
            "time": 1700002000,
            "bookmark_id": 100001,
        }
        mock_client._request.return_value = {"items": [highlight_data]}
        bookmark = Bookmark.from_api(bookmark_data, mock_client)

        highlights = bookmark.get_highlights()

        mock_client._request.assert_called_once_with("bookmarks/100001/highlights")
        assert len(highlights) == 1
        assert isinstance(highlights[0], Highlight)
        assert highlights[0].text == "Highlighted text"


class TestFolder:
    """Tests for Folder model."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def folder_data(self) -> dict:
        return {
            "folder_id": 5001,
            "title": "Tech",
            "slug": "tech",
            "display_title": "Tech",
            "sync_to_mobile": "1",
            "position": 0,
        }

    def test_from_api(self, folder_data: dict, mock_client: MagicMock) -> None:
        folder = Folder.from_api(folder_data, mock_client)

        assert folder.folder_id == 5001
        assert folder.title == "Tech"
        assert folder.slug == "tech"
        assert folder.display_title == "Tech"
        assert folder.sync_to_mobile is True
        assert folder.position == 0

    def test_from_api_sync_disabled(self, folder_data: dict, mock_client: MagicMock) -> None:
        folder_data["sync_to_mobile"] = "0"
        folder = Folder.from_api(folder_data, mock_client)
        assert folder.sync_to_mobile is False

    def test_delete(self, folder_data: dict, mock_client: MagicMock) -> None:
        mock_client._request.return_value = {}
        folder = Folder.from_api(folder_data, mock_client)

        folder.delete()

        mock_client._request.assert_called_once_with("folders/delete", folder_id=5001)


class TestHighlight:
    """Tests for Highlight model."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def highlight_data(self) -> dict:
        return {
            "highlight_id": 9001,
            "text": "This is highlighted",
            "position": 100,
            "time": 1700002000,
            "bookmark_id": 100001,
        }

    def test_from_api(self, highlight_data: dict, mock_client: MagicMock) -> None:
        highlight = Highlight.from_api(highlight_data, mock_client)

        assert highlight.highlight_id == 9001
        assert highlight.text == "This is highlighted"
        assert highlight.position == 100
        assert highlight.time == 1700002000
        assert highlight.bookmark_id == 100001

    def test_delete(self, highlight_data: dict, mock_client: MagicMock) -> None:
        mock_client._request.return_value = {}
        highlight = Highlight.from_api(highlight_data, mock_client)

        highlight.delete()

        mock_client._request.assert_called_once_with("highlights/9001/delete")


class TestHtmlToText:
    """Tests for HTML to text conversion."""

    def test_simple_html(self) -> None:
        html = "<p>Hello World</p>"
        text = html_to_text(html)
        assert text == "Hello World"

    def test_paragraphs(self) -> None:
        html = "<p>First paragraph</p><p>Second paragraph</p>"
        text = html_to_text(html)
        assert text is not None
        assert "First paragraph" in text
        assert "Second paragraph" in text

    def test_line_breaks(self) -> None:
        html = "Line one<br>Line two"
        text = html_to_text(html)
        assert text is not None
        assert "Line one" in text
        assert "Line two" in text

    def test_whitespace_normalization(self) -> None:
        html = "<p>Too    many   spaces</p>"
        text = html_to_text(html)
        assert text is not None
        assert "Too many spaces" in text

    def test_none_input(self) -> None:
        assert html_to_text(None) is None

    def test_empty_input(self) -> None:
        assert html_to_text("") is None
