# Running the Test Suite

## Prerequisites

This project uses `uv` for dependency management. Make sure it is installed.

## Run all tests

```bash
uv run pytest books/tests.py -q
```

Expected output: **45 passed, 3 skipped** (skipped tests have `FIXME` placeholders awaiting specs).

## Run a specific test class

```bash
uv run pytest books/tests.py::TestUserViews -q
uv run pytest books/tests.py::TestBooksViews -q
uv run pytest books/tests.py::TestBooksPagination -q
uv run pytest books/tests.py::TestBookCover -q
```

## Run a single test

```bash
uv run pytest books/tests.py::TestBooksViews::test_request_book_exchange -q
```

## Run with verbose output

```bash
uv run pytest books/tests.py -v
```

## Run with log output (useful for debugging email/file errors)

```bash
uv run pytest books/tests.py -q --log-cli-level=ERROR
```

## Test configuration

Tests run against an in-memory SQLite database (configured in `config.py` `TestingConfig`).
Email is captured in memory — no real emails are sent.
The `FLASK_ENV=testing` environment variable is set automatically by `conftest.py`.

## Before running: apply migrations (only needed for a fresh DB)

```bash
uv run flask db upgrade
```
