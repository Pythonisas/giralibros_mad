# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Giralibros is a Flask-based book exchange platform where users can offer books for exchange and request books from other users. The system includes location-based filtering (focused on Buenos Aires areas) and manages exchange requests between users.

## Development Commands

**Note**: This project uses `uv` for dependency management. All Python commands should be run with `uv run` prefix.

The most important commands are specified in a Makefile. Use the makefile as documentation but NEVER run make commands directly.

## Architecture

The app uses the Flask application factory pattern:

- **`app.py`**: `create_app()` factory — wires extensions, registers the blueprint, registers Jinja2 filters
- **`extensions.py`**: singleton extension instances (`db`, `login_manager`, `mail`, `migrate`)
- **`config.py`**: `DevelopmentConfig`, `TestingConfig`, `ProductionConfig` — selected via `FLASK_ENV`
- **`books/views.py`**: single Blueprint (`views`) containing all routes
- **`books/models.py`**: SQLAlchemy models and query helper functions
- **`books/forms.py`**: Flask-WTF forms
- **`books/filters.py`**: custom Jinja2 filters registered in `create_app()`
- **`books/admin_views.py`**: Flask-Admin configuration
- **`books/templates/`**: all Jinja2 templates

## Flask Configuration

- **Database**: SQLite (`db.sqlite3`) via Flask-SQLAlchemy
- **Python Version**: >= 3.12
- **Flask Version**: >= 3.1
- **Key extensions**: Flask-SQLAlchemy, Flask-Login, Flask-WTF, Flask-Mail, Flask-Migrate, Flask-Admin
- **Config selection**: `FLASK_ENV` environment variable (`development` / `testing` / `production`; defaults to `development`)
- **Admin interface**: Flask-Admin at `/admin/`
- **Migrations**: Flask-Migrate (`uv run flask db migrate` / `uv run flask db upgrade`)

## Testing Philosophy

### Core Principles

The goal of testing is to **catch bugs and prevent regressions**. Tests should focus on observable behavior that matters to users, not implementation details.

### Preferred Testing Approach

1. **Favor integration tests over unit tests**: Test Flask views with real HTTP requests and database interactions using pytest + pytest-flask (`conftest.py` provides `app`, `client`, `db_cleanup`, and `outbox` fixtures)
2. **Test business logic through behavior**: Focus on meaningful user actions (creating exchange requests, filtering by location, reserving books) rather than testing individual model methods in isolation
3. **Use the real database**: Never mock SQLAlchemy or the database; use the in-memory SQLite test database configured in `TestingConfig`
4. **Minimize mocking**: Only mock external services (email, third-party APIs). Don't mock internal collaborators or model relationships
5. **Keep tests simple**: Use helper functions to reduce duplication, but avoid complex test abstractions or frameworks

### What to Test

- **Critical business flows**: Exchange request creation, location-based filtering, book reservation logic
- **Edge cases**: Handling deleted books in exchange requests, user deletion with SET_NULL, location overlap scenarios
- **Simple models**: Test through views/integration tests rather than isolated unit tests

### What NOT to Test

- Flask framework behavior (URL routing, SQLAlchemy ORM functionality)
- Simple CRUD operations without business logic
- Implementation details (internal method calls, private functions)
- Every single code path (coverage is informative, not a target)

### Test Implementation Rules (for AI assistants)

When working with tests:
- **Don't add new test cases** unless explicitly requested
- **Skip incomplete test specifications**: If a test has placeholders like "FIXME human to provide spec", skip implementing it
- **Don't skip tests**: Run the full test suite; don't use markers to skip failing tests
- **Discuss before adjusting code for tests**: If a test requires changing production code, discuss the approach first rather than immediately modifying the code to make tests pass
- **Use docstrings**: Every test method should have a one-sentence docstring explaining the use case or business rule being tested (e.g., "Test that a user is redirected to profile setup on first login")
- **Propose tests for new business logic**: When adding new features with business rules, propose test cases (with FIXME placeholders for specs) for the human to review and fill in, but don't implement them without permission
- **No direct database access in client tests**: Tests using the Flask test client should only check observable application behavior (status codes, redirects, response content, outbound emails). Don't directly access the database to verify state (e.g., `User.query.filter_by(...)`, checking model attributes). The only exception is helper methods with explicit FIXME notes for temporary workarounds.

