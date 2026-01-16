"""CLI for Instapaper using typer."""

from __future__ import annotations

import json
import os
import signal
import sys
from pathlib import Path
from typing import Annotated

try:
    import typer
    from rich.console import Console
    from rich.table import Table
except ImportError:
    print(
        "CLI dependencies not installed. Install with:\n  pip install instapyper[cli]",
        file=sys.stderr,
    )
    sys.exit(1)

from . import __version__
from .client import Bookmark, Instapaper
from .exceptions import AuthenticationError, InstapaperError


def _handle_sigint(signum: int, frame: object) -> None:
    """Handle Ctrl-C gracefully."""
    # Print newline to avoid clobbering spinner output
    print()
    raise SystemExit(130)  # Standard exit code for SIGINT


# Register signal handler for clean Ctrl-C handling
signal.signal(signal.SIGINT, _handle_sigint)

# Global state for flags
_no_input: bool = False
_verbose: bool = False
_debug: bool = False
_quiet: bool = False
_no_color: bool = False
_pager: bool = True
_timeout: int = 30
_config_path: Path | None = None


def make_console(stderr: bool = False) -> Console:
    """Create a Console with NO_COLOR/TERM/--no-color detection.

    Disables color when:
    - NO_COLOR env var is set
    - TERM=dumb
    - --no-color flag is set
    - Output is not a TTY
    """
    force_terminal = None
    no_color = os.environ.get("NO_COLOR") is not None or _no_color
    dumb_term = os.environ.get("TERM") == "dumb"
    if no_color or dumb_term:
        force_terminal = False
    return Console(stderr=stderr, force_terminal=force_terminal, no_color=no_color)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"instapyper {__version__}")
        raise typer.Exit()


def get_no_input() -> bool:
    """Check if --no-input mode is active."""
    return _no_input


app = typer.Typer(
    name="instapyper",
    help="CLI for Instapaper - manage your bookmarks from the command line.",
    no_args_is_help=True,
)
bookmarks_app = typer.Typer(help="Manage bookmarks")
folders_app = typer.Typer(help="Manage folders")
highlights_app = typer.Typer(help="Manage highlights")

app.add_typer(bookmarks_app, name="bookmarks")
app.add_typer(folders_app, name="folders")
app.add_typer(highlights_app, name="highlights")


@app.command(
    "completion",
    help="""Generate shell completion script.

Prints a shell completion script to stdout. Redirect to a file or eval directly.

Examples:
  # Bash (add to ~/.bashrc)
  instapyper completion bash >> ~/.bashrc

  # Zsh (add to ~/.zshrc)
  instapyper completion zsh >> ~/.zshrc

  # Fish
  instapyper completion fish > ~/.config/fish/completions/instapyper.fish

  # PowerShell
  instapyper completion powershell >> $PROFILE
""",
)
def completion(
    shell: Annotated[
        str,
        typer.Argument(help="Shell type: bash, zsh, fish, or powershell"),
    ],
) -> None:
    """Generate shell completion script."""
    import subprocess

    shell_lower = shell.lower()
    valid_shells = ["bash", "zsh", "fish", "powershell"]

    if shell_lower not in valid_shells:
        error_with_hint(
            f"Unknown shell: {shell}",
            f"Supported shells: {', '.join(valid_shells)}",
        )
        raise typer.Exit(2) from None

    # Use typer's built-in completion generation
    try:
        result = subprocess.run(
            [sys.executable, "-m", "typer", "instapyper.cli", "utils", "complete", shell_lower],
            capture_output=True,
            text=True,
            check=True,
        )
        print(result.stdout)
    except subprocess.CalledProcessError:
        # Fallback: provide manual instructions
        console.print(f"[yellow]Could not auto-generate completion for {shell}.[/yellow]")
        console.print("\nTo enable completion, run:")
        if shell_lower == "bash":
            console.print('  eval "$(instapyper --install-completion bash)"')
        elif shell_lower == "zsh":
            console.print('  eval "$(instapyper --install-completion zsh)"')
        elif shell_lower == "fish":
            console.print("  instapyper --install-completion fish")
        elif shell_lower == "powershell":
            console.print("  instapyper --install-completion powershell")


console = make_console()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=version_callback, is_eager=True, help="Show version"),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Config file path"),
    ] = None,
    no_input: Annotated[
        bool,
        typer.Option("--no-input", help="Disable interactive prompts, fail if input needed"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Show verbose output"),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", "-d", help="Show debug output (API requests/responses)"),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress non-essential output"),
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable colored output"),
    ] = False,
    no_pager: Annotated[
        bool,
        typer.Option("--no-pager", help="Disable pager for long output"),
    ] = False,
    timeout: Annotated[
        int,
        typer.Option("--timeout", help="Network timeout in seconds"),
    ] = 30,
) -> None:
    """Instapyper - CLI for Instapaper.

    Manage your Instapaper bookmarks from the command line.

    \b
    Environment variables:
      INSTAPAPER_CONSUMER_KEY     API consumer key
      INSTAPAPER_CONSUMER_SECRET  API consumer secret

    \b
    Shell completion: Run 'instapyper completion <shell>' to generate.
    Documentation: https://github.com/Barabazs/instapyper
    Report issues: https://github.com/Barabazs/instapyper/issues
    """
    global \
        _no_input, \
        _verbose, \
        _debug, \
        _quiet, \
        _no_color, \
        _pager, \
        _timeout, \
        _config_path, \
        console, \
        err_console
    _no_input = no_input
    _verbose = verbose
    _debug = debug
    _quiet = quiet
    _no_color = no_color
    _pager = not no_pager
    _timeout = timeout
    _config_path = config
    # Recreate consoles with updated color settings
    if no_color:
        console = make_console()
        err_console = make_console(stderr=True)


