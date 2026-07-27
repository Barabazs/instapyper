"""Modern Python wrapper for the Instapaper Full API.

Usage (sync):
    from instapyper import Instapaper

    client = Instapaper(consumer_key, consumer_secret)
    client.login(username, password)
    bookmarks = client.get_bookmarks(limit=10)

Usage (async):
    from instapyper import AsyncInstapaper

    async with AsyncInstapaper(consumer_key, consumer_secret) as client:
        await client.login(username, password)
        bookmarks = await client.get_bookmarks(limit=10)
"""

from .async_client import AsyncBookmark, AsyncFolder, AsyncHighlight, AsyncInstapaper
from .client import Instapaper
from .exceptions import (
    AuthenticationError,
    InstapaperError,
    InvalidRequestError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from .models import Bookmark, BookmarksResponse, Folder, Highlight, Tag, User

__version__ = "0.0.5"

__all__ = [
    # Sync client
    "Instapaper",
    # Async client
    "AsyncInstapaper",
    "AsyncBookmark",
    "AsyncFolder",
    "AsyncHighlight",
    # Models
    "Bookmark",
    "BookmarksResponse",
    "Folder",
    "Highlight",
    "Tag",
    "User",
    # Exceptions
    "InstapaperError",
    "AuthenticationError",
    "RateLimitError",
    "NotFoundError",
    "InvalidRequestError",
    "ServerError",
]
