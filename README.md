# instapyper

Modern Python wrapper for the [Instapaper Full API](https://www.instapaper.com/api).

## Features

- Full type hints (PEP 561 compliant)
- Both sync and async clients
- Python 3.10+
- All API endpoints supported including `update_read_progress` and `set_folder_order`

## Installation

```bash
pip install instapyper
# or
uv add instapyper
```

## Usage

### Sync Client

```python
from instapyper import Instapaper

client = Instapaper(consumer_key, consumer_secret)
client.login(username, password)

# Get bookmarks
bookmarks = client.get_bookmarks(limit=10)
for bookmark in bookmarks:
    print(bookmark.title, bookmark.url)

# Add a bookmark
bookmark = client.add_bookmark("https://example.com")

# Star/archive/move
bookmark.star()
bookmark.archive()
bookmark.move(folder_id=12345)

# Get folders
folders = client.get_folders()
```

### Async Client

```python
from instapyper import AsyncInstapaper

async with AsyncInstapaper(consumer_key, consumer_secret) as client:
    await client.login(username, password)

    bookmarks = await client.get_bookmarks(limit=10)
    for bookmark in bookmarks:
        print(bookmark.title)
        await bookmark.star()
```

### Reusing OAuth Tokens

```python
# After login, save tokens for reuse
client.login(username, password)
token = client.oauth_token
secret = client.oauth_token_secret

# Later, login with saved tokens (no password needed)
from instapyper import Instapaper
client = Instapaper(consumer_key, consumer_secret)
client.login_with_token(token, secret)
```

## CLI

```bash
pip install instapyper[cli]

instapyper login
instapyper bookmarks list
instapyper bookmarks add https://example.com --tags "tech,ai"
instapyper bookmarks archive 12345 67890
instapyper folders list
instapyper cheatsheet  # more examples
```

## API Coverage

100% coverage of the [Instapaper Full API](https://www.instapaper.com/api) as of January 2026.

## Built With

Built with [Claude Code](https://claude.ai/code) (Claude Opus 4.5).

## License

MIT