err_console = make_console(stderr=True)


def get_verbose() -> bool:
    """Check if --verbose mode is active."""
    return _verbose


def get_debug() -> bool:
    """Check if --debug mode is active."""
    return _debug


def get_quiet() -> bool:
    """Check if --quiet mode is active."""
    return _quiet


def get_timeout() -> int:
    """Get network timeout in seconds."""
    return _timeout


def get_pager() -> bool:
    """Check if pager is enabled."""
    return _pager


def print_with_pager(renderable: object, item_count: int, threshold: int = 25) -> None:
    """Print output, using pager if item count exceeds threshold and output is a TTY.

    Args:
        renderable: Rich renderable object (table, text, etc.)
        item_count: Number of items being displayed (for threshold comparison)
        threshold: Number of items that triggers pager
    """
    if _pager and sys.stdout.isatty() and item_count > threshold:
        with console.pager(styles=True):
            console.print(renderable)
    else:
        console.print(renderable)


def verbose_print(message: str) -> None:
    """Print message only in verbose mode."""
    if _verbose:
        console.print(f"[dim]{message}[/dim]")


def debug_print(message: str) -> None:
    """Print message only in debug mode."""
    if _debug:
        err_console.print(f"DEBUG: {message}")


def quiet_print(message: str) -> None:
    """Print message unless in quiet mode."""
    if not _quiet:
        console.print(message)


def error_with_hint(error: str, hint: str | None = None) -> None:
    """Print an error message with an optional hint."""
    err_console.print(f"[red]{error}[/red]")
    if hint:
        err_console.print(f"Hint: {hint}")


def handle_error(e: InstapaperError, hint: str | None = None) -> None:
    """Handle an InstapaperError, showing stack trace in debug mode."""
    if _debug:
        import traceback

        err_console.print("DEBUG: Stack trace:")
        err_console.print(traceback.format_exc())
    error_with_hint(str(e), hint)


def get_config_path() -> Path:
    """Get the config file path, respecting --config flag and XDG_CONFIG_HOME."""
    if _config_path is not None:
        return _config_path
    config_home = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(config_home) / "instapyper" / "config.json"


def load_config() -> dict:
    """Load config from file."""
    config_path = get_config_path()
    if config_path.exists():
        return json.loads(config_path.read_text())
    return {}


def save_config(config: dict) -> None:
    """Save config to file."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2))


# Keyring support
KEYRING_SERVICE = "instapyper"


def _keyring_available() -> bool:
    """Check if keyring is installed."""
    try:
        import keyring  # noqa: F401

        return True
    except ImportError:
        return False


def _get_from_keyring(key: str) -> str | None:
    """Get a value from system keyring."""
    if not _keyring_available():
        return None
    import keyring

    return keyring.get_password(KEYRING_SERVICE, key)


def _set_in_keyring(key: str, value: str) -> bool:
    """Store a value in system keyring. Returns True on success."""
    if not _keyring_available():
        return False
    import keyring

    keyring.set_password(KEYRING_SERVICE, key, value)
    return True


def _delete_from_keyring(key: str) -> None:
    """Delete a value from system keyring."""
    if not _keyring_available():
        return
    import contextlib

    import keyring
    import keyring.errors

    with contextlib.suppress(keyring.errors.PasswordDeleteError):
        keyring.delete_password(KEYRING_SERVICE, key)


def get_credentials() -> tuple[str, str, str | None, str | None]:
    """Get credentials from env vars, config file, or keyring.

    Lookup order:
    1. Environment variables (INSTAPAPER_CONSUMER_KEY, etc.)
    2. Config file (~/.config/instapyper/config.json)
    3. System keyring (if available)

    Returns:
        Tuple of (consumer_key, consumer_secret, oauth_token, oauth_token_secret)
    """
    # 1. Environment variables first
    consumer_key = os.environ.get("INSTAPAPER_CONSUMER_KEY")
    consumer_secret = os.environ.get("INSTAPAPER_CONSUMER_SECRET")

    # 2. Config file
    config = load_config()
    if not consumer_key:
        consumer_key = config.get("consumer_key")
    if not consumer_secret:
        consumer_secret = config.get("consumer_secret")

    # 3. Keyring fallback for consumer credentials
    if not consumer_key:
        consumer_key = _get_from_keyring("consumer_key")
    if not consumer_secret:
        consumer_secret = _get_from_keyring("consumer_secret")

    # OAuth tokens: config file first, then keyring
    oauth_token = config.get("oauth_token") or _get_from_keyring("oauth_token")
    oauth_token_secret = config.get("oauth_token_secret") or _get_from_keyring("oauth_token_secret")

    return consumer_key or "", consumer_secret or "", oauth_token, oauth_token_secret


def get_client(require_auth: bool = True) -> Instapaper:
    """Get an authenticated Instapaper client."""
    consumer_key, consumer_secret, oauth_token, oauth_token_secret = get_credentials()

    if not consumer_key or not consumer_secret:
        err_console.print(
            "[red]Consumer credentials not found.[/red]\n"
            "Set INSTAPAPER_CONSUMER_KEY and INSTAPAPER_CONSUMER_SECRET environment variables,\n"
            "or run 'instapyper login' to configure."
        )
        raise typer.Exit(1) from None

    client = Instapaper(consumer_key, consumer_secret, timeout=_timeout)

    if require_auth:
        if not oauth_token or not oauth_token_secret:
            err_console.print("[red]Not logged in.[/red] Run 'instapyper login' first.")
            raise typer.Exit(1) from None
        client.login_with_token(oauth_token, oauth_token_secret)

    return client


def _find_bookmark(
    client: Instapaper,
    bookmark_id: int,
    folder: str = "unread",
    status_msg: str = "Fetching bookmarks...",
) -> Bookmark:
    """Find a bookmark by ID, fetching from specified folder.

    Note: Instapaper API does not support single-bookmark lookup, so we must
    fetch and filter. For repeated operations, consider caching the result.

    Args:
        client: Authenticated Instapaper client
        bookmark_id: The bookmark ID to find
        folder: Folder to search in (default "unread")
        status_msg: Status message to show during fetch

    Returns:
        The Bookmark object if found

    Raises:
        typer.Exit: If bookmark not found
    """

    with err_console.status(status_msg):
        bookmarks = client.get_bookmarks(folder=folder, limit=500)
    bookmark = next((b for b in bookmarks if b.bookmark_id == bookmark_id), None)
    if not bookmark:
        folder_hint = f" --folder {folder}" if folder != "unread" else ""
        error_with_hint(
            f"Bookmark {bookmark_id} not found in {folder}",
            f"Check bookmark ID with 'instapyper bookmarks list{folder_hint}'",
        )
        raise typer.Exit(1) from None
    return bookmark


def _resolve_folder(client: Instapaper, folder_str: str) -> int:
    """Resolve a folder name/slug to its ID.

    Args:
        client: Authenticated Instapaper client
        folder_str: Folder ID (numeric) or name/slug

    Returns:
        The folder ID as an integer

    Raises:
        typer.Exit: If folder not found by name/slug
    """
    # If it's already a numeric ID, return it directly
    if folder_str.isdigit():
        return int(folder_str)

    # Search folders by name or slug
    with err_console.status("Looking up folder..."):
        folders = client.get_folders()

    folder_lower = folder_str.lower()
    for f in folders:
        if f.title.lower() == folder_lower or f.slug.lower() == folder_lower:
            return f.folder_id

    error_with_hint(
        f"Folder '{folder_str}' not found",
        "Check folder names with 'instapyper folders list'",
    )
    raise typer.Exit(1) from None


@app.command(
    help="""Authenticate with Instapaper and store tokens.

