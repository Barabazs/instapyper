"""Asynchronous Instapaper API client using httpx and authlib."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from authlib.integrations.httpx_client import AsyncOAuth1Client
from typing_extensions import Self

from .exceptions import (
    AuthenticationError,
    InstapaperError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from .models import (
    AsyncInstapaperClientProtocol,
    BookmarkBase,
    FolderBase,
    HighlightBase,
    User,
    html_to_text,
)

BASE_URL = "https://www.instapaper.com"
API_VERSION = "api/1.1"


@dataclass
class AsyncHighlight(HighlightBase):
    """A text highlight within a bookmark (async client)."""

    _client: AsyncInstapaperClientProtocol = field(repr=False)

    @classmethod
    def from_api(cls, data: dict[str, Any], client: AsyncInstapaperClientProtocol) -> Self:
        """Create AsyncHighlight from API response."""
        return cls(
            highlight_id=data["highlight_id"],
            text=data["text"],
            position=data.get("position", 0),
            time=data.get("time", 0),
            bookmark_id=data["bookmark_id"],
            _client=client,
        )

    async def delete(self) -> None:
        """Delete this highlight."""
        await self._client._request(f"highlights/{self.highlight_id}/delete")


@dataclass
class AsyncFolder(FolderBase):
    """An Instapaper folder (async client)."""

    _client: AsyncInstapaperClientProtocol = field(repr=False)

    @classmethod
    def from_api(cls, data: dict[str, Any], client: AsyncInstapaperClientProtocol) -> Self:
        """Create AsyncFolder from API response."""
        return cls(
            folder_id=data["folder_id"],
            title=data["title"],
            slug=data.get("slug", ""),
            display_title=data.get("display_title", data["title"]),
            sync_to_mobile=data.get("sync_to_mobile", "1") == "1",
            position=data.get("position", 0),
            _client=client,
        )

    async def delete(self) -> None:
        """Delete this folder."""
        await self._client._request("folders/delete", folder_id=self.folder_id)


@dataclass
class AsyncBookmark(BookmarkBase):
    """An Instapaper bookmark (async client)."""

    _client: AsyncInstapaperClientProtocol = field(repr=False)
    _html: str | None = field(default=None, repr=False)

    @classmethod
    def from_api(cls, data: dict[str, Any], client: AsyncInstapaperClientProtocol) -> Self:
        """Create AsyncBookmark from API response."""
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

    async def star(self) -> Self:
        """Star this bookmark."""
        data = await self._client._request("bookmarks/star", bookmark_id=self.bookmark_id)
        bookmarks = data.get("bookmarks", [])
        if bookmarks:
            return type(self).from_api(bookmarks[0], self._client)
        self.starred = True
        return self

    async def unstar(self) -> Self:
        """Unstar this bookmark."""
        data = await self._client._request("bookmarks/unstar", bookmark_id=self.bookmark_id)
        bookmarks = data.get("bookmarks", [])
        if bookmarks:
            return type(self).from_api(bookmarks[0], self._client)
        self.starred = False
        return self

    async def archive(self) -> Self:
        """Archive this bookmark."""
        data = await self._client._request("bookmarks/archive", bookmark_id=self.bookmark_id)
        bookmarks = data.get("bookmarks", [])
        if bookmarks:
            return type(self).from_api(bookmarks[0], self._client)
        return self

    async def unarchive(self) -> Self:
        """Unarchive this bookmark."""
        data = await self._client._request("bookmarks/unarchive", bookmark_id=self.bookmark_id)
        bookmarks = data.get("bookmarks", [])
        if bookmarks:
            return type(self).from_api(bookmarks[0], self._client)
        return self

    async def move(self, folder_id: int) -> Self:
        """Move this bookmark to a different folder."""
        data = await self._client._request(
            "bookmarks/move", bookmark_id=self.bookmark_id, folder_id=folder_id
        )
        bookmarks = data.get("bookmarks", [])
        if bookmarks:
            return type(self).from_api(bookmarks[0], self._client)
        return self

    async def delete(self) -> None:
        """Delete this bookmark."""
        await self._client._request("bookmarks/delete", bookmark_id=self.bookmark_id)

    async def get_html(self) -> str:
        """Get the processed HTML content of the bookmark."""
        if self._html is None:
            self._html = await self._client._get_bookmark_text(self.bookmark_id)
        return self._html or ""

    async def get_text(self) -> str:
        """Get the plain text content of the bookmark."""
        html = await self.get_html()
        return html_to_text(html) or ""

    async def get_highlights(self) -> list[AsyncHighlight]:
        """Get all highlights for this bookmark."""
        data = await self._client._request(f"bookmarks/{self.bookmark_id}/highlights")
        items = data.get("items", [])
        return [
            AsyncHighlight.from_api(h, self._client) for h in items if h.get("type") == "highlight"
        ]

    async def create_highlight(self, text: str, position: int = 0) -> AsyncHighlight:
        """Create a new highlight in this bookmark."""
        data = await self._client._request(
            f"bookmarks/{self.bookmark_id}/highlight", text=text, position=position
        )
        items = data.get("items", [])
        highlights = [h for h in items if h.get("type") == "highlight"]
        if highlights:
            return AsyncHighlight.from_api(highlights[0], self._client)
        raise ValueError("Failed to create highlight")


class AsyncInstapaper:
    """Asynchronous client for the Instapaper Full API."""

    def __init__(self, consumer_key: str, consumer_secret: str, timeout: int = 30) -> None:
        """Initialize the client with OAuth consumer credentials.

        Args:
            consumer_key: Your Instapaper OAuth consumer key.
            consumer_secret: Your Instapaper OAuth consumer secret.
            timeout: Network timeout in seconds (default 30).
        """
        if not consumer_key or not consumer_secret:
            raise AuthenticationError("Consumer key and secret are required")

        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._timeout = timeout
        self._client: AsyncOAuth1Client | None = None
        self._oauth_token: str | None = None
        self._oauth_token_secret: str | None = None

    async def login(self, username: str, password: str) -> User:
        """Authenticate with username and password using xAuth.

        Args:
            username: Instapaper account email or username.
            password: Instapaper account password.

        Returns:
            The authenticated User object.

        Raises:
            AuthenticationError: If credentials are invalid.
        """
        async with AsyncOAuth1Client(
            client_id=self._consumer_key, client_secret=self._consumer_secret, timeout=self._timeout
        ) as client:
            response = await client.post(
                f"{BASE_URL}/{API_VERSION}/oauth/access_token",
                data={
                    "x_auth_mode": "client_auth",
                    "x_auth_username": username,
                    "x_auth_password": password,
                },
            )

        if response.status_code in (401, 403):
            raise AuthenticationError("Invalid username or password")

        if response.status_code != 200:
            raise AuthenticationError(f"Authentication failed: {response.text}")

        # Parse OAuth tokens from response
        tokens = dict(pair.split("=") for pair in response.text.split("&"))
        self._oauth_token = tokens["oauth_token"]
        self._oauth_token_secret = tokens["oauth_token_secret"]

        self._client = AsyncOAuth1Client(
            client_id=self._consumer_key,
            client_secret=self._consumer_secret,
            token=self._oauth_token,
            token_secret=self._oauth_token_secret,
            timeout=self._timeout,
        )

        return await self.get_user()

    def login_with_token(self, oauth_token: str, oauth_token_secret: str) -> None:
        """Authenticate using existing OAuth tokens.

        Args:
            oauth_token: Previously obtained OAuth token.
            oauth_token_secret: Previously obtained OAuth token secret.
        """
        self._oauth_token = oauth_token
        self._oauth_token_secret = oauth_token_secret
        self._client = AsyncOAuth1Client(
            client_id=self._consumer_key,
            client_secret=self._consumer_secret,
            token=oauth_token,
            token_secret=oauth_token_secret,
            timeout=self._timeout,
        )

    @property
    def oauth_token(self) -> str | None:
        """Get the current OAuth token (for storing/reusing)."""
        return self._oauth_token

    @property
    def oauth_token_secret(self) -> str | None:
        """Get the current OAuth token secret (for storing/reusing)."""
        return self._oauth_token_secret

    def _ensure_client(self) -> AsyncOAuth1Client:
        """Ensure we have an authenticated client."""
        if self._client is None:
            raise AuthenticationError("Not logged in. Call login() or login_with_token() first.")
        return self._client

    async def _request(self, endpoint: str, **params: Any) -> dict[str, Any]:
        """Make an authenticated API request.

        Args:
            endpoint: API endpoint path (without base URL or version).
            **params: Parameters to send with the request.

        Returns:
            Parsed JSON response as a dictionary.

        Raises:
            AuthenticationError: If not authenticated or token is invalid.
            RateLimitError: If rate limit is exceeded.
            NotFoundError: If the resource is not found.
            ServerError: If the server returns a 5xx error.
            InstapaperError: For other API errors.
        """
        client = self._ensure_client()
        url = f"{BASE_URL}/{API_VERSION}/{endpoint}"

        response = await client.post(url, data=params if params else None)

        # Handle HTTP errors
        if response.status_code == 401:
            raise AuthenticationError("Invalid or expired OAuth token")
        if response.status_code == 403:
            raise AuthenticationError("Access forbidden")
        if response.status_code == 404:
            raise NotFoundError(f"Resource not found: {endpoint}")
        if response.status_code == 429:
            raise RateLimitError("Rate limit exceeded")
        if response.status_code >= 500:
            raise ServerError(f"Server error: {response.status_code}")

        # Parse response
        if not response.text:
            return {}

        # Some endpoints return plain text (like get_text)
        try:
            data = response.json()
        except ValueError:
            return {"text": response.text}

        # Handle API-level errors
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("type") == "error":
                    error_code = item.get("error_code", 0)
                    message = item.get("message", "Unknown error")
                    if error_code == 1040:
                        raise RateLimitError(message, code=error_code)
                    if error_code == 1041:
                        raise AuthenticationError(message, code=error_code)
                    raise InstapaperError(message, code=error_code)
            return {"items": data}

        if isinstance(data, dict) and data.get("type") == "error":
            error_code = data.get("error_code", 0)
            message = data.get("message", "Unknown error")
            raise InstapaperError(message, code=error_code)

        return data if isinstance(data, dict) else {"items": data}

    async def _get_bookmark_text(self, bookmark_id: int) -> str:
        """Get the HTML content of a bookmark."""
        client = self._ensure_client()
        url = f"{BASE_URL}/{API_VERSION}/bookmarks/get_text"
        response = await client.post(url, data={"bookmark_id": bookmark_id})

        if response.status_code != 200:
            return ""

        return response.text

    # Account methods

    async def get_user(self) -> User:
        """Get the authenticated user's account info."""
        data = await self._request("account/verify_credentials")
        items = data.get("items", [data])
        for item in items:
            if isinstance(item, dict) and item.get("type") == "user":
                return User.from_api(item)
        raise InstapaperError("Failed to get user info")

    # Bookmark methods

    async def get_bookmarks(
        self,
        folder: str | int = "unread",
        limit: int = 25,
        have: str = "",
        highlights: str = "",
        tag: str = "",
    ) -> list[AsyncBookmark]:
        """Get bookmarks from a folder.

        Args:
            folder: Folder ID or special name ('unread', 'starred', 'archive').
            limit: Maximum number of bookmarks to return (1-500).
            have: Comma-separated list of bookmark_id:hash pairs for de-duplication.
            highlights: Dash-delimited list of highlight IDs already cached.
            tag: Filter bookmarks by tag name.

        Returns:
            List of AsyncBookmark objects.
        """
        params: dict[str, Any] = {"folder_id": folder, "limit": min(max(1, limit), 500)}
        if have:
            params["have"] = have
        if highlights:
            params["highlights"] = highlights
        if tag:
            params["tag"] = tag

        data = await self._request("bookmarks/list", **params)
        bookmarks = data.get("bookmarks", [])
        return [AsyncBookmark.from_api(b, self) for b in bookmarks]

    async def add_bookmark(
        self,
        url: str,
        title: str | None = None,
        description: str | None = None,
        folder_id: int | None = None,
        content: str | None = None,
        is_private_from_source: bool = False,
        resolve_final_url: bool = True,
        archived: bool = False,
        tags: list[str] | None = None,
    ) -> AsyncBookmark:
        """Add a new bookmark.

        Args:
            url: URL to bookmark.
            title: Optional title (auto-detected if not provided).
            description: Optional description.
            folder_id: Optional folder ID to save to.
            content: Optional HTML content (for private sources).
            is_private_from_source: Whether the content is from a private source.
            resolve_final_url: Whether to resolve redirects (default True).
            archived: Whether to archive immediately after adding.
            tags: List of tag names to apply.

        Returns:
            The created AsyncBookmark object.
        """
        params: dict[str, Any] = {"url": url}
        if title:
            params["title"] = title
        if description:
            params["description"] = description
        if folder_id:
            params["folder_id"] = folder_id
        if content:
            params["content"] = content
        if is_private_from_source:
            params["is_private_from_source"] = "1"
        if not resolve_final_url:
            params["resolve_final_url"] = "0"
        if archived:
            params["archived"] = "1"
        if tags:
            import json

            params["tags"] = json.dumps([{"name": t} for t in tags])

        data = await self._request("bookmarks/add", **params)
        items = data.get("items", [])
        for item in items:
            if isinstance(item, dict) and item.get("type") == "bookmark":
                return AsyncBookmark.from_api(item, self)
        raise InstapaperError("Failed to create bookmark")

    async def delete_bookmark(self, bookmark_id: int) -> None:
        """Delete a bookmark by ID."""
        await self._request("bookmarks/delete", bookmark_id=bookmark_id)

    # Folder methods

    async def get_folders(self) -> list[AsyncFolder]:
        """Get all folders."""
        data = await self._request("folders/list")
        items = data.get("items", [])
        return [AsyncFolder.from_api(f, self) for f in items if f.get("type") == "folder"]

    async def create_folder(self, title: str) -> AsyncFolder:
        """Create a new folder.

        Args:
            title: Name for the new folder.

        Returns:
            The created AsyncFolder object.
        """
        data = await self._request("folders/add", title=title)
        items = data.get("items", [data])
        for item in items:
            if isinstance(item, dict) and item.get("type") == "folder":
                return AsyncFolder.from_api(item, self)
        raise InstapaperError("Failed to create folder")

    async def delete_folder(self, folder_id: int) -> None:
        """Delete a folder by ID."""
        await self._request("folders/delete", folder_id=folder_id)

    async def set_folder_order(self, order: dict[int, int]) -> None:
        """Set the display order of folders.

        Args:
            order: Dict mapping folder_id to position (0-indexed).
        """
        order_str = ",".join(f"{fid}:{pos}" for fid, pos in order.items())
        await self._request("folders/set_order", order=order_str)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> AsyncInstapaper:
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context manager."""
        await self.close()
