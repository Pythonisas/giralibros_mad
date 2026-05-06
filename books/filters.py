import datetime
import re
from markupsafe import Markup, escape


def timeago(dt):
    """Jinja2 filter: convert a datetime to a human-readable relative string."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    delta = datetime.datetime.now(datetime.timezone.utc) - dt

    if delta < datetime.timedelta(seconds=60):
        return f"{delta.seconds}s"
    elif delta < datetime.timedelta(hours=1):
        return f"{delta.seconds // 60}m"
    elif delta < datetime.timedelta(days=1):
        return f"{delta.seconds // 60 // 60}h"
    elif delta < datetime.timedelta(days=8):
        return f"{delta.days}d"
    elif delta < datetime.timedelta(days=365):
        return f"{dt.day}/{dt.month}"
    return f"{dt.day}/{dt.month}/{dt.year}"


def isoformat(dt):
    """Jinja2 filter: return ISO 8601 string."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.isoformat()


def month_year(dt):
    """Jinja2 filter: return 'Month YYYY' in Spanish."""
    if dt is None:
        return ""
    months = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
               "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    return f"{months[dt.month - 1]} {dt.year}"


def linebreaksbr(text):
    """Jinja2 filter: convert newlines to <br>."""
    if not text:
        return Markup("")
    return Markup(str(escape(text)).replace("\n", "<br>\n"))


def linebreaks(text):
    """Jinja2 filter: wrap paragraphs in <p>, single newlines to <br>."""
    if not text:
        return Markup("")
    paragraphs = re.split(r"\n\n+", str(text))
    result = []
    for para in paragraphs:
        para = Markup(str(escape(para)).replace("\n", "<br>\n"))
        result.append(Markup(f"<p>{para}</p>"))
    return Markup("\n".join(result))


def urlize_filter(text):
    """Jinja2 filter: convert URLs to clickable links."""
    if not text:
        return Markup("")
    pattern = re.compile(r"(https?://[^\s<>\"']+)", re.IGNORECASE)
    escaped = str(escape(text))
    result = pattern.sub(lambda m: f'<a href="{m.group(1)}" rel="nofollow">{m.group(1)}</a>', escaped)
    return Markup(result)