## Code Style

### Comments and Docstrings

1. **No redundant comments**: Don't write comments that simply restate what the code does. Comments should explain *why*, not *what*.
2. **Function docstrings**:
   - Considered part of the public interface
   - Should be succinct and focus on behavior
   - Don't duplicate information already in the function signature
   - Don't refer to implementation details—describe what callers care about
   - Example: Instead of "Renders both .txt and .html versions of the template and sends a multipart email", write "Send multipart email with HTML and plain text versions"
3. Assume files are read top-bottom and preserve readability in this context: helper functions should be prefixed with _ and go to:
  a. the bottom of the file if they are to be used by multiple unrelated functions
  b. right next to the functions/methods that called them if it's not a general purpose helper but a snippet of code extraction.
4. Modules should be deep---this applies to python module files, classes and functions/methods. don't break functions into smaller ones unless there's a good reason for it (e.g. immediate need to reuse)

## Frontend & Styling

- **CSS Framework**: Bulma (https://bulma.io/documentation/)
- **Icons**: FontAwesome
- **JavaScript**: Vanilla JS (no frameworks)

### Styling Rules (CRITICAL - Read Carefully)

**Default to Bulma first, custom CSS as last resort.**

Before adding ANY custom CSS or inline styles, you MUST:

1. **Check Bulma's utility classes first**:
   - Layout: `is-flex`, `is-justify-content-*`, `is-align-items-*`, `columns`, `is-centered`
   - Sizing: `is-size-1` through `is-size-7` (controls font-size, which scales em-based components)
   - Spacing: `m-*`, `p-*`, `mt-*`, `mb-*`, etc.
   - Display: `is-hidden-*`, `is-block`, `is-inline-block`
   - Text: `has-text-centered`, `has-text-weight-*`, `has-text-*` (colors)

2. **Check Bulma's components**: Most UI patterns already exist (`.loader`, `.button`, `.card`, `.modal`, `.navbar`, `.tag`, etc.)

3. **Bulma components are styled via their container's font-size**: Many Bulma elements (like `.loader`) use `em` units and scale automatically when you change the parent's `font-size` or add `is-size-*` classes. Don't reinvent animations or create custom sized versions.

4. **Only add custom CSS when**:
   - Bulma truly doesn't provide the functionality
   - You've verified this by checking the documentation
   - The custom style is project-specific (not a general layout/spacing concern)

**Examples of what NOT to do**:
- ❌ Creating a `.loader-large` class with custom animation when you can use `<div class="is-size-1"><span class="loader"></span></div>`
- ❌ Adding `margin: 0 auto` when Bulma's `is-flex is-justify-content-center` exists
- ❌ Custom width/height CSS when Bulma's spacing or sizing classes work
- ❌ Writing custom animations that Bulma already includes
- ❌ Adding spacing utilities (`m-*`, `p-*`, `mb-3`, etc.) to every element when Bulma components already have sensible default spacing

**Spacing utility classes (m-*, p-*, etc.)**:
- Bulma components (`.card`, `.box`, `.section`, `.navbar-item`, etc.) already include appropriate default spacing
- Only add spacing utilities when you have a specific reason to override defaults
- Don't pepper every tag with spacing classes for basic layouts
- Ask yourself: "Why does this need different spacing than Bulma's default?"

**When you propose a styling solution**: Always explain which Bulma classes you're using and why. If you're adding custom CSS or spacing overrides, explain why Bulma's defaults don't work.
