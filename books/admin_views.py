from flask import redirect, url_for
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user

from extensions import db
from books.models import ExchangeRequest, Like, OfferedBook, User, UserLocation, UserProfile, WantedBook


class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_staff

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("views.login"))


def init_admin(app):
    admin = Admin(app, name="GiraLibros Admin", template_mode="bootstrap4")
    admin.add_view(SecureModelView(User, db.session))
    admin.add_view(SecureModelView(UserProfile, db.session))
    admin.add_view(SecureModelView(UserLocation, db.session))
    admin.add_view(SecureModelView(OfferedBook, db.session))
    admin.add_view(SecureModelView(WantedBook, db.session))
    admin.add_view(SecureModelView(Like, db.session))
    admin.add_view(SecureModelView(ExchangeRequest, db.session))
