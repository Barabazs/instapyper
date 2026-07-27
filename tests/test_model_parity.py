"""Sync/async model parity tests.

The sync models (models.py) and their async twins (async_client.py) duplicate
their ``from_api`` parsing and method logic. These tests run identical API
payloads through both sides of each pair so any drift between the two
implementations fails loudly instead of passing CI silently.

Payload field types mirror what the live API actually returns (verified
2026-07-27): bookmark booleans are strings ("0"/"1"), folder booleans are
native ints, and tags arrive as rich dicts.
"""

import dataclasses
import inspect
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

from instapyper import (
    AsyncBookmark,
    AsyncFolder,
    AsyncHighlight,
    Bookmark,
    Folder,
    Highlight,
)
from instapyper.models import BookmarkBase, FolderBase, HighlightBase

FULL_HIGHLIGHT = {
    "type": "highlight",
    "highlight_id": 9001,
    "text": "Highlighted text",
    "position": 100,
    "time": 1785142000,
    "bookmark_id": 100001,
    "note": "My annotation",
}

FULL_FOLDER = {
    "type": "folder",
    "folder_id": 5001,
    "title": "Tech",
    "slug": "tech",
    "display_title": "Tech",
    "sync_to_mobile": 1,
    "position": 1785143639,
    "count": 13,
    "public": 1,
}

FULL_BOOKMARK = {
    "type": "bookmark",
    "bookmark_id": 100001,
    "url": "https://example.com/article",
    "title": "Example Article",
    "description": "A description",
    "time": 1785143426,
    "progress": 0.5,
    "progress_timestamp": 1785143500,
    "starred": "1",
    "hash": "0zQk353o",
    "private_source": "",
    "tags": [
        {"id": 4031606, "name": "tech", "slug": "tech", "count": 1, "hash": "nsRwVT"},
    ],
}

PAYLOAD_VARIANTS = {
    "highlight": {
        "full": FULL_HIGHLIGHT,
        "minimal": {"highlight_id": 9001, "text": "t", "bookmark_id": 100001},
        "nulls": {"highlight_id": 9001, "text": "t", "bookmark_id": 100001, "note": None},
    },
    "folder": {
        "full": FULL_FOLDER,
        "minimal": {"folder_id": 5001, "title": "Tech"},
        "nulls": {
            "folder_id": 5001,
            "title": "Tech",
            "sync_to_mobile": None,
            "count": None,
            "public": None,
        },
    },
    "bookmark": {
        "full": FULL_BOOKMARK,
        "minimal": {"bookmark_id": 100001, "url": "https://example.com/article"},
        "nulls": {"bookmark_id": 100001, "url": "https://example.com/article", "tags": None},
    },
}

MODEL_PAIRS = {
    "highlight": (Highlight, AsyncHighlight, HighlightBase),
    "folder": (Folder, AsyncFolder, FolderBase),
    "bookmark": (Bookmark, AsyncBookmark, BookmarkBase),
}

ASYNC_MODELS = (AsyncHighlight, AsyncFolder, AsyncBookmark)

HIGHLIGHT_CLASSES = [pytest.param(Highlight, id="sync"), pytest.param(AsyncHighlight, id="async")]
FOLDER_CLASSES = [pytest.param(Folder, id="sync"), pytest.param(AsyncFolder, id="async")]
BOOKMARK_CLASSES = [pytest.param(Bookmark, id="sync"), pytest.param(AsyncBookmark, id="async")]


def _client_for(cls) -> MagicMock:
    client = MagicMock()
    if cls in ASYNC_MODELS:
        client._request = AsyncMock()
        client._get_bookmark_text = AsyncMock()
    return client


async def _invoke(bound_method, *args, **kwargs):
    result = bound_method(*args, **kwargs)
    if inspect.isawaitable(result):
        result = await result
    return result


class TestFromApiParity:
    """The sync and async twins must parse identical payloads identically."""

    @pytest.mark.parametrize("kind", MODEL_PAIRS)
    @pytest.mark.parametrize("variant", ["full", "minimal", "nulls"])
    def test_same_payload_same_fields(self, kind: str, variant: str) -> None:
        sync_cls, async_cls, base_cls = MODEL_PAIRS[kind]
        payload = PAYLOAD_VARIANTS[kind][variant]

        sync_obj = sync_cls.from_api(dict(payload), MagicMock())
        async_obj = async_cls.from_api(dict(payload), MagicMock())

        for field in dataclasses.fields(base_cls):
            assert getattr(sync_obj, field.name) == getattr(async_obj, field.name), field.name


