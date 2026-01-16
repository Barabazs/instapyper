"""Exception hierarchy for the Instapaper API client."""

from __future__ import annotations


class InstapaperError(Exception):
    """Base exception for all Instapaper errors."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class AuthenticationError(InstapaperError):
    """Raised when authentication fails (invalid credentials or tokens)."""


class RateLimitError(InstapaperError):
    """Raised when API rate limit is exceeded."""


class NotFoundError(InstapaperError):
    """Raised when a requested resource (bookmark, folder, etc.) is not found."""


class InvalidRequestError(InstapaperError):
    """Raised when the API request is malformed or missing required parameters."""


class ServerError(InstapaperError):
    """Raised when the Instapaper server returns a 5xx error."""
