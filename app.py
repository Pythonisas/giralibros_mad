import os

from flask import Flask

from config import config
from extensions import db, login_manager, mail, migrate
from books.filters import isoformat, linebreaks, linebreaksbr, month_year, timeago, urlize_filter


def create_app(config_name=None):
    app = Flask(__name__, template_folder="books/templates", static_folder="books/static")

    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")
    app.config.from_object(config[config_name])

    # Ensure media folder exists
    media_folder = app.config.get("MEDIA_FOLDER", "media")
    os.makedirs(media_folder, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = "views.login"
    login_manager.login_message = "Por favor iniciá sesión para acceder a esta página."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        from books.models import User
        return db.session.get(User, int(user_id))

    # Register custom Jinja2 filters
    app.jinja_env.filters["timeago"] = timeago
    app.jinja_env.filters["isoformat"] = isoformat
    app.jinja_env.filters["month_year"] = month_year
    app.jinja_env.filters["linebreaksbr"] = linebreaksbr
    app.jinja_env.filters["linebreaks"] = linebreaks
    app.jinja_env.filters["urlize"] = urlize_filter

    from books.views import views as views_blueprint
    app.register_blueprint(views_blueprint)

    return app
