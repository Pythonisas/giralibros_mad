import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///db.sqlite3")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True") == "True"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = "GiraLibros <noreply@giralibros.com>"
    MAIL_SUPPRESS_SEND = False
    MEDIA_FOLDER = os.environ.get("MEDIA_FOLDER", "media")
    EXCHANGE_REQUEST_EXPIRY_DAYS = 15
    EXCHANGE_REQUEST_DAILY_LIMIT = 25
    BOOKS_PER_PAGE = 20
    BOOK_COVER_MAX_SIZE = 10 * 1024 * 1024
    BOOK_COVER_ALLOWED_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    BOOK_COVER_THUMBNAIL_MAX_WIDTH = 400
    BOOK_COVER_THUMBNAIL_MAX_HEIGHT = 600
    BOOK_COVER_JPEG_QUALITY = 85
    PROFILE_PICTURE_MAX_SIZE = 5 * 1024 * 1024
    PROFILE_PICTURE_ALLOWED_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    PROFILE_PICTURE_MAX_DIMENSION = 300
    PROFILE_PICTURE_JPEG_QUALITY = 85
    REGISTRATION_ENABLED = True
    HONEYPOT_FIELD_NAME = "website"
    PASSWORD_RESET_MAX_AGE = 3600


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False},
        "poolclass": __import__("sqlalchemy.pool", fromlist=["StaticPool"]).StaticPool,
    }
    MAIL_SUPPRESS_SEND = True
    WTF_CSRF_ENABLED = False
    SERVER_NAME = "localhost"
    MEDIA_FOLDER = "test_media"


class ProductionConfig(Config):
    REGISTRATION_ENABLED = os.environ.get("REGISTRATION_ENABLED", "False") == "True"
    SECRET_KEY = os.environ.get("SECRET_KEY")
    MAIL_SUPPRESS_SEND = False


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
