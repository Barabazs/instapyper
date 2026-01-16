"""Data models for the Instapaper API."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from functools import cached_property
from html.parser import HTMLParser
from re import sub
from typing import TYPE_CHECKING, Any, Protocol

from typing_extensions import Self

if TYPE_CHECKING:
    from collections.abc import Awaitable


class _DeHTMLParser(HTMLParser):
    """Parser to convert HTML to plain text."""

    def __init__(self) -> None:
        super().__init__()
        self._text: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            text = sub(r"[ \t\r\n]+", " ", text)
            self._text.append(text + " ")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p":
            self._text.append("\n\n")
        elif tag == "br":
            self._text.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self._text.append("\n\n")

    def get_text(self) -> str:
        return "".join(self._text).strip()


def html_to_text(html: str | None) -> str | None:
    """Convert HTML to plain text."""
    if not html:
        return None
    parser = _DeHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.get_text()


class InstapaperClientProtocol(Protocol):
    """Protocol for Instapaper client methods used by models."""

    def _request(self, endpoint: str, **params: Any) -> dict[str, Any]: ...
    def _get_bookmark_text(self, bookmark_id: int) -> str: ...


class AsyncInstapaperClientProtocol(Protocol):
    """Protocol for async Instapaper client methods used by models."""

    def _request(self, endpoint: str, **params: Any) -> Awaitable[dict[str, Any]]: ...
    def _get_bookmark_text(self, bookmark_id: int) -> Awaitable[str]: ...


@dataclass
class User:
    """Instapaper user account."""

    user_id: int
    username: str
    subscription_is_active: bool

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Self:
        """Create User from API response."""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            subscription_is_active=data.get("subscription_is_active", "0") == "1",
        )


@dataclass
class HighlightBase:
    """Base data for a text highlight within a bookmark."""

    highlight_id: int
    text: str
    position: int
    time: int
    bookmark_id: int


@dataclass
class Highlight(HighlightBase):
    """A text highlight within a bookmark (sync client)."""

    _client: InstapaperClientProtocol = field(repr=False)

    @classmethod
    def from_api(cls, data: dict[str, Any], client: InstapaperClientProtocol) -> Self:
        """Create Highlight from API response."""
        return cls(
            highlight_id=data["highlight_id"],
            text=data["text"],
            position=data.get("position", 0),
            time=data.get("time", 0),
            bookmark_id=data["bookmark_id"],
            _client=client,
        )

    def delete(self) -> None:
        """Delete this highlight."""
        self._client._request(f"highlights/{self.highlight_id}/delete")


@dataclass
class FolderBase:
    """Base data for an Instapaper folder."""

    folder_id: int
    title: str
    slug: str
    display_title: str
    sync_to_mobile: bool
    position: int


@dataclass
class Folder(FolderBase):
    """An Instapaper folder (sync client)."""

    _client: InstapaperClientProtocol = field(repr=False)

    @classmethod
    def from_api(cls, data: dict[str, Any], client: InstapaperClientProtocol) -> Self:
        """Create Folder from API response."""
        return cls(
            folder_id=data["folder_id"],
            title=data["title"],
            slug=data.get("slug", ""),
            display_title=data.get("display_title", data["title"]),
            sync_to_mobile=data.get("sync_to_mobile", "1") == "1",
            position=data.get("position", 0),
            _client=client,
        )

    def delete(self) -> None:
        """Delete this folder."""
        self._client._request("folders/delete", folder_id=self.folder_id)


@dataclass
class BookmarkBase:
    """Base data for an Instapaper bookmark."""

    bookmark_id: int
    url: str
    title: str
    description: str
    time: int
    progress: float
    progress_timestamp: int
    starred: bool
    hash: str
    private_source: str


@dataclass
class Bookmark(BookmarkBase):
    """An Instapaper bookmark (sync client)."""

    _client: InstapaperClientProtocol = field(repr=False)
    _html: str | None = field(default=None, repr=False)

    @classmethod
    def from_api(cls, data: dict[str, Any], client: InstapaperClientProtocol) -> Self:
        """Create Bookmark from API response."""
        return cls(
            bookmark_id=data["bookmark_id"],
            url=data["url"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            time=data.get("time", 0),
            progress=float(data.get("progress", 0)),
            progress_timestamp=data.get("progress_timestamp", 0),
            starred=data.get("starred", "0") == "1",
            hash=data.get("hash", ""),
            private_source=data.get("private_source", ""),
            _client=client,
        )

    @cached_property
    def html(self) -> str:
        """Get the processed HTML content of the bookmark (lazy loaded)."""
        if self._html is None:
            self._html = self._client._get_bookmark_text(self.bookmark_id)
        return self._html or ""

    @cached_property
    def text(self) -> str:
        """Get the plain text content of the bookmark (lazy loaded)."""
        return html_to_text(self.html) or ""

    def star(self) -> Self:
        """Star this bookmark."""
        data = self._client._request("bookmarks/star", bookmark_id=self.bookmark_id)
        for item in data.get("items", []):
            if isinstance(item, dict) and item.get("type") == "bookmark":
                return type(self).from_api(item, self._client)
        self.starred = True
        return self

    def unstar(self) -> Self:
        """Unstar this bookmark."""
        data = self._client._request("bookmarks/unstar", bookmark_id=self.bookmark_id)
        for item in data.get("items", []):
            if isinstance(item, dict) and item.get("type") == "bookmark":
                return type(self).from_api(item, self._client)
        self.starred = False
        return self

    def archive(self) -> Self:
        """Archive this bookmark."""
        data = self._client._request("bookmarks/archive", bookmark_id=self.bookmark_id)
        for item in data.get("items", []):
            if isinstance(item, dict) and item.get("type") == "bookmark":
                return type(self).from_api(item, self._client)
        return self

    def unarchive(self) -> Self:
        """Unarchive this bookmark."""
        data = self._client._request("bookmarks/unarchive", bookmark_id=self.bookmark_id)
        for item in data.get("items", []):
            if isinstance(item, dict) and item.get("type") == "bookmark":
                return type(self).from_api(item, self._client)
        return self

    def move(self, folder_id: int) -> Self:
        """Move this bookmark to a different folder."""
        data = self._client._request(
            "bookmarks/move", bookmark_id=self.bookmark_id, folder_id=folder_id
        )
        for item in data.get("items", []):
            if isinstance(item, dict) and item.get("type") == "bookmark":
                return type(self).from_api(item, self._client)
        return self

    def delete(self) -> None:
        """Delete this bookmark."""
        self._client._request("bookmarks/delete", bookmark_id=self.bookmark_id)

    def update_progress(self, progress: float) -> Self:
        """Update reading progress (0.0 to 1.0)."""
        if not 0.0 <= progress <= 1.0:
            raise ValueError("Progress must be between 0.0 and 1.0")
        data = self._client._request(
            "bookmarks/update_read_progress",
            bookmark_id=self.bookmark_id,
            progress=progress,
            progress_timestamp=int(time.time()),
        )
        for item in data.get("items", []):
            if isinstance(item, dict) and item.get("type") == "bookmark":
                return type(self).from_api(item, self._client)
        self.progress = progress
        self.progress_timestamp = int(time.time())
        return self

    def get_highlights(self) -> list[Highlight]:
        """Get all highlights for this bookmark."""
        data = self._client._request(f"bookmarks/{self.bookmark_id}/highlights")
        items = data.get("items", [])
        return [Highlight.from_api(h, self._client) for h in items if h.get("type") == "highlight"]

    def create_highlight(self, text: str, position: int = 0) -> Highlight:
        """Create a new highlight in this bookmark."""
        data = self._client._request(
            f"bookmarks/{self.bookmark_id}/highlight", text=text, position=position
        )
        items = data.get("items", [])
        highlights = [h for h in items if h.get("type") == "highlight"]
        if highlights:
            return Highlight.from_api(highlights[0], self._client)
        raise ValueError("Failed to create highlight")
