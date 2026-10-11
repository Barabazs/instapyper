# instapyper

Python wrapper for the Instapaper Full API (sync + async clients + Typer CLI). Published to PyPI.

## Commands

```bash
uv sync --group dev --all-extras   # install (CLI + keyring extras needed for tests)
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run ty check .                  # type checker is astral ty, not mypy
```

## Architecture

- `instapyper/client.py` — sync client (`requests-oauthlib`)
- `instapyper/async_client.py` — async client (`httpx` + `authlib`) **plus** the async model twins (`AsyncBookmark`, `AsyncFolder`, `AsyncHighlight`)
- `instapyper/models.py` — sync dataclass models; lazy `html`/`text` properties call `_get_bookmark_text`, which returns `""` on failure by contract
- `instapyper/cli.py` — Typer CLI (`instapyper` entry point); credentials resolve env vars → config file → keyring

## Sync/async duplication is deliberate

Model parsing and method logic are intentionally duplicated between `models.py` and
`async_client.py`. Any change to one side must be mirrored on the other —
`tests/test_model_parity.py` runs identical payloads through both and fails on drift.

## Instapaper API quirks (verified against live API 2026-07-27)

- Bookmark booleans are strings (`"0"`/`"1"`); folder booleans are ints; tags arrive as
  rich dicts (sometimes plain strings); fields may be `null` instead of omitted.
- Most errors arrive inside HTTP 200 bodies as `{"type": "error", "error_code": …}` items;
  1040 = rate limit, 1041 = auth.
- `bookmarks/get_text` returns raw HTML, not JSON. All endpoints are POST.

## Testing

Sync mocks use `responses`; async uses `pytest-httpx`. `asyncio_mode = "auto"` — no
`@pytest.mark.asyncio` needed.

## Releasing

- Version lives only in `instapyper/__init__.py` (hatch dynamic version).
- Stays on 0.0.x; breaking changes ship as patch bumps (`feat!` → patch).
- Publishing: bump version → tag + publish a GitHub release → workflow builds and publishes
  to PyPI via OIDC trusted publishing. `uv lock --check` runs first, so keep the lockfile fresh.