Examples:
  instapyper login
  instapyper login --username user@example.com --password-stdin < password.txt
  instapyper login --consumer-key-file key.txt --consumer-secret-file secret.txt
  instapyper login --keyring  # store in system keyring instead of config file
""",
)
def login(
    consumer_key_file: Annotated[
        Path | None,
        typer.Option("--consumer-key-file", help="Read consumer key from file"),
    ] = None,
    consumer_secret_file: Annotated[
        Path | None,
        typer.Option("--consumer-secret-file", help="Read consumer secret from file"),
    ] = None,
    username_opt: Annotated[
        str | None,
        typer.Option("--username", "-u", help="Instapaper username/email"),
    ] = None,
    password_file: Annotated[
        Path | None,
        typer.Option("--password-file", help="Read password from file"),
    ] = None,
    password_stdin: Annotated[
        bool,
        typer.Option("--password-stdin", help="Read password from stdin"),
    ] = False,
    use_keyring: Annotated[
        bool,
        typer.Option("--keyring", help="Store tokens in system keyring instead of config file"),
    ] = False,
) -> None:
    """Authenticate with Instapaper and store tokens."""
    config = load_config()

    # Get consumer credentials from various sources
    consumer_key = os.environ.get("INSTAPAPER_CONSUMER_KEY") or config.get("consumer_key")
    consumer_secret = os.environ.get("INSTAPAPER_CONSUMER_SECRET") or config.get("consumer_secret")

    # Read from files if specified
    if consumer_key_file:
        if not consumer_key_file.exists():
            error_with_hint(
                f"Consumer key file not found: {consumer_key_file}",
                "Check the file path is correct.",
            )
            raise typer.Exit(1) from None
        consumer_key = consumer_key_file.read_text().strip()

    if consumer_secret_file:
        if not consumer_secret_file.exists():
            error_with_hint(
                f"Consumer secret file not found: {consumer_secret_file}",
                "Check the file path is correct.",
            )
            raise typer.Exit(1) from None
        consumer_secret = consumer_secret_file.read_text().strip()

    # Check if prompts are needed but --no-input is set
    needs_prompt = not consumer_key or not consumer_secret
    if needs_prompt and get_no_input():
        error_with_hint(
            "Cannot prompt for credentials with --no-input.",
            "Set INSTAPAPER_CONSUMER_KEY/INSTAPAPER_CONSUMER_SECRET env vars, "
            "or use --consumer-key-file/--consumer-secret-file.",
        )
        raise typer.Exit(1) from None

    # Get username
    username = username_opt
    if not username:
        if get_no_input():
            error_with_hint(
                "Cannot prompt for username with --no-input.",
                "Use --username to specify the username.",
            )
            raise typer.Exit(1) from None
        username = typer.prompt("Instapaper username/email")

    # Get password from various sources
    password: str | None = None
    if password_stdin:
        password = sys.stdin.read().strip()
        if not password:
            error_with_hint("No password provided on stdin.")
            raise typer.Exit(1) from None
    elif password_file:
        if not password_file.exists():
            error_with_hint(
                f"Password file not found: {password_file}",
                "Check the file path is correct.",
            )
            raise typer.Exit(1) from None
        password = password_file.read_text().strip()
    else:
        if get_no_input():
            error_with_hint(
                "Cannot prompt for password with --no-input.",
                "Use --password-file or --password-stdin.",
            )
            raise typer.Exit(1) from None
        password = typer.prompt("Instapaper password", hide_input=True)

    if not consumer_key:
        consumer_key = typer.prompt("Consumer key")
    if not consumer_secret:
        consumer_secret = typer.prompt("Consumer secret", hide_input=True)

    try:
        client = Instapaper(consumer_key, consumer_secret, timeout=_timeout)
        with err_console.status("Authenticating..."):
            user = client.login(username, password)

        # Save credentials
        if use_keyring:
            if not _keyring_available():
                error_with_hint(
                    "Keyring not available.",
                    "Install with: pip install instapyper[keyring]",
                )
                raise typer.Exit(1) from None
            _set_in_keyring("consumer_key", consumer_key)
            _set_in_keyring("consumer_secret", consumer_secret)
            _set_in_keyring("oauth_token", client.oauth_token)
            _set_in_keyring("oauth_token_secret", client.oauth_token_secret)
            quiet_print(f"Logged in as {user.username}")
            quiet_print("Credentials saved to system keyring")
        else:
            config["consumer_key"] = consumer_key
            config["consumer_secret"] = consumer_secret
            config["oauth_token"] = client.oauth_token
            config["oauth_token_secret"] = client.oauth_token_secret
            save_config(config)
            quiet_print(f"Logged in as {user.username}")
            quiet_print(f"Credentials saved to {get_config_path()}")

    except AuthenticationError as e:
        error_with_hint(
            f"Authentication failed: {e}",
            "Check your username/email and password.",
        )
        raise typer.Exit(1) from None


@app.command(
    help="""Remove stored credentials.

