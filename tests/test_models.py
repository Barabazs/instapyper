"""Tests for data models."""

from unittest.mock import MagicMock

import pytest

from instapyper import Bookmark, Folder, Highlight, Tag, User
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


class TestTag:
    """Tests for Tag model."""

    def test_from_api_full(self) -> None:
        tag = Tag.from_api(
            {
                "id": 4031606,
                "name": "tech",
                "slug": "tech",
                "time": 1785143426.5,
                "count": 3,
                "hash": "nsRwVT",
            }
        )
        assert tag == Tag(
            name="tech", id=4031606, slug="tech", time=1785143426.5, count=3, hash="nsRwVT"
        )
        assert tag.extra == {}

    def test_from_api_name_only(self) -> None:
        tag = Tag.from_api({"name": "tech"})
        assert tag == Tag(name="tech")
        assert tag.id == 0
        assert tag.slug == ""
        assert tag.time == 0.0
        assert tag.count == 0
        assert tag.hash == ""

    def test_from_api_unknown_fields_land_in_extra(self) -> None:
        tag = Tag.from_api({"name": "tech", "color": "red"})
        assert tag.extra == {"color": "red"}

    def test_from_api_null_numeric_fields(self) -> None:
        tag = Tag.from_api({"name": "tech", "id": None, "time": None, "count": None})
        assert tag.id == 0
        assert tag.time == 0.0
        assert tag.count == 0


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
        assert bookmark.tags == []

    def test_from_api_with_tags(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        bookmark_data["tags"] = [{"name": "tech"}, {"name": "python"}]
        bookmark = Bookmark.from_api(bookmark_data, mock_client)

        assert bookmark.tags == [Tag(name="tech"), Tag(name="python")]

    def test_from_api_with_rich_tags(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        bookmark_data["tags"] = [
            {
                "id": 4031606,
                "name": "tech",
                "slug": "tech",
                "time": 1785143426.5,
                "count": 3,
                "hash": "nsRwVT",
                "color": "red",
            }
        ]
        bookmark = Bookmark.from_api(bookmark_data, mock_client)

        assert bookmark.tags == [
            Tag(
                name="tech",
                id=4031606,
                slug="tech",
                time=1785143426.5,
                count=3,
                hash="nsRwVT",
                extra={"color": "red"},
            )
        ]

    def test_from_api_with_string_tags(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        bookmark_data["tags"] = ["tech", "python"]
        bookmark = Bookmark.from_api(bookmark_data, mock_client)

        assert bookmark.tags == [Tag(name="tech"), Tag(name="python")]

    def test_from_api_empty_tags(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        bookmark_data["tags"] = []
        bookmark = Bookmark.from_api(bookmark_data, mock_client)

        assert bookmark.tags == []

    def test_from_api_null_tags(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        bookmark_data["tags"] = None
        bookmark = Bookmark.from_api(bookmark_data, mock_client)

        assert bookmark.tags == []

    def test_star(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        mock_client._request.return_value = {
            "items": [{**bookmark_data, "type": "bookmark", "starred": "1"}]
        }
        bookmark = Bookmark.from_api({**bookmark_data, "starred": "0"}, mock_client)

        result = bookmark.star()

        mock_client._request.assert_called_once_with("bookmarks/star", bookmark_id=100001)
        assert isinstance(result, Bookmark)
        assert result is not bookmark
        assert result.starred is True

    def test_star_fallback_without_items(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        mock_client._request.return_value = {}
        bookmark = Bookmark.from_api({**bookmark_data, "starred": "0"}, mock_client)

        result = bookmark.star()

        assert result is bookmark
        assert bookmark.starred is True

    def test_delete(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        mock_client._request.return_value = {}
        bookmark = Bookmark.from_api(bookmark_data, mock_client)

        bookmark.delete()

        mock_client._request.assert_called_once_with("bookmarks/delete", bookmark_id=100001)

    def test_move(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        mock_client._request.return_value = {
            "items": [{**bookmark_data, "type": "bookmark", "title": "Moved"}]
        }
        bookmark = Bookmark.from_api(bookmark_data, mock_client)

        result = bookmark.move(5001)

        mock_client._request.assert_called_once_with(
            "bookmarks/move", bookmark_id=100001, folder_id=5001
        )
        assert isinstance(result, Bookmark)
        assert result is not bookmark
        assert result.title == "Moved"

    def test_update_progress(self, bookmark_data: dict, mock_client: MagicMock) -> None:
        mock_client._request.return_value = {
            "items": [{**bookmark_data, "type": "bookmark", "progress": 0.75}]
        }
        bookmark = Bookmark.from_api(bookmark_data, mock_client)

        result = bookmark.update_progress(0.75)

        assert mock_client._request.called
        call_args = mock_client._request.call_args
        assert call_args[0][0] == "bookmarks/update_read_progress"
        assert call_args[1]["bookmark_id"] == 100001
        assert call_args[1]["progress"] == 0.75
        assert isinstance(result, Bookmark)
        assert result is not bookmark
        assert result.progress == 0.75

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
            "sync_to_mobile": 1,
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
        assert folder.count == 0
        assert folder.public is False

    def test_from_api_with_count_and_public(
        self, folder_data: dict, mock_client: MagicMock
    ) -> None:
        folder_data["count"] = 13
        folder_data["public"] = 1
        folder = Folder.from_api(folder_data, mock_client)

        assert folder.count == 13
        assert folder.public is True

    def test_from_api_null_count_and_public(
        self, folder_data: dict, mock_client: MagicMock
    ) -> None:
        folder_data["count"] = None
        folder_data["public"] = None
        folder = Folder.from_api(folder_data, mock_client)

        assert folder.count == 0
        assert folder.public is False

    def test_from_api_sync_disabled(self, folder_data: dict, mock_client: MagicMock) -> None:
        folder_data["sync_to_mobile"] = 0
        folder = Folder.from_api(folder_data, mock_client)
        assert folder.sync_to_mobile is False

    def test_from_api_sync_missing_defaults_enabled(
        self, folder_data: dict, mock_client: MagicMock
    ) -> None:
        del folder_data["sync_to_mobile"]
        folder = Folder.from_api(folder_data, mock_client)
        assert folder.sync_to_mobile is True

    def test_from_api_sync_null(self, folder_data: dict, mock_client: MagicMock) -> None:
        folder_data["sync_to_mobile"] = None
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
        assert highlight.note == ""

    def test_from_api_with_note(self, highlight_data: dict, mock_client: MagicMock) -> None:
        highlight_data["note"] = "My annotation"
        highlight = Highlight.from_api(highlight_data, mock_client)

        assert highlight.note == "My annotation"

    def test_from_api_missing_note(self, highlight_data: dict, mock_client: MagicMock) -> None:
        highlight = Highlight.from_api(highlight_data, mock_client)
        assert highlight.note == ""

    def test_from_api_null_note(self, highlight_data: dict, mock_client: MagicMock) -> None:
        highlight_data["note"] = None
        highlight = Highlight.from_api(highlight_data, mock_client)
        assert highlight.note == ""

    def test_delete(self, highlight_data: dict, mock_client: MagicMock) -> None:
        mock_client._request.return_value = {}
        highlight = Highlight.from_api(highlight_data, mock_client)

        highlight.delete()

        mock_client._request.assert_called_once_with("highlights/9001/delete")


class TestExtraFieldsPassthrough:
    """Tests for extra fields passthrough on all models."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    def test_bookmark_extra_captures_unknown_fields(self, mock_client: MagicMock) -> None:
        data = {
            "bookmark_id": 1,
            "url": "https://example.com",
            "some_future_field": "surprise",
        }
        bookmark = Bookmark.from_api(data, mock_client)
        assert bookmark.extra["some_future_field"] == "surprise"

    def test_bookmark_extra_excludes_tags_field(self, mock_client: MagicMock) -> None:
        """tags is a known field routed to the model, so it never lands in extra."""
        data = {
            "bookmark_id": 1,
            "url": "https://example.com",
            "tags": [{"name": "tech"}],
        }
        bookmark = Bookmark.from_api(data, mock_client)
        assert "tags" not in bookmark.extra

    def test_bookmark_extra_excludes_known_fields(self, mock_client: MagicMock) -> None:
        data = {
            "bookmark_id": 1,
            "url": "https://example.com",
            "title": "Test",
        }
        bookmark = Bookmark.from_api(data, mock_client)
        assert "bookmark_id" not in bookmark.extra
        assert "url" not in bookmark.extra
        assert "title" not in bookmark.extra

    def test_highlight_extra_excludes_note_field(self, mock_client: MagicMock) -> None:
        """note is a known field routed to the model, so it never lands in extra."""
        data = {
            "highlight_id": 1,
            "text": "highlighted",
            "bookmark_id": 100,
            "note": "my annotation",
        }
        highlight = Highlight.from_api(data, mock_client)
        assert "note" not in highlight.extra

    def test_folder_extra_captures_unknown_fields(self, mock_client: MagicMock) -> None:
        data = {
            "folder_id": 1,
            "title": "Test",
            "some_future_field": "surprise",
        }
        folder = Folder.from_api(data, mock_client)
        assert folder.extra["some_future_field"] == "surprise"

    def test_folder_extra_excludes_count_and_public(self, mock_client: MagicMock) -> None:
        """count/public are known fields routed to the model, never landing in extra."""
        data = {
            "folder_id": 1,
            "title": "Test",
            "count": 42,
            "public": 0,
        }
        folder = Folder.from_api(data, mock_client)
        assert "count" not in folder.extra
        assert "public" not in folder.extra

    def test_empty_extra_when_no_unknown_fields(self, mock_client: MagicMock) -> None:
        data = {
            "highlight_id": 1,
            "text": "highlighted",
            "bookmark_id": 100,
            "type": "highlight",
        }
        highlight = Highlight.from_api(data, mock_client)
        assert highlight.extra == {}


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
