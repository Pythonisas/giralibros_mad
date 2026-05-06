import io
import pytest
from app import create_app
from extensions import db as _db, mail as _mail
from books.models import OfferedBook, User, UserLocation, UserProfile, WantedBook


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


@pytest.fixture(scope="function", autouse=True)
def db_cleanup(app):
    """Roll back database changes after each test."""
    with app.app_context():
        yield
        _db.session.remove()
        # Clear all data between tests
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture(scope="function")
def outbox():
    """Capture all emails sent during the test."""
    with _mail.record_messages() as _outbox:
        yield _outbox


def make_user(username="testuser", email=None, password="testpass123",
              is_active=True, is_staff=False):
    """Helper: create and persist a User with a UserProfile."""
    if email is None:
        email = f"{username}@example.com"
    user = User(username=username, email=email, is_active=is_active, is_staff=is_staff)
    user.set_password(password)
    _db.session.add(user)
    _db.session.flush()
    profile = UserProfile(user_id=user.id, contact_email=email)
    _db.session.add(profile)
    _db.session.commit()
    return user


def login(client, email_or_username, password):
    """Helper: POST to /login/ with credentials."""
    return client.post(
        "/login/",
        data={"email": email_or_username, "password": password},
        follow_redirects=True,
    )


def make_image_file(name="test.jpg", size=(10, 10)):
    """Helper: create a minimal in-memory JPEG file."""
    from PIL import Image

    buf = io.BytesIO()
    img = Image.new("RGB", size, color=(255, 0, 0))
    img.save(buf, "JPEG")
    buf.seek(0)
    buf.name = name
    return buf