Clears OAuth tokens from both the config file and system keyring (if available).

Examples:
  instapyper logout
  instapyper logout --force
""",
)
def logout(
    force: Annotated[
        bool, typer.Option("--force", "-f", "--yes", "-y", help="Skip confirmation prompt")
    ] = False,
) -> None:
    """Remove stored credentials."""
    config_path = get_config_path()
    has_config = config_path.exists()
    has_keyring = _get_from_keyring("oauth_token") is not None

    if not has_config and not has_keyring:
        quiet_print("No credentials stored.")
        return

    if not force:
        if get_no_input():
            error_with_hint(
                "Cannot confirm logout with --no-input.",
                "Use --force to skip confirmation.",
            )
            raise typer.Exit(1) from None
        if not typer.confirm("Remove stored credentials?"):
            console.print("Cancelled")
            raise typer.Exit(0) from None

    # Remove auth tokens from config file (keep consumer keys)
    if has_config:
        config = load_config()
        config.pop("oauth_token", None)
        config.pop("oauth_token_secret", None)
        save_config(config)

    # Also clear from keyring
    _delete_from_keyring("oauth_token")
    _delete_from_keyring("oauth_token_secret")

    quiet_print("Logged out successfully")


@app.command(
    help="""Show current user info.

Examples:
  instapyper user
""",
)
def user() -> None:
    """Show current user info."""
    client = get_client()
    try:
        with err_console.status("Fetching user info..."):
            user_info = client.get_user()
        console.print(f"User ID: {user_info.user_id}")
        console.print(f"Username: {user_info.username}")
        active = user_info.subscription_is_active
        status = "[green]Active[/green]" if active else "[yellow]Inactive[/yellow]"
        console.print(f"Subscription: {status}")
    except InstapaperError as e:
        handle_error(e)
        raise typer.Exit(1) from None


# Bookmark commands


@bookmarks_app.command(
    "list",
    help="""List bookmarks in a folder.

Examples:
  instapyper bookmarks list
  instapyper bookmarks list -F archive
  instapyper bookmarks list --folder archive --tag tech --limit 10
  instapyper bookmarks list --all  # list from all folders
  instapyper bookmarks list --json | jq '.[].title'
""",
)
def bookmarks_list(
    folder: Annotated[str, typer.Option("--folder", "-F", help="Folder name or ID")] = "unread",
    all_folders: Annotated[bool, typer.Option("--all", "-a", help="List from all folders")] = False,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max bookmarks to show")] = 25,
    tag: Annotated[str | None, typer.Option("--tag", help="Filter by tag")] = None,
    json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
    plain_output: Annotated[
        bool, typer.Option("--plain", "-p", help="Plain tab-separated output")
    ] = False,
) -> None:
    client = get_client()
    try:
        if all_folders:
            # Fetch from all folders: unread, starred, archive, and custom folders
            with err_console.status("Fetching bookmarks from all folders..."):
                all_bookmarks: list = []
                seen_ids: set[int] = set()

                # Built-in folders
                for builtin_folder in ["unread", "starred", "archive"]:
                    folder_bookmarks = client.get_bookmarks(
                        folder=builtin_folder, limit=500, tag=tag or ""
                    )
                    for b in folder_bookmarks:
                        if b.bookmark_id not in seen_ids:
                            seen_ids.add(b.bookmark_id)
                            all_bookmarks.append(b)

                # Custom folders
                folders = client.get_folders()
                for f in folders:
                    folder_bookmarks = client.get_bookmarks(
                        folder=f.folder_id, limit=500, tag=tag or ""
                    )
                    for b in folder_bookmarks:
                        if b.bookmark_id not in seen_ids:
                            seen_ids.add(b.bookmark_id)
                            all_bookmarks.append(b)

                bookmarks = all_bookmarks[:limit]
        else:
            with err_console.status("Fetching bookmarks..."):
                bookmarks = client.get_bookmarks(folder=folder, limit=limit, tag=tag or "")

        use_json = json_output

        if use_json:
            output = [
                {
                    "bookmark_id": b.bookmark_id,
                    "url": b.url,
                    "title": b.title,
                    "description": b.description,
                    "starred": b.starred,
                    "progress": b.progress,
                }
                for b in bookmarks
            ]
            print(json.dumps(output))
            return

        if plain_output:
            # Tab-separated: ID, title, url, starred, progress
            for b in bookmarks:
                starred = "1" if b.starred else "0"
                print(f"{b.bookmark_id}\t{b.title}\t{b.url}\t{starred}\t{b.progress}")
            return

        if not bookmarks:
            console.print("[dim]No bookmarks found.[/dim]")
            return

        table_title = "Bookmarks (all folders)" if all_folders else f"Bookmarks ({folder})"
        table = Table(title=table_title)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="white", max_width=50)
        table.add_column("★", style="yellow", justify="center")
        table.add_column("Progress", justify="right")

        for b in bookmarks:
            star = "★" if b.starred else ""
            progress = f"{b.progress:.0%}" if b.progress > 0 else ""
            title = b.title[:50] + "..." if len(b.title) > 50 else b.title
            table.add_row(str(b.bookmark_id), title, star, progress)

        print_with_pager(table, len(bookmarks))

    except InstapaperError as e:
        handle_error(e)
        raise typer.Exit(1) from None


@bookmarks_app.command(
    "add",
    help="""Add a new bookmark.

