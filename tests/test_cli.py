"""Tests for the CLI."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from instapyper.cli import app

from .conftest import (
    CONSUMER_KEY,
    CONSUMER_SECRET,
    OAUTH_TOKEN,
    OAUTH_TOKEN_SECRET,
    USERNAME,
)

runner = CliRunner()


@pytest.fixture
def mock_config(tmp_path: Path) -> Path:
    """Create a mock config file with credentials."""
    config_dir = tmp_path / "instapyper"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "consumer_key": CONSUMER_KEY,
                "consumer_secret": CONSUMER_SECRET,
                "oauth_token": OAUTH_TOKEN,
                "oauth_token_secret": OAUTH_TOKEN_SECRET,
            }
        )
    )
    return config_file


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock Instapaper client."""
    client = MagicMock()
    client.oauth_token = OAUTH_TOKEN
    client.oauth_token_secret = OAUTH_TOKEN_SECRET
    return client


class TestVersion:
    """Tests for --version flag."""

    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "instapyper" in result.stdout


class TestHelp:
    """Tests for --help flag."""

    def test_help_flag(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Instapaper" in result.stdout
        assert "bookmarks" in result.stdout
        assert "folders" in result.stdout
        assert "highlights" in result.stdout

    def test_bookmarks_help(self) -> None:
        result = runner.invoke(app, ["bookmarks", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout
        assert "add" in result.stdout
        assert "delete" in result.stdout

    def test_folders_help(self) -> None:
        result = runner.invoke(app, ["folders", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout
        assert "create" in result.stdout
        assert "delete" in result.stdout

    def test_highlights_help(self) -> None:
        result = runner.invoke(app, ["highlights", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout
        assert "create" in result.stdout
        assert "delete" in result.stdout


class TestCheatsheet:
    """Tests for cheatsheet command."""

    def test_cheatsheet(self) -> None:
        result = runner.invoke(app, ["cheatsheet"])
        assert result.exit_code == 0
        assert "Getting Started" in result.stdout
        assert "Bookmarks" in result.stdout
        assert "Bulk Operations" in result.stdout
        assert "Folders" in result.stdout


class TestLogin:
    """Tests for login command."""

    def test_login_no_credentials_no_input(self) -> None:
        result = runner.invoke(app, ["--no-input", "login"])
        assert result.exit_code == 1
        assert "Cannot prompt" in result.stderr

    @patch("instapyper.cli.Instapaper")
    @patch("instapyper.cli.save_config")
    @patch("instapyper.cli.load_config")
    def test_login_with_prompts(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_instapaper: MagicMock,
        mock_client: MagicMock,
    ) -> None:
        mock_load.return_value = {}
        mock_instapaper.return_value = mock_client
        mock_user = MagicMock()
        mock_user.username = USERNAME
        mock_client.login.return_value = mock_user

        result = runner.invoke(
            app,
            ["login"],
            input=f"{USERNAME}\npassword\n{CONSUMER_KEY}\n{CONSUMER_SECRET}\n",
        )
        assert result.exit_code == 0
        assert f"Logged in as {USERNAME}" in result.stdout


class TestLogout:
    """Tests for logout command."""

    @patch("instapyper.cli._get_from_keyring", return_value=None)
    @patch("instapyper.cli.get_config_path")
    def test_logout_no_credentials_anywhere(
        self, mock_path: MagicMock, mock_keyring_get: MagicMock, tmp_path: Path
    ) -> None:
        """No config file and no keyring credentials."""
        mock_path.return_value = tmp_path / "nonexistent" / "config.json"
        result = runner.invoke(app, ["logout"])
        assert result.exit_code == 0
        assert "No credentials stored" in result.stdout

    @patch("instapyper.cli._delete_from_keyring")
    @patch("instapyper.cli._get_from_keyring", return_value=None)
    @patch("instapyper.cli.save_config")
    @patch("instapyper.cli.load_config")
    @patch("instapyper.cli.get_config_path")
    def test_logout_config_only(
        self,
        mock_path: MagicMock,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_keyring_get: MagicMock,
        mock_keyring_delete: MagicMock,
        mock_config: Path,
    ) -> None:
        """Credentials in config file only, not in keyring."""
        mock_path.return_value = mock_config
        mock_load.return_value = {
            "consumer_key": "key",
            "oauth_token": "token",
            "oauth_token_secret": "secret",
        }

        result = runner.invoke(app, ["logout", "--force"])

        assert result.exit_code == 0
        assert "Logged out successfully" in result.stdout
        # Verify config was saved without oauth tokens but keeping consumer_key
        mock_save.assert_called_once()
        saved_config = mock_save.call_args[0][0]
        assert "oauth_token" not in saved_config
        assert "oauth_token_secret" not in saved_config
        assert saved_config.get("consumer_key") == "key"
        # Verify keyring delete was still called (cleanup)
        assert mock_keyring_delete.call_count == 2

    @patch("instapyper.cli._delete_from_keyring")
    @patch("instapyper.cli._get_from_keyring", return_value="keyring_token")
    @patch("instapyper.cli.get_config_path")
    def test_logout_keyring_only(
        self,
        mock_path: MagicMock,
        mock_keyring_get: MagicMock,
        mock_keyring_delete: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Credentials in keyring only, no config file."""
        mock_path.return_value = tmp_path / "nonexistent" / "config.json"

        result = runner.invoke(app, ["logout", "--force"])

        assert result.exit_code == 0
        assert "Logged out successfully" in result.stdout
        # Verify keyring delete was called for both tokens
        assert mock_keyring_delete.call_count == 2
        mock_keyring_delete.assert_any_call("oauth_token")
        mock_keyring_delete.assert_any_call("oauth_token_secret")

    @patch("instapyper.cli._delete_from_keyring")
    @patch("instapyper.cli._get_from_keyring", return_value="keyring_token")
    @patch("instapyper.cli.save_config")
    @patch("instapyper.cli.load_config")
    @patch("instapyper.cli.get_config_path")
    def test_logout_both_config_and_keyring(
        self,
        mock_path: MagicMock,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_keyring_get: MagicMock,
        mock_keyring_delete: MagicMock,
        mock_config: Path,
    ) -> None:
        """Credentials in both config file and keyring."""
        mock_path.return_value = mock_config
        mock_load.return_value = {"oauth_token": "file_token", "oauth_token_secret": "file_secret"}

        result = runner.invoke(app, ["logout", "--force"])

        assert result.exit_code == 0
        assert "Logged out successfully" in result.stdout
        # Verify config was saved without oauth tokens
        mock_save.assert_called_once()
        saved_config = mock_save.call_args[0][0]
        assert "oauth_token" not in saved_config
        assert "oauth_token_secret" not in saved_config
        # Verify keyring delete was called
        assert mock_keyring_delete.call_count == 2

    @patch("instapyper.cli._delete_from_keyring")
    @patch("instapyper.cli._get_from_keyring", return_value="keyring_token")
    @patch("instapyper.cli.save_config")
    @patch("instapyper.cli.load_config")
    @patch("instapyper.cli.get_config_path")
    def test_logout_confirmed_with_prompt(
        self,
        mock_path: MagicMock,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_keyring_get: MagicMock,
        mock_keyring_delete: MagicMock,
        mock_config: Path,
    ) -> None:
        """User confirms logout when prompted."""
        mock_path.return_value = mock_config
        mock_load.return_value = {"oauth_token": "token", "oauth_token_secret": "secret"}

        result = runner.invoke(app, ["logout"], input="y\n")

        assert result.exit_code == 0
        assert "Logged out successfully" in result.stdout
        mock_save.assert_called_once()
        assert mock_keyring_delete.call_count == 2

    @patch("instapyper.cli._get_from_keyring", return_value="keyring_token")
    @patch("instapyper.cli.get_config_path")
    def test_logout_cancelled_by_user(
        self, mock_path: MagicMock, mock_keyring_get: MagicMock, mock_config: Path
    ) -> None:
        """User cancels logout when prompted."""
        mock_path.return_value = mock_config

        result = runner.invoke(app, ["logout"], input="n\n")

        assert result.exit_code == 0
        assert "Cancelled" in result.stdout

    @patch("instapyper.cli.get_no_input", return_value=True)
    @patch("instapyper.cli._get_from_keyring", return_value="keyring_token")
    @patch("instapyper.cli.get_config_path")
    def test_logout_no_input_without_force_fails(
        self,
        mock_path: MagicMock,
        mock_keyring_get: MagicMock,
        mock_no_input: MagicMock,
        mock_config: Path,
    ) -> None:
        """--no-input without --force should fail."""
        mock_path.return_value = mock_config

        result = runner.invoke(app, ["logout"])

        assert result.exit_code == 1
        output = result.stdout + (result.stderr or "")
        assert "Cannot confirm logout" in output or "force" in output.lower()

    @patch("instapyper.cli._delete_from_keyring")
    @patch("instapyper.cli.get_no_input", return_value=True)
    @patch("instapyper.cli._get_from_keyring", return_value="keyring_token")
    @patch("instapyper.cli.get_config_path")
    def test_logout_no_input_with_force_succeeds(
        self,
        mock_path: MagicMock,
        mock_keyring_get: MagicMock,
        mock_no_input: MagicMock,
        mock_keyring_delete: MagicMock,
        tmp_path: Path,
    ) -> None:
        """--no-input with --force should succeed."""
        mock_path.return_value = tmp_path / "nonexistent" / "config.json"

        result = runner.invoke(app, ["logout", "--force"])

        assert result.exit_code == 0
        assert "Logged out successfully" in result.stdout


class TestUser:
    """Tests for user command."""

    @patch("instapyper.cli.get_client")
    def test_user_info(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_id = 12345
        mock_user.username = USERNAME
        mock_user.subscription_is_active = True
        mock_client.get_user.return_value = mock_user
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["user"])
        assert result.exit_code == 0
        assert "12345" in result.stdout
        assert USERNAME in result.stdout


class TestBookmarksList:
    """Tests for bookmarks list command."""

    @patch("instapyper.cli.get_client")
    def test_list_empty(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.get_bookmarks.return_value = []
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["bookmarks", "list"])
        assert result.exit_code == 0
        assert "No bookmarks found" in result.stdout

    @patch("instapyper.cli.get_client")
    def test_list_with_bookmarks(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_bookmark = MagicMock()
        mock_bookmark.bookmark_id = 100001
        mock_bookmark.title = "Test Article"
        mock_bookmark.url = "https://example.com"
        mock_bookmark.starred = False
        mock_bookmark.progress = 0.5
        mock_client.get_bookmarks.return_value = [mock_bookmark]
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["bookmarks", "list"])
        assert result.exit_code == 0
        assert "100001" in result.stdout
        assert "Test Article" in result.stdout

    @patch("instapyper.cli.get_client")
    def test_list_json_output(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_bookmark = MagicMock()
        mock_bookmark.bookmark_id = 100001
        mock_bookmark.title = "Test Article"
        mock_bookmark.url = "https://example.com"
        mock_bookmark.description = "A test"
        mock_bookmark.starred = True
        mock_bookmark.progress = 0.0
        mock_client.get_bookmarks.return_value = [mock_bookmark]
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["bookmarks", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["bookmark_id"] == 100001

    @patch("instapyper.cli.get_client")
    def test_list_plain_output(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_bookmark = MagicMock()
        mock_bookmark.bookmark_id = 100001
        mock_bookmark.title = "Test Article"
        mock_bookmark.url = "https://example.com"
        mock_bookmark.starred = False
        mock_bookmark.progress = 0.25
        mock_client.get_bookmarks.return_value = [mock_bookmark]
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["bookmarks", "list", "--plain"])
        assert result.exit_code == 0
        assert "100001\t" in result.stdout
        assert "https://example.com" in result.stdout


class TestBookmarksAdd:
    """Tests for bookmarks add command."""

    @patch("instapyper.cli.get_client")
    def test_add_bookmark(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_bookmark = MagicMock()
        mock_bookmark.bookmark_id = 100003
        mock_bookmark.title = "New Article"
        mock_bookmark.url = "https://example.com/new"
        mock_client.add_bookmark.return_value = mock_bookmark
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["bookmarks", "add", "https://example.com/new"])
        assert result.exit_code == 0
        assert "Added: New Article" in result.stdout
        assert "ID: 100003" in result.stdout

    @patch("instapyper.cli.get_client")
    def test_add_bookmark_with_title(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_bookmark = MagicMock()
        mock_bookmark.bookmark_id = 100003
        mock_bookmark.title = "Custom Title"
        mock_bookmark.url = "https://example.com/new"
        mock_client.add_bookmark.return_value = mock_bookmark
        mock_get_client.return_value = mock_client

        result = runner.invoke(
            app, ["bookmarks", "add", "https://example.com/new", "--title", "Custom Title"]
        )
        assert result.exit_code == 0
        mock_client.add_bookmark.assert_called_once()
        call_kwargs = mock_client.add_bookmark.call_args[1]
        assert call_kwargs["title"] == "Custom Title"

    @patch("instapyper.cli._resolve_folder")
    @patch("instapyper.cli.get_client")
    def test_add_bookmark_with_folder_name(
        self, mock_get_client: MagicMock, mock_resolve: MagicMock
    ) -> None:
        mock_client = MagicMock()
        mock_bookmark = MagicMock()
        mock_bookmark.bookmark_id = 100003
        mock_bookmark.title = "New Article"
        mock_bookmark.url = "https://example.com/new"
        mock_client.add_bookmark.return_value = mock_bookmark
        mock_get_client.return_value = mock_client
        mock_resolve.return_value = 5001

        result = runner.invoke(app, ["bookmarks", "add", "https://example.com/new", "-F", "Tech"])
        assert result.exit_code == 0
        mock_resolve.assert_called_once_with(mock_client, "Tech")

    @patch("instapyper.cli.get_client")
    def test_add_bookmark_json_output(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_bookmark = MagicMock()
        mock_bookmark.bookmark_id = 100003
        mock_bookmark.title = "New Article"
        mock_bookmark.url = "https://example.com/new"
        mock_client.add_bookmark.return_value = mock_bookmark
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["bookmarks", "add", "https://example.com/new", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["bookmark_id"] == 100003


class TestBookmarksDelete:
    """Tests for bookmarks delete command."""

    @patch("instapyper.cli.get_client")
    def test_delete_with_force(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["bookmarks", "delete", "100001", "--force"])
        assert result.exit_code == 0
        assert "Deleted bookmark 100001" in result.stdout
        mock_client.delete_bookmark.assert_called_once_with(100001)

    @patch("instapyper.cli.get_client")
    def test_delete_multiple(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = runner.invoke(
            app, ["bookmarks", "delete", "100001", "100002", "100003", "--force"]
        )
        assert result.exit_code == 0
        assert "Deleted 1/3" in result.stdout
        assert "Deleted 2/3" in result.stdout
        assert "Deleted 3/3" in result.stdout

    def test_delete_dry_run(self) -> None:
        result = runner.invoke(app, ["bookmarks", "delete", "100001", "--dry-run"])
        assert result.exit_code == 0
        assert "Dry run" in result.stdout
        assert "100001" in result.stdout

    def test_delete_cancelled(self) -> None:
        result = runner.invoke(app, ["bookmarks", "delete", "100001"], input="n\n")
        assert result.exit_code == 0
        assert "Cancelled" in result.stdout


class TestBookmarksArchive:
    """Tests for bookmarks archive command."""

    @patch("instapyper.cli.get_client")
    def test_archive_single(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["bookmarks", "archive", "100001"])
        assert result.exit_code == 0
        assert "Archived bookmark 100001" in result.stdout
        mock_client.archive_bookmark.assert_called_once_with(100001)

    @patch("instapyper.cli.get_client")
    def test_archive_multiple(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["bookmarks", "archive", "100001", "100002"])
        assert result.exit_code == 0
        assert "Archived 1/2" in result.stdout
        assert "Archived 2/2" in result.stdout


class TestBookmarksStar:
    """Tests for bookmarks star command."""

    @patch("instapyper.cli.get_client")
    def test_star_single(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["bookmarks", "star", "100001"])
        assert result.exit_code == 0
        assert "Starred bookmark 100001" in result.stdout
        assert "★" in result.stdout
        mock_client.star_bookmark.assert_called_once_with(100001)


class TestBookmarksUnarchive:
    """Tests for bookmarks unarchive command."""

    @patch("instapyper.cli.get_client")
    def test_unarchive_single(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["bookmarks", "unarchive", "100001"])
        assert result.exit_code == 0
        assert "Unarchived bookmark 100001" in result.stdout
        mock_client.unarchive_bookmark.assert_called_once_with(100001)

    @patch("instapyper.cli.get_client")
    def test_unarchive_multiple(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["bookmarks", "unarchive", "100001", "100002"])
        assert result.exit_code == 0
        assert "Unarchived 1/2" in result.stdout
        assert "Unarchived 2/2" in result.stdout


class TestBookmarksMove:
    """Tests for bookmarks move command."""

    @patch("instapyper.cli._resolve_folder")
    @patch("instapyper.cli.get_client")
    def test_move_single(self, mock_get_client: MagicMock, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_resolve.return_value = 5001

        result = runner.invoke(app, ["bookmarks", "move", "100001", "-F", "5001"])
        assert result.exit_code == 0
        assert "Moved bookmark 100001" in result.stdout
        mock_client.move_bookmark.assert_called_once_with(100001, 5001)

    @patch("instapyper.cli._resolve_folder")
    @patch("instapyper.cli.get_client")
    def test_move_by_folder_name(self, mock_get_client: MagicMock, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_resolve.return_value = 5001

        result = runner.invoke(app, ["bookmarks", "move", "100001", "-F", "Tech"])
        assert result.exit_code == 0
        mock_resolve.assert_called_once_with(mock_client, "Tech")

    @patch("instapyper.cli._resolve_folder")
    @patch("instapyper.cli.get_client")
    def test_move_multiple(self, mock_get_client: MagicMock, mock_resolve: MagicMock) -> None:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_resolve.return_value = 5001

        result = runner.invoke(app, ["bookmarks", "move", "100001", "100002", "-F", "5001"])
        assert result.exit_code == 0
        assert "Moved 1/2" in result.stdout
        assert "Moved 2/2" in result.stdout


class TestFoldersList:
    """Tests for folders list command."""

    @patch("instapyper.cli.get_client")
    def test_list_empty(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.get_folders.return_value = []
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["folders", "list"])
        assert result.exit_code == 0
        assert "No folders found" in result.stdout

    @patch("instapyper.cli.get_client")
    def test_list_with_folders(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_folder = MagicMock()
        mock_folder.folder_id = 5001
        mock_folder.title = "Tech"
        mock_folder.slug = "tech"
        mock_folder.position = 0
        mock_client.get_folders.return_value = [mock_folder]
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["folders", "list"])
        assert result.exit_code == 0
        assert "5001" in result.stdout
        assert "Tech" in result.stdout

    @patch("instapyper.cli.get_client")
    def test_list_json_output(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_folder = MagicMock()
        mock_folder.folder_id = 5001
        mock_folder.title = "Tech"
        mock_folder.slug = "tech"
        mock_folder.position = 0
        mock_client.get_folders.return_value = [mock_folder]
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["folders", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["folder_id"] == 5001


class TestFoldersCreate:
    """Tests for folders create command."""

    @patch("instapyper.cli.get_client")
    def test_create_folder(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_folder = MagicMock()
        mock_folder.folder_id = 5003
        mock_folder.title = "New Folder"
        mock_client.create_folder.return_value = mock_folder
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["folders", "create", "New Folder"])
        assert result.exit_code == 0
        assert "Created folder: New Folder" in result.stdout
        assert "ID: 5003" in result.stdout


class TestFoldersDelete:
    """Tests for folders delete command."""

    @patch("instapyper.cli.get_client")
    def test_delete_with_force(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["folders", "delete", "5001", "--force"])
        assert result.exit_code == 0
        assert "Deleted folder 5001" in result.stdout
        mock_client.delete_folder.assert_called_once_with(5001)

    def test_delete_dry_run(self) -> None:
        result = runner.invoke(app, ["folders", "delete", "5001", "--dry-run"])
        assert result.exit_code == 0
        assert "Dry run" in result.stdout
        assert "5001" in result.stdout


class TestResolveFolderHelper:
    """Tests for _resolve_folder helper function."""

    @patch("instapyper.cli.err_console")
    def test_resolve_numeric_id(self, mock_console: MagicMock) -> None:
        from instapyper.cli import _resolve_folder

        mock_client = MagicMock()
        result = _resolve_folder(mock_client, "5001")
        assert result == 5001
        mock_client.get_folders.assert_not_called()

    @patch("instapyper.cli.err_console")
    def test_resolve_by_name(self, mock_console: MagicMock) -> None:
        from instapyper.cli import _resolve_folder

        mock_client = MagicMock()
        mock_folder = MagicMock()
        mock_folder.folder_id = 5001
        mock_folder.title = "Tech"
        mock_folder.slug = "tech"
        mock_client.get_folders.return_value = [mock_folder]

        result = _resolve_folder(mock_client, "Tech")
        assert result == 5001

    @patch("instapyper.cli.err_console")
    def test_resolve_by_slug(self, mock_console: MagicMock) -> None:
        from instapyper.cli import _resolve_folder

        mock_client = MagicMock()
        mock_folder = MagicMock()
        mock_folder.folder_id = 5001
        mock_folder.title = "Tech Articles"
        mock_folder.slug = "tech"
        mock_client.get_folders.return_value = [mock_folder]

        result = _resolve_folder(mock_client, "tech")
        assert result == 5001

    @patch("instapyper.cli.err_console")
    def test_resolve_not_found(self, mock_console: MagicMock) -> None:
        from click.exceptions import Exit

        from instapyper.cli import _resolve_folder

        mock_client = MagicMock()
        mock_client.get_folders.return_value = []

        with pytest.raises(Exit):
            _resolve_folder(mock_client, "NonExistent")


class TestGlobalFlags:
    """Tests for global flags."""

    def test_no_color_flag(self) -> None:
        result = runner.invoke(app, ["--no-color", "--help"])
        assert result.exit_code == 0

    def test_quiet_flag(self) -> None:
        result = runner.invoke(app, ["--quiet", "--help"])
        assert result.exit_code == 0

    def test_debug_flag(self) -> None:
        result = runner.invoke(app, ["--debug", "--help"])
        assert result.exit_code == 0


class TestCompletion:
    """Tests for completion command."""

    def test_completion_invalid_shell(self) -> None:
        result = runner.invoke(app, ["completion", "invalid"])
        assert result.exit_code == 2
        assert "Unknown shell" in result.stderr
