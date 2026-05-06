# GiraLibros

GiraLibros is a free book trading application for the Buenos Aires local area.

The application uses Django, SQLite, and Bulma. It was implemented entirely via Chat-Oriented Programming with Claude Code.

The development process is detailed in [this blog post](https://olano.dev/blog/agents2).

![](giralibros.png)

## Running locally

**1. Install dependencies**
```bash
uv sync
```

**2. Set up the database**
```bash
uv run flask db upgrade
```

**3. Run the dev server**
```bash
FLASK_ENV=development uv run flask run
```

The app will be at `http://127.0.0.1:5000`.

**Other useful commands:**

```bash
# Run tests
uv run pytest books/tests.py

# Open a Flask shell
uv run flask shell

# Open the SQLite database directly
sqlite3 -cmd ".open db.sqlite3"
```

> **Prerequisites:** [`uv`](https://docs.astral.sh/uv/) must be installed. Python 3.12+ is required (uv handles this automatically).