Examples:
  instapyper bookmarks add https://example.com
  instapyper bookmarks add https://example.com --title "My Article"
  instapyper bookmarks add https://example.com --tags "tech,ai"
  echo "https://example.com" | instapyper bookmarks add -
  instapyper bookmarks add -- -weird-url.com  # use -- for URLs starting with -
""",
)
def bookmarks_add(
    url: Annotated[str, typer.Argument(help="URL to bookmark (use '-' to read from stdin)")],
    title: Annotated[str | None, typer.Option("--title", "-t", help="Bookmark title")] = None,
    folder: Annotated[str | None, typer.Option("--folder", "-F", help="Folder ID or name")] = None,
    tags: Annotated[str | None, typer.Option("--tags", help="Comma-separated tags")] = None,
    json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
) -> None:
    # Support reading URL from stdin
    if url == "-":
        if sys.stdin.isatty():
            error_with_hint(
                "No URL provided on stdin",
                "Pipe a URL: echo 'https://...' | instapyper bookmarks add -",
            )
            raise typer.Exit(2) from None  # Exit 2 for bad arguments
        url = sys.stdin.read().strip()
        if not url:
            error_with_hint(
                "Empty input on stdin",
                "Pipe a URL: echo 'https://...' | instapyper bookmarks add -",
            )
            raise typer.Exit(2) from None  # Exit 2 for bad arguments

    client = get_client()
    try:
        folder_id = _resolve_folder(client, folder) if folder else None
        tag_list = [t.strip() for t in tags.split(",")] if tags else None
        bookmark = client.add_bookmark(url=url, title=title, folder_id=folder_id, tags=tag_list)

        if json_output:
            console.print_json(
                json.dumps(
                    {
                        "bookmark_id": bookmark.bookmark_id,
                        "url": bookmark.url,
                        "title": bookmark.title,
                    }
                )
            )
            return

        quiet_print(f"Added: {bookmark.title}")
        quiet_print(f"ID: {bookmark.bookmark_id}")

    except InstapaperError as e:
        handle_error(e, "Check that the URL is valid and accessible.")
        raise typer.Exit(1) from None


@bookmarks_app.command(
    "delete",
    help="""Delete one or more bookmarks.

Examples:
  instapyper bookmarks delete 12345
  instapyper bookmarks delete 12345 67890 11111  # delete multiple
  instapyper bookmarks delete 12345 --force
  instapyper bookmarks delete 12345 --dry-run
""",
)
def bookmarks_delete(
    bookmark_ids: Annotated[list[int], typer.Argument(help="Bookmark ID(s) to delete")],
    force: Annotated[
        bool, typer.Option("--force", "-f", "--yes", "-y", help="Skip confirmation prompt")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", "-n", help="Preview what would be deleted")
    ] = False,
) -> None:
    if dry_run:
        ids_str = ", ".join(str(id) for id in bookmark_ids)
        console.print(f"Dry run: Would delete bookmark(s) {ids_str}")
        return

    if not force:
        if get_no_input():
            error_with_hint(
                "Cannot confirm deletion with --no-input.",
                "Use --force to skip confirmation, or --dry-run to preview.",
            )
            raise typer.Exit(1) from None
        count = len(bookmark_ids)
        msg = f"Delete {count} bookmark(s)?" if count > 1 else f"Delete bookmark {bookmark_ids[0]}?"
        if not typer.confirm(msg):
            console.print("Cancelled")
            raise typer.Exit(0) from None

    client = get_client()
    total = len(bookmark_ids)
    for i, bookmark_id in enumerate(bookmark_ids, 1):
        try:
            client.delete_bookmark(bookmark_id)
            if total > 1:
                quiet_print(f"Deleted {i}/{total}: {bookmark_id}")
            else:
                quiet_print(f"Deleted bookmark {bookmark_id}")
        except InstapaperError as e:
            handle_error(e, "Check bookmark ID with 'instapyper bookmarks list'")
            raise typer.Exit(1) from None


@bookmarks_app.command(
    "archive",
    help="""Archive one or more bookmarks.

Examples:
  instapyper bookmarks archive 12345
  instapyper bookmarks archive 12345 67890 11111  # archive multiple
""",
)
def bookmarks_archive(
    bookmark_ids: Annotated[list[int], typer.Argument(help="Bookmark ID(s) to archive")],
) -> None:
    """Archive one or more bookmarks."""
    client = get_client()
    total = len(bookmark_ids)
    for i, bookmark_id in enumerate(bookmark_ids, 1):
        try:
            client.archive_bookmark(bookmark_id)
            if total > 1:
                quiet_print(f"Archived {i}/{total}: {bookmark_id}")
            else:
                quiet_print(f"Archived bookmark {bookmark_id}")
        except InstapaperError as e:
            handle_error(e)
            raise typer.Exit(1) from None


@bookmarks_app.command(
    "star",
    help="""Star one or more bookmarks.

Examples:
  instapyper bookmarks star 12345
  instapyper bookmarks star 12345 67890 11111  # star multiple
