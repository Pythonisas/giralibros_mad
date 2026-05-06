# Improvement Plan: Flask Codebase

This plan addresses the security vulnerabilities, behavioral regressions, bugs, and performance issues
identified in the code review of the Django-to-Flask migration.

---

## Priority 1 — Critical Security

### 1a. Initialize CSRFProtect for AJAX endpoints
**Files**: `extensions.py`, `app.py`, `books/templates/base_logged.html`

Add a `CSRFProtect` instance to `extensions.py` and call `csrf.init_app(app)` inside `create_app()`.
In `base_logged.html`, change `{{ csrf_token }}` → `{{ csrf_token() }}` (Flask-WTF exposes it as a
callable). All AJAX `X-CSRFToken` headers will then carry a validated token.

### 1b. Fix open redirect in `login()`
**File**: `books/views.py`

After reading `next_url = request.args.get("next")`, validate it is a relative URL pointing to the
same host before redirecting. Use `urllib.parse.urlparse` to compare netloc, falling back to
`url_for("views.list_books")` on failure.

### 1c. Fix path traversal in file deletion
**File**: `books/models.py` (or `books/views.py`, wherever `_remove_cover_file`/`_delete_media_file` live)

Replace the `startswith(media_folder)` string check with an `os.path.abspath` comparison on both
sides, including the `os.sep` suffix guard:
```python
abs_media = os.path.abspath(media_folder)
abs_path  = os.path.abspath(os.path.join(media_folder, filename))
if abs_path.startswith(abs_media + os.sep):
    os.remove(abs_path)
```

---

## Priority 2 — Bugs

### 2a. Wire up Flask-Admin
**File**: `app.py`

Call `init_admin(app)` from `books/admin_views.py` inside `create_app()` before returning the app.

### 2b. Add `ondelete` constraints to `ExchangeRequest`
**File**: `books/models.py`, new migration

- `from_user_id` FK: add `ondelete="CASCADE"`
- `to_user_id` FK: add `ondelete="SET NULL"`
- `offered_book_id` FK: add `ondelete="SET NULL"`

Generate a new migration: `uv run flask db migrate -m "fix exchange request ondelete constraints"`.

### 2c. Move `db.session.commit()` out of model methods
**Files**: `books/models.py`, `books/views.py`

Remove `db.session.commit()` from `OfferedBook.delete()`, `trade()`, `reserve()`, and
`toggle_like()`. Update each call site in `views.py` to commit after the model method returns.
This restores proper unit-of-work control and prevents partial state from mid-flight commits.

### 2d. Fix `db.func.max` → `db.func.greatest`
**File**: `books/models.py` (`get_books_for_user` ordering expression)

`db.func.max(col1, col2)` is the aggregate `MAX()`, not `GREATEST()`. Replace with
`db.func.greatest(col1, col2)`. Works correctly across all SQL backends.

### 2e. Restore `like_book` guards
**File**: `books/views.py`

Re-add:
1. Ownership check — reject if `book.user_id == current_user.id`.
2. Availability check — fetch via `OfferedBook.query.filter_by(id=book_id, status=BookStatus.AVAILABLE)`
   instead of `db.session.get(OfferedBook, book_id)`.

### 2f. Fix `request_exchange` atomicity
**File**: `books/views.py`

Move `db.session.commit()` to after the email send. Use `db.session.flush()` inside the try block
to assign an ID to the new `ExchangeRequest` without committing, commit only on email success, and
let the session roll back naturally on failure (no explicit delete needed).

---

## Priority 3 — Regressions

### 3a. Restore `about` page stats
**Files**: `books/views.py`, `books/templates/about.html` (if needed)

Pass live counts to the `about` template and restore `@login_required`:
```python
registered_users = User.query.join(UserProfile).count()
offered_books    = OfferedBook.query.filter_by(status=BookStatus.AVAILABLE).count()
traded_books     = OfferedBook.query.filter_by(status=BookStatus.TRADED).count()
recent_requests  = ExchangeRequest.query.filter(
    ExchangeRequest.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
).count()
```

### 3b. Restore email `reply_to`
**File**: `books/views.py`

In `_send_exchange_request_email`, add `reply_to=[requester.profile.contact_email]` to the
`Message` constructor so replies from the book owner reach the requester's preferred address.

### 3c. Restore EXIF rotation on image upload
**File**: `books/views.py`

In `_save_book_cover` and `_save_profile_picture`, add `img = ImageOps.exif_transpose(img)` after
opening the image and before resizing, so portrait photos taken on mobile display correctly.

### 3d. Add logging on failures
**File**: `books/views.py`

Replace silent `except Exception: pass` blocks in `_save_book_cover`, `_save_profile_picture`, and
the email send path with `current_app.logger.exception("...")` so errors are visible in production
logs.

---

## Priority 4 — Performance

### 4a. DB-level pagination in `list_books`
**Files**: `books/models.py`, `books/views.py`

Change `get_books_for_user()` to return a SQLAlchemy `Query` object instead of a fully-materialized
list. In the view, derive the total with `.count()` and fetch the page with `.offset(start).limit(per_page).all()`.
This replaces a full-table Python load on every request with a targeted `LIMIT/OFFSET` query.

---

## Key Files

| File | Changes |
|------|---------|
| `app.py` | Wire `init_admin(app)`, `csrf.init_app(app)` |
| `extensions.py` | Add `CSRFProtect` instance |
| `books/models.py` | `ondelete` constraints, remove model commits, fix `greatest`, return Query from `get_books_for_user` |
| `books/views.py` | Open redirect fix, `like_book` guards, `request_exchange` atomicity, `about` stats, `reply_to`, EXIF, logging, DB pagination |
| `books/templates/base_logged.html` | `{{ csrf_token() }}` (callable) |
| `books/admin_views.py` | No changes; just call `init_admin` from `app.py` |
| `books/migrations/` | New migration for `ondelete` FK changes |

---

## Verification

1. `uv run pytest` — full suite must pass.
2. Visit `/login/?next=https://evil.com` — should land on book list, not the external URL.
3. `curl -X POST /like/1/` without CSRF header — should return 400.
4. Visit `/admin/` as a staff user — Flask-Admin panel should load.
5. Enable SQLAlchemy query logging; verify `list_books` issues `LIMIT/OFFSET`, not a full scan.
6. Upload a portrait photo taken on mobile — should display upright.
7. Visit `/about/` as a logged-in user — stats should show real counts.