class TestKnownKeys:
    """_KNOWN_KEYS must track the base dataclass fields on both sides.

    Every base field except the extra bucket itself, plus the API's "type"
    discriminator. A new field added to a base class without updating both
    _KNOWN_KEYS sets (or vice versa) fails here.
    """

    @pytest.mark.parametrize(
        ("cls", "base_cls"),
        [
            pytest.param(Highlight, HighlightBase, id="highlight-sync"),
            pytest.param(AsyncHighlight, HighlightBase, id="highlight-async"),
            pytest.param(Folder, FolderBase, id="folder-sync"),
            pytest.param(AsyncFolder, FolderBase, id="folder-async"),
            pytest.param(Bookmark, BookmarkBase, id="bookmark-sync"),
            pytest.param(AsyncBookmark, BookmarkBase, id="bookmark-async"),
        ],
    )
    def test_known_keys_track_base_fields(self, cls, base_cls) -> None:
        expected = {f.name for f in dataclasses.fields(base_cls)} - {"extra"} | {"type"}
        assert expected == cls._KNOWN_KEYS


class TestHighlightBehavior:
    """Parsing and methods, run against both Highlight and AsyncHighlight."""

    @pytest.mark.parametrize("cls", HIGHLIGHT_CLASSES)
    def test_full_payload(self, cls) -> None:
        h = cls.from_api(dict(FULL_HIGHLIGHT), MagicMock())

        assert h.highlight_id == 9001
        assert h.text == "Highlighted text"
        assert h.position == 100
        assert h.time == 1785142000
        assert h.bookmark_id == 100001
        assert h.note == "My annotation"
        assert h.extra == {}

    @pytest.mark.parametrize("cls", HIGHLIGHT_CLASSES)
    def test_minimal_payload_defaults(self, cls) -> None:
        h = cls.from_api(dict(PAYLOAD_VARIANTS["highlight"]["minimal"]), MagicMock())

        assert h.position == 0
        assert h.time == 0
        assert h.note == ""
        assert h.extra == {}

    @pytest.mark.parametrize("cls", HIGHLIGHT_CLASSES)
    def test_null_note(self, cls) -> None:
        h = cls.from_api(dict(PAYLOAD_VARIANTS["highlight"]["nulls"]), MagicMock())
        assert h.note == ""

    @pytest.mark.parametrize("cls", HIGHLIGHT_CLASSES)
    def test_unknown_fields_land_in_extra(self, cls) -> None:
        h = cls.from_api({**FULL_HIGHLIGHT, "future_field": "surprise"}, MagicMock())
        assert h.extra == {"future_field": "surprise"}

    @pytest.mark.parametrize("cls", HIGHLIGHT_CLASSES)
    async def test_delete(self, cls) -> None:
        client = _client_for(cls)
        client._request.return_value = {}
        h = cls.from_api(dict(FULL_HIGHLIGHT), client)

        await _invoke(h.delete)

        client._request.assert_called_once_with("highlights/9001/delete")


class TestFolderBehavior:
    """Parsing and methods, run against both Folder and AsyncFolder."""

    @pytest.mark.parametrize("cls", FOLDER_CLASSES)
    def test_full_payload(self, cls) -> None:
        f = cls.from_api(dict(FULL_FOLDER), MagicMock())

        assert f.folder_id == 5001
        assert f.title == "Tech"
        assert f.slug == "tech"
        assert f.display_title == "Tech"
        assert f.sync_to_mobile is True
        assert f.position == 1785143639
        assert f.count == 13
        assert f.public is True
        assert f.extra == {}

    @pytest.mark.parametrize("cls", FOLDER_CLASSES)
    def test_minimal_payload_defaults(self, cls) -> None:
        f = cls.from_api(dict(PAYLOAD_VARIANTS["folder"]["minimal"]), MagicMock())

        assert f.slug == ""
        assert f.display_title == "Tech"
        assert f.sync_to_mobile is True
        assert f.position == 0
        assert f.count == 0
        assert f.public is False

    @pytest.mark.parametrize("cls", FOLDER_CLASSES)
    def test_null_fields(self, cls) -> None:
        f = cls.from_api(dict(PAYLOAD_VARIANTS["folder"]["nulls"]), MagicMock())

        assert f.sync_to_mobile is False
        assert f.count == 0
        assert f.public is False

    @pytest.mark.parametrize("cls", FOLDER_CLASSES)
    async def test_delete(self, cls) -> None:
        client = _client_for(cls)
        client._request.return_value = {}
        f = cls.from_api(dict(FULL_FOLDER), client)

        await _invoke(f.delete)

        client._request.assert_called_once_with("folders/delete", folder_id=5001)