""",
)
def bookmarks_star(
    bookmark_ids: Annotated[list[int], typer.Argument(help="Bookmark ID(s) to star")],
) -> None:
    """Star one or more bookmarks."""
    client = get_client()
    total = len(bookmark_ids)
    for i, bookmark_id in enumerate(bookmark_ids, 1):
        try:
            client.star_bookmark(bookmark_id)
            if total > 1:
                quiet_print(f"Starred {i}/{total}: {bookmark_id} ★")
            else:
                quiet_print(f"Starred bookmark {bookmark_id} ★")
        except InstapaperError as e:
            handle_error(e)
            raise typer.Exit(1) from None


@bookmarks_app.command(
    "unstar",
    help="""Unstar one or more bookmarks.

Examples:
  instapyper bookmarks unstar 12345
  instapyper bookmarks unstar 12345 67890 11111  # unstar multiple
""",
)
def bookmarks_unstar(
    bookmark_ids: Annotated[list[int], typer.Argument(help="Bookmark ID(s) to unstar")],
) -> None:
    """Unstar one or more bookmarks."""
    client = get_client()
    total = len(bookmark_ids)
    for i, bookmark_id in enumerate(bookmark_ids, 1):
        try:
            client.unstar_bookmark(bookmark_id)
            if total > 1:
                quiet_print(f"Unstarred {i}/{total}: {bookmark_id}")
            else:
                quiet_print(f"Unstarred bookmark {bookmark_id}")
        except InstapaperError as e:
            handle_error(e)
            raise typer.Exit(1) from None


@bookmarks_app.command(
    "unarchive",
    help="""Unarchive one or more bookmarks (move back to unread).

Examples:
  instapyper bookmarks unarchive 12345
  instapyper bookmarks unarchive 12345 67890 11111  # unarchive multiple
""",
)
def bookmarks_unarchive(
    bookmark_ids: Annotated[list[int], typer.Argument(help="Bookmark ID(s) to unarchive")],
) -> None:
    """Unarchive one or more bookmarks (move back to unread)."""
    client = get_client()
    total = len(bookmark_ids)
    for i, bookmark_id in enumerate(bookmark_ids, 1):
        try:
            client.unarchive_bookmark(bookmark_id)
            if total > 1:
                quiet_print(f"Unarchived {i}/{total}: {bookmark_id}")
            else:
                quiet_print(f"Unarchived bookmark {bookmark_id}")
        except InstapaperError as e:
            handle_error(e)
            raise typer.Exit(1) from None


@bookmarks_app.command(
    "move",
    help="""Move one or more bookmarks to a different folder.

Examples:
  instapyper bookmarks move 12345 -F 456
  instapyper bookmarks move 12345 -F "Read Later"  # by folder name
  instapyper bookmarks move 12345 67890 -F 456  # move multiple
  instapyper folders list  # to see folder IDs/names
""",
)
def bookmarks_move(
    bookmark_ids: Annotated[list[int], typer.Argument(help="Bookmark ID(s) to move")],
    folder: Annotated[str, typer.Option("--folder", "-F", help="Target folder ID or name")],
) -> None:
    """Move one or more bookmarks to a different folder."""
    client = get_client()
    folder_id = _resolve_folder(client, folder)
    total = len(bookmark_ids)
    for i, bookmark_id in enumerate(bookmark_ids, 1):
        try:
            client.move_bookmark(bookmark_id, folder_id)
            if total > 1:
                quiet_print(f"Moved {i}/{total}: {bookmark_id} to folder {folder}")
            else:
                quiet_print(f"Moved bookmark {bookmark_id} to folder {folder}")
        except InstapaperError as e:
            handle_error(e, "Check folder ID with 'instapyper folders list'")
            raise typer.Exit(1) from None


@bookmarks_app.command(
    "progress",
    help="""Update reading progress for a bookmark.

Examples:
  instapyper bookmarks progress 12345 0.5   # Mark as 50% read
  instapyper bookmarks progress 12345 1.0   # Mark as fully read
""",
)
def bookmarks_progress(
    bookmark_id: Annotated[int, typer.Argument(help="Bookmark ID")],
    progress: Annotated[float, typer.Argument(help="Reading progress (0.0 to 1.0)")],
) -> None:
    """Update reading progress for a bookmark."""
    if not 0.0 <= progress <= 1.0:
        error_with_hint("Progress must be between 0.0 and 1.0", "Example: 0.5 for 50%")
        raise typer.Exit(2) from None  # Exit 2 for bad arguments

    client = get_client()
    try:
        client.update_bookmark_progress(bookmark_id, progress)
        quiet_print(f"Updated progress to {progress:.0%}")
    except InstapaperError as e:
        handle_error(e)
        raise typer.Exit(1) from None


@bookmarks_app.command(
    "text",
    help="""Get the text content of a bookmark.

Examples:
  instapyper bookmarks text 12345
  instapyper bookmarks text 12345 --html
  instapyper bookmarks text 12345 | less
""",
)
def bookmarks_text(
    bookmark_id: Annotated[int, typer.Argument(help="Bookmark ID")],
    html: Annotated[bool, typer.Option("--html", help="Output raw HTML instead of text")] = False,
) -> None:
    """Get the text content of a bookmark."""
    client = get_client()
    try:
        bookmark = _find_bookmark(client, bookmark_id)
        if html:
            console.print(bookmark.html)
        else:
            console.print(bookmark.text)
    except InstapaperError as e:
        handle_error(e)
        raise typer.Exit(1) from None


# Folder commands


@folders_app.command(
    "list",
    help="""List all folders.

Examples:
  instapyper folders list
  instapyper folders list --json
  instapyper folders list --plain | cut -f1  # just IDs
