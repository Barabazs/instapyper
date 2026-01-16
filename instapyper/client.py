"""Synchronous Instapaper API client using requests-oauthlib."""

from __future__ import annotations

from typing import Any

from requests_oauthlib import OAuth1Session

from .exceptions import (
    AuthenticationError,
    InstapaperError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from .models import Bookmark, Folder, User

BASE_URL = "https://www.instapaper.com"
API_VERSION = "api/1.1"


class Instapaper:
    """Synchronous client for the Instapaper Full API."""

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
        self._session: OAuth1Session | None = None
        self._oauth_token: str | None = None
        self._oauth_token_secret: str | None = None

    def login(self, username: str, password: str) -> User:
        """Authenticate with username and password using xAuth.

        Args:
            username: Instapaper account email or username.
            password: Instapaper account password.

        Returns:
            The authenticated User object.

        Raises:
            AuthenticationError: If credentials are invalid.
        """
        session = OAuth1Session(self._consumer_key, client_secret=self._consumer_secret)

        response = session.post(
            f"{BASE_URL}/{API_VERSION}/oauth/access_token",
            data={
                "x_auth_mode": "client_auth",
                "x_auth_username": username,
                "x_auth_password": password,
            },
            timeout=self._timeout,
        )

        if response.status_code in (401, 403):
            raise AuthenticationError("Invalid username or password")

        if response.status_code != 200:
            raise AuthenticationError(f"Authentication failed: {response.text}")

        # Parse OAuth tokens from response
        tokens = dict(pair.split("=") for pair in response.text.split("&"))
        self._oauth_token = tokens["oauth_token"]
        self._oauth_token_secret = tokens["oauth_token_secret"]

        self._session = OAuth1Session(
            self._consumer_key,
            client_secret=self._consumer_secret,
            resource_owner_key=self._oauth_token,
            resource_owner_secret=self._oauth_token_secret,
        )

        return self.get_user()

    def login_with_token(self, oauth_token: str, oauth_token_secret: str) -> None:
        """Authenticate using existing OAuth tokens.

        Args:
            oauth_token: Previously obtained OAuth token.
            oauth_token_secret: Previously obtained OAuth token secret.
        """
        self._oauth_token = oauth_token
        self._oauth_token_secret = oauth_token_secret
        self._session = OAuth1Session(
            self._consumer_key,
            client_secret=self._consumer_secret,
            resource_owner_key=oauth_token,
            resource_owner_secret=oauth_token_secret,
        )

    @property
    def oauth_token(self) -> str | None:
        """Get the current OAuth token (for storing/reusing)."""
        return self._oauth_token

    @property
    def oauth_token_secret(self) -> str | None:
        """Get the current OAuth token secret (for storing/reusing)."""
        return self._oauth_token_secret

    def _ensure_session(self) -> OAuth1Session:
        """Ensure we have an authenticated session."""
        if self._session is None:
            raise AuthenticationError("Not logged in. Call login() or login_with_token() first.")
        return self._session

    def _request(self, endpoint: str, **params: Any) -> dict[str, Any]:
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
            InvalidRequestError: If the request is malformed.
            ServerError: If the server returns a 5xx error.
            InstapaperError: For other API errors.
        """
        session = self._ensure_session()
        url = f"{BASE_URL}/{API_VERSION}/{endpoint}"

        response = session.post(url, data=params if params else None, timeout=self._timeout)

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
            # Return as dict with list
            return {"items": data}

        if isinstance(data, dict) and data.get("type") == "error":
            error_code = data.get("error_code", 0)
            message = data.get("message", "Unknown error")
            raise InstapaperError(message, code=error_code)

        return data if isinstance(data, dict) else {"items": data}

    def _get_bookmark_text(self, bookmark_id: int) -> str:
        """Get the HTML content of a bookmark."""
        session = self._ensure_session()
        url = f"{BASE_URL}/{API_VERSION}/bookmarks/get_text"
        response = session.post(url, data={"bookmark_id": bookmark_id}, timeout=self._timeout)

        if response.status_code != 200:
            return ""

        return response.text

    # Account methods

    def get_user(self) -> User:
        """Get the authenticated user's account info."""
        data = self._request("account/verify_credentials")
        items = data.get("items", [data])
        for item in items:
            if isinstance(item, dict) and item.get("type") == "user":
                return User.from_api(item)
        raise InstapaperError("Failed to get user info")

    # Bookmark methods

    def get_bookmarks(
        self,
        folder: str | int = "unread",
        limit: int = 25,
        have: str = "",
        highlights: str = "",
        tag: str = "",
    ) -> list[Bookmark]:
        """Get bookmarks from a folder.

        Args:
            folder: Folder ID or special name ('unread', 'starred', 'archive').
            limit: Maximum number of bookmarks to return (1-500).
            have: Comma-separated list of bookmark_id:hash pairs for de-duplication.
            highlights: Dash-delimited list of highlight IDs already cached.
            tag: Filter bookmarks by tag name.

        Returns:
            List of Bookmark objects.
        """
        params: dict[str, Any] = {"folder_id": folder, "limit": min(max(1, limit), 500)}
        if have:
            params["have"] = have
        if highlights:
            params["highlights"] = highlights
        if tag:
            params["tag"] = tag

        data = self._request("bookmarks/list", **params)
        bookmarks = data.get("bookmarks", [])
        return [Bookmark.from_api(b, self) for b in bookmarks]

    def add_bookmark(
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
    ) -> Bookmark:
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
            The created Bookmark object.
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

        data = self._request("bookmarks/add", **params)
        items = data.get("items", [])
        for item in items:
            if isinstance(item, dict) and item.get("type") == "bookmark":
                return Bookmark.from_api(item, self)
        raise InstapaperError("Failed to create bookmark")

    def delete_bookmark(self, bookmark_id: int) -> None:
        """Delete a bookmark by ID."""
        self._request("bookmarks/delete", bookmark_id=bookmark_id)

    # Folder methods

    def get_folders(self) -> list[Folder]:
        """Get all folders."""
        data = self._request("folders/list")
        items = data.get("items", [])
        return [Folder.from_api(f, self) for f in items if f.get("type") == "folder"]

    def create_folder(self, title: str) -> Folder:
        """Create a new folder.

        Args:
            title: Name for the new folder.

        Returns:
            The created Folder object.
        """
        data = self._request("folders/add", title=title)
        items = data.get("items", [data])
        for item in items:
            if isinstance(item, dict) and item.get("type") == "folder":
                return Folder.from_api(item, self)
        raise InstapaperError("Failed to create folder")

    def delete_folder(self, folder_id: int) -> None:
        """Delete a folder by ID."""
        self._request("folders/delete", folder_id=folder_id)

    def set_folder_order(self, order: dict[int, int]) -> None:
        """Set the display order of folders.

        Args:
            order: Dict mapping folder_id to position (0-indexed).
        """
        order_str = ",".join(f"{fid}:{pos}" for fid, pos in order.items())
        self._request("folders/set_order", order=order_str)