class TestBookmarkBehavior:
    """Parsing and methods, run against both Bookmark and AsyncBookmark."""

    @pytest.mark.parametrize("cls", BOOKMARK_CLASSES)
    def test_full_payload(self, cls) -> None:
        b = cls.from_api(dict(FULL_BOOKMARK), MagicMock())

        assert b.bookmark_id == 100001
        assert b.url == "https://example.com/article"
        assert b.title == "Example Article"
        assert b.time == 1785143426
        assert b.progress == 0.5
        assert b.progress_timestamp == 1785143500
        assert b.starred is True
        assert b.hash == "0zQk353o"
        assert b.tags == ["tech"]
        assert b.extra == {}

    @pytest.mark.parametrize("cls", BOOKMARK_CLASSES)
    def test_minimal_payload_defaults(self, cls) -> None:
        b = cls.from_api(dict(PAYLOAD_VARIANTS["bookmark"]["minimal"]), MagicMock())

        assert b.title == ""
        assert b.description == ""
        assert b.time == 0
        assert b.progress == 0.0
        assert b.progress_timestamp == 0
        assert b.starred is False
        assert b.hash == ""
        assert b.private_source == ""
        assert b.tags == []
        assert b.extra == {}

    @pytest.mark.parametrize("cls", BOOKMARK_CLASSES)
    def test_null_tags(self, cls) -> None:
        b = cls.from_api(dict(PAYLOAD_VARIANTS["bookmark"]["nulls"]), MagicMock())
        assert b.tags == []

    @pytest.mark.parametrize(
        ("method_name", "endpoint"),
        [
            ("star", "bookmarks/star"),
            ("unstar", "bookmarks/unstar"),
            ("archive", "bookmarks/archive"),
            ("unarchive", "bookmarks/unarchive"),
        ],
    )
    @pytest.mark.parametrize("cls", BOOKMARK_CLASSES)
    async def test_actions_fallback_returns_self(
        self, cls, method_name: str, endpoint: str
    ) -> None:
        client = _client_for(cls)
        client._request.return_value = {}
        b = cls.from_api(dict(FULL_BOOKMARK), client)

        result = await _invoke(getattr(b, method_name))

        assert result is b
        client._request.assert_called_once_with(endpoint, bookmark_id=100001)

    @pytest.mark.parametrize(
        ("method_name", "args"),
        [
            ("star", ()),
            ("unstar", ()),
            ("archive", ()),
            ("unarchive", ()),
            ("move", (42,)),
            ("update_progress", (0.25,)),
        ],
    )
    @pytest.mark.parametrize("cls", BOOKMARK_CLASSES)
    async def test_actions_parse_returned_bookmark(
        self, cls, method_name: str, args: tuple
    ) -> None:
        client = _client_for(cls)
        client._request.return_value = {"items": [{**FULL_BOOKMARK, "title": "Updated"}]}
        b = cls.from_api(dict(FULL_BOOKMARK), client)

        result = await _invoke(getattr(b, method_name), *args)

        assert type(result) is cls
        assert result is not b
        assert result.title == "Updated"

    @pytest.mark.parametrize(
        ("method_name", "expected_flag"),
        [("star", True), ("unstar", False)],
    )
    @pytest.mark.parametrize("cls", BOOKMARK_CLASSES)
    async def test_star_flag_set_on_fallback(
        self, cls, method_name: str, expected_flag: bool
    ) -> None:
        client = _client_for(cls)
        client._request.return_value = {}
        starred = "0" if expected_flag else "1"
        b = cls.from_api({**FULL_BOOKMARK, "starred": starred}, client)

        result = await _invoke(getattr(b, method_name))

        assert result is b
        assert b.starred is expected_flag

    @pytest.mark.parametrize("cls", BOOKMARK_CLASSES)
    async def test_delete(self, cls) -> None:
        client = _client_for(cls)
        client._request.return_value = {}
        b = cls.from_api(dict(FULL_BOOKMARK), client)

        await _invoke(b.delete)

        client._request.assert_called_once_with("bookmarks/delete", bookmark_id=100001)

    @pytest.mark.parametrize("cls", BOOKMARK_CLASSES)
    async def test_move(self, cls) -> None:
        client = _client_for(cls)
        client._request.return_value = {}
        b = cls.from_api(dict(FULL_BOOKMARK), client)

        moved = await _invoke(b.move, 42)

        assert moved is b
        client._request.assert_called_once_with("bookmarks/move", bookmark_id=100001, folder_id=42)

    @pytest.mark.parametrize("cls", BOOKMARK_CLASSES)
    async def test_update_progress_fallback(self, cls) -> None:
        client = _client_for(cls)
        client._request.return_value = {}
        b = cls.from_api(dict(FULL_BOOKMARK), client)

        result = await _invoke(b.update_progress, 0.75)

        client._request.assert_called_once_with(
            "bookmarks/update_read_progress",
            bookmark_id=100001,
            progress=0.75,
            progress_timestamp=ANY,
        )
        sent_ts = client._request.call_args.kwargs["progress_timestamp"]
        assert isinstance(sent_ts, int)
        # unix seconds, not milliseconds or a placeholder
        assert 1_700_000_000 < sent_ts < 10_000_000_000
        assert result is b
        assert b.progress == 0.75
        assert isinstance(b.progress_timestamp, int)
        assert b.progress_timestamp >= sent_ts

    @pytest.mark.parametrize("progress", [0.0, 1.0])
    @pytest.mark.parametrize("cls", BOOKMARK_CLASSES)
    async def test_update_progress_accepts_bounds(self, cls, progress: float) -> None:
        client = _client_for(cls)
        client._request.return_value = {}
        b = cls.from_api(dict(FULL_BOOKMARK), client)

        await _invoke(b.update_progress, progress)

        assert b.progress == progress

    @pytest.mark.parametrize("progress", [-0.1, 1.5])
    @pytest.mark.parametrize("cls", BOOKMARK_CLASSES)
    async def test_update_progress_out_of_range(self, cls, progress: float) -> None:
        b = cls.from_api(dict(FULL_BOOKMARK), _client_for(cls))

        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            await _invoke(b.update_progress, progress)

    @pytest.mark.parametrize("cls", BOOKMARK_CLASSES)
    async def test_get_highlights(self, cls) -> None:
        client = _client_for(cls)
        client._request.return_value = {
            "items": [dict(FULL_HIGHLIGHT), {"type": "user", "user_id": 1}]
        }
        b = cls.from_api(dict(FULL_BOOKMARK), client)

        highlights = await _invoke(b.get_highlights)

        expected_cls = AsyncHighlight if cls is AsyncBookmark else Highlight
        assert len(highlights) == 1
        assert type(highlights[0]) is expected_cls
        assert highlights[0].note == "My annotation"
        client._request.assert_called_once_with("bookmarks/100001/highlights")

    @pytest.mark.parametrize("cls", BOOKMARK_CLASSES)
    async def test_create_highlight(self, cls) -> None:
        client = _client_for(cls)
        client._request.return_value = {"items": [dict(FULL_HIGHLIGHT)]}
        b = cls.from_api(dict(FULL_BOOKMARK), client)

        highlight = await _invoke(b.create_highlight, "Highlighted text", 100)

        expected_cls = AsyncHighlight if cls is AsyncBookmark else Highlight
        assert type(highlight) is expected_cls
        assert highlight.text == "Highlighted text"
        client._request.assert_called_once_with(
            "bookmarks/100001/highlight", text="Highlighted text", position=100
        )

    @pytest.mark.parametrize("cls", BOOKMARK_CLASSES)
    async def test_create_highlight_failure(self, cls) -> None:
        client = _client_for(cls)
        client._request.return_value = {"items": []}
        b = cls.from_api(dict(FULL_BOOKMARK), client)

        with pytest.raises(ValueError, match="Failed to create highlight"):
            await _invoke(b.create_highlight, "text")

    @pytest.mark.parametrize("cls", BOOKMARK_CLASSES)
    async def test_html_and_text(self, cls) -> None:
        client = _client_for(cls)
        client._get_bookmark_text.return_value = "<p>Hello World</p>"
        b = cls.from_api(dict(FULL_BOOKMARK), client)

        if cls is AsyncBookmark:
            html = await b.get_html()
            text = await b.get_text()
        else:
            html = b.html
            text = b.text

        assert html == "<p>Hello World</p>"
        assert text == "Hello World"
        client._get_bookmark_text.assert_called_once_with(100001)