""",
)
def folders_list(
    json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
    plain_output: Annotated[
        bool, typer.Option("--plain", "-p", help="Plain tab-separated output")
    ] = False,
) -> None:
    """List all folders."""
    client = get_client()
    try:
        with err_console.status("Fetching folders..."):
            folders = client.get_folders()

        use_json = json_output

        if use_json:
            output = [
                {
                    "folder_id": f.folder_id,
                    "title": f.title,
                    "slug": f.slug,
                    "position": f.position,
                }
                for f in folders
            ]
            print(json.dumps(output))
            return

        if plain_output:
            # Tab-separated: ID, title, slug, position
            for f in folders:
                print(f"{f.folder_id}\t{f.title}\t{f.slug}\t{f.position}")
            return

        if not folders:
            console.print("[dim]No folders found.[/dim]")
            return

        table = Table(title="Folders")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="white")
        table.add_column("Slug", style="dim")

        for f in folders:
            table.add_row(str(f.folder_id), f.title, f.slug)

        console.print(table)

    except InstapaperError as e:
        handle_error(e)
        raise typer.Exit(1) from None


@folders_app.command(
    "create",
    help="""Create a new folder.

Examples:
  instapyper folders create "Read Later"
  instapyper folders create "Tech Articles" --json
""",
)
def folders_create(
    name: Annotated[str, typer.Argument(help="Folder name")],
    json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
) -> None:
    """Create a new folder."""
    client = get_client()
    try:
        with err_console.status("Creating folder..."):
            folder = client.create_folder(name)

        if json_output:
            console.print_json(
                json.dumps(
                    {
                        "folder_id": folder.folder_id,
                        "title": folder.title,
                    }
                )
            )
            return

        quiet_print(f"Created folder: {folder.title}")
        quiet_print(f"ID: {folder.folder_id}")

    except InstapaperError as e:
        handle_error(e)
        raise typer.Exit(1) from None


@folders_app.command(
    "delete",
    help="""Delete a folder.

Examples:
  instapyper folders delete 12345
  instapyper folders delete 12345 --force
  instapyper folders delete 12345 --dry-run
""",
)
def folders_delete(
    folder_id: Annotated[int, typer.Argument(help="Folder ID to delete")],
    force: Annotated[
        bool, typer.Option("--force", "-f", "--yes", "-y", help="Skip confirmation prompt")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", "-n", help="Preview what would be deleted")
    ] = False,
) -> None:
    """Delete a folder."""
    if dry_run:
        console.print(f"Dry run: Would delete folder {folder_id}")
        return

    if not force:
        if get_no_input():
            error_with_hint(
                "Cannot confirm deletion with --no-input.",
                "Use --force to skip confirmation, or --dry-run to preview.",
            )
            raise typer.Exit(1) from None
        if not typer.confirm(f"Delete folder {folder_id}?"):
            console.print("Cancelled")
            raise typer.Exit(0) from None

    client = get_client()
    try:
        with err_console.status("Deleting folder..."):
            client.delete_folder(folder_id)
        quiet_print(f"Deleted folder {folder_id}")
    except InstapaperError as e:
        handle_error(e, "Check folder ID with 'instapyper folders list'")
        raise typer.Exit(1) from None


@folders_app.command(
    "order",
    help="""Set the display order of folders.

Examples:
  instapyper folders order "123:0,456:1"
  instapyper folders order "123:0,456:1,789:2"
""",
)
def folders_order(
    order: Annotated[str, typer.Argument(help="Order as 'id:pos,...' (e.g., '123:0,456:1')")],
) -> None:
    """Set the display order of folders."""
    client = get_client()
    try:
        # Parse order string into dict
        order_dict: dict[int, int] = {}
        for pair in order.split(","):
            pair = pair.strip()
            if not pair:
                continue
            folder_id_str, position_str = pair.split(":")
            order_dict[int(folder_id_str)] = int(position_str)

        if not order_dict:
            error_with_hint(
                "No valid order pairs provided",
                "Use format 'id:pos,...' (e.g., '123:0,456:1')",
            )
            raise typer.Exit(2) from None  # Exit 2 for bad arguments

        with err_console.status("Updating folder order..."):
            client.set_folder_order(order_dict)
        quiet_print("Folder order updated")
    except ValueError as e:
        error_with_hint(f"Invalid format: {e}", "Use format 'id:pos,...' (e.g., '123:0,456:1')")
        raise typer.Exit(2) from None  # Exit 2 for bad arguments
    except InstapaperError as e:
        handle_error(e)
        raise typer.Exit(1) from None


# Highlight commands


@highlights_app.command(
    "list",
    help="""List highlights for a bookmark.

Examples:
  instapyper highlights list 12345
  instapyper highlights list 12345 --json
  instapyper highlights list 12345 --plain | cut -f2  # just text
""",
)
def highlights_list(
    bookmark_id: Annotated[int, typer.Argument(help="Bookmark ID")],
    json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
    plain_output: Annotated[
        bool, typer.Option("--plain", "-p", help="Plain tab-separated output")
    ] = False,
) -> None:
    """List highlights for a bookmark."""
    client = get_client()
    try:
        bookmark = _find_bookmark(client, bookmark_id)
        highlights = bookmark.get_highlights()

        use_json = json_output

        if use_json:
            output = [
                {
                    "highlight_id": h.highlight_id,
                    "text": h.text,
                    "position": h.position,
                }
                for h in highlights
            ]
            print(json.dumps(output))
            return

        if plain_output:
            # Tab-separated: ID, text, position
            for h in highlights:
                # Replace tabs/newlines in text to avoid breaking TSV format
                text = h.text.replace("\t", " ").replace("\n", " ")
                print(f"{h.highlight_id}\t{text}\t{h.position}")
            return

        if not highlights:
            console.print("[dim]No highlights found.[/dim]")
            return

        table = Table(title=f"Highlights for bookmark {bookmark_id}")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Text", style="white", max_width=60)
        table.add_column("Position", justify="right")

        for h in highlights:
            text = h.text[:60] + "..." if len(h.text) > 60 else h.text
            table.add_row(str(h.highlight_id), text, str(h.position))

        print_with_pager(table, len(highlights))

    except InstapaperError as e:
        handle_error(e)
        raise typer.Exit(1) from None


@highlights_app.command(
    "create",
    help="""Create a highlight in a bookmark.

Examples:
  instapyper highlights create 12345 "Important quote"
  instapyper highlights create 12345 "Key insight" --position 100
  instapyper highlights create 12345 "Notable text" --json
""",
)
def highlights_create(
    bookmark_id: Annotated[int, typer.Argument(help="Bookmark ID")],
    text: Annotated[str, typer.Argument(help="Text to highlight")],
    position: Annotated[int, typer.Option("--position", "-p", help="Position in text")] = 0,
    json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
) -> None:
    """Create a highlight in a bookmark."""
    client = get_client()
    try:
        bookmark = _find_bookmark(client, bookmark_id)
        highlight = bookmark.create_highlight(text, position)

        if json_output:
            console.print_json(
                json.dumps(
                    {
                        "highlight_id": highlight.highlight_id,
                        "text": highlight.text,
                        "position": highlight.position,
                    }
                )
            )
            return

        quiet_print("Created highlight")
        quiet_print(f"ID: {highlight.highlight_id}")

    except InstapaperError as e:
        handle_error(e)
        raise typer.Exit(1) from None


@highlights_app.command(
    "delete",
    help="""Delete a highlight.

Examples:
  instapyper highlights delete 12345 67890
  instapyper highlights delete 12345 67890 --force
  instapyper highlights delete 12345 67890 --dry-run
""",
)
def highlights_delete(
    bookmark_id: Annotated[int, typer.Argument(help="Bookmark ID")],
    highlight_id: Annotated[int, typer.Argument(help="Highlight ID to delete")],
    force: Annotated[
        bool, typer.Option("--force", "-f", "--yes", "-y", help="Skip confirmation prompt")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", "-n", help="Preview what would be deleted")
    ] = False,
) -> None:
    """Delete a highlight."""
    if dry_run:
        console.print(f"Dry run: Would delete highlight {highlight_id} from bookmark {bookmark_id}")
        return

    if not force:
        if get_no_input():
            error_with_hint(
                "Cannot confirm deletion with --no-input.",
                "Use --force to skip confirmation, or --dry-run to preview.",
            )
            raise typer.Exit(1) from None
        if not typer.confirm(f"Delete highlight {highlight_id}?"):
            console.print("Cancelled")
            raise typer.Exit(0) from None

    client = get_client()
    try:
        client.delete_highlight(highlight_id)
        quiet_print(f"Deleted highlight {highlight_id}")
    except InstapaperError as e:
        handle_error(e, f"Check highlight IDs with 'instapyper highlights list {bookmark_id}'")
        raise typer.Exit(1) from None


@app.command("cheatsheet", help="Show common workflows and quick reference.")
def cheatsheet() -> None:
    """Print a quick reference of common commands and workflows."""
    cheat = """\
[bold]instapyper cheatsheet[/bold]

[bold cyan]Getting Started[/bold cyan]
  instapyper login                    # authenticate with Instapaper
  instapyper user                     # show current user info

[bold cyan]Bookmarks[/bold cyan]
  instapyper bookmarks list           # list unread bookmarks
  instapyper bookmarks list -F archive# list archived bookmarks
  instapyper bookmarks list --all     # list from all folders
  instapyper bookmarks add URL        # add a new bookmark
  instapyper bookmarks archive ID     # archive a bookmark
  instapyper bookmarks star ID        # star a bookmark
  instapyper bookmarks text ID        # get article text
  instapyper bookmarks delete ID -f   # delete (skip confirm)

[bold cyan]Bulk Operations[/bold cyan]
  instapyper bookmarks delete 1 2 3   # delete multiple bookmarks
  instapyper bookmarks archive 1 2 3  # archive multiple
  instapyper bookmarks star 1 2 3     # star multiple
  instapyper bookmarks unarchive 1 2 3  # unarchive multiple
  instapyper bookmarks move 1 2 3 -F Tech  # move multiple to folder

[bold cyan]Folders[/bold cyan]
  instapyper folders list             # list all folders
  instapyper folders create "Name"    # create a folder
  instapyper bookmarks move ID -F 123 # move by folder ID
  instapyper bookmarks move ID -F Tech  # move by folder name

[bold cyan]Highlights[/bold cyan]
  instapyper highlights list ID       # list highlights for bookmark
  instapyper highlights create ID "text"  # create highlight

[bold cyan]Output Formats[/bold cyan]
  --json                              # JSON output for scripting
  --plain                             # tab-separated for grep/cut

[bold cyan]Scripting Examples[/bold cyan]
  # Archive all starred bookmarks
  instapyper bookmarks list -F starred --plain | cut -f1 | \\
    xargs instapyper bookmarks archive

  # Export all bookmarks as JSON
  instapyper bookmarks list --all --json > bookmarks.json

  # Delete old archived items (requires jq)
  instapyper bookmarks list -F archive --json | jq -r '.[].bookmark_id' | \\
    xargs instapyper bookmarks delete -f

[bold cyan]Global Options[/bold cyan]
  --debug                             # show API requests & stack traces
  --quiet                             # suppress non-essential output
  --no-pager                          # disable pager for long output
  --timeout N                         # network timeout in seconds
"""
    console.print(cheat)


if __name__ == "__main__":
    app()
