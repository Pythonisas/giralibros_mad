import os
import re
from datetime import datetime, timedelta, timezone

from flask import current_app
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False, index=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(150), default="")
    password_hash = db.Column(db.String(256), nullable=False, default="")
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    is_staff = db.Column(db.Boolean, default=False, nullable=False)
    date_joined = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    profile = db.relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    locations = db.relationship("UserLocation", back_populates="user", cascade="all, delete-orphan")
    offered = db.relationship("OfferedBook", back_populates="user", foreign_keys="OfferedBook.user_id")
    wanted = db.relationship("WantedBook", back_populates="user", cascade="all, delete-orphan")
    likes = db.relationship("Like", back_populates="user", cascade="all, delete-orphan")
    sent_requests = db.relationship("ExchangeRequest", back_populates="from_user", foreign_keys="ExchangeRequest.from_user_id")
    received_requests = db.relationship("ExchangeRequest", back_populates="to_user", foreign_keys="ExchangeRequest.to_user_id")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class UserProfile(db.Model):
    __tablename__ = "user_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    contact_email = db.Column(db.String(254), nullable=False)
    alternate_contact = db.Column(db.String(200), default="")
    about = db.Column(db.Text, default="")
    profile_picture = db.Column(db.String(500), nullable=True)

    user = db.relationship("User", back_populates="profile")

    @property
    def profile_picture_url(self):
        if self.profile_picture:
            return f"/media/{self.profile_picture}"
        return None


class LocationArea:
    CABA_CENTRO = "CABA_CENTRO"
    CABA_SUR = "CABA_SUR"
    CABA_NORTE = "CABA_NORTE"
    GBA_NORTE = "GBA_NORTE"
    GBA_OESTE = "GBA_OESTE"
    GBA_SUR = "GBA_SUR"

    choices = [
        ("CABA_CENTRO", "CABA Centro"),
        ("CABA_SUR", "CABA Sur"),
        ("CABA_NORTE", "CABA Norte"),
        ("GBA_NORTE", "GBA Norte"),
        ("GBA_OESTE", "GBA Oeste"),
        ("GBA_SUR", "GBA Sur"),
    ]

    @classmethod
    def display(cls, value):
        return dict(cls.choices).get(value, value)


class BookStatus:
    NEW = "NEW"
    RESERVED = "RESERVED"
    DELETED = "DELETED"
    TRADED = "TRADED"


class UserLocation(db.Model):
    __tablename__ = "user_location"
    __table_args__ = (db.UniqueConstraint("user_id", "area", name="unique_user_area"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    area = db.Column(db.String(20), nullable=False)

    user = db.relationship("User", back_populates="locations")

    def get_area_display(self):
        return LocationArea.display(self.area)

    def __str__(self):
        return f"{self.user.username} - {LocationArea.display(self.area)}"


def _normalize_spanish(text):
    """Normalize text for search: lowercase, remove accents, clean punctuation."""
    text = text.lower()
    for old, new in {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u"}.items():
        text = text.replace(old, new)
    text = text.replace("100", "cien")
    text = re.sub(r"[^\wñ\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class OfferedBook(db.Model):
    __tablename__ = "offered_book"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(200), nullable=False)
    title_normalized = db.Column(db.String(200), index=True, default="")
    author_normalized = db.Column(db.String(200), index=True, default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    notes = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default=BookStatus.NEW, nullable=False)
    status_changed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    cover_image = db.Column(db.String(500), nullable=True)
    cover_uploaded_at = db.Column(db.DateTime, nullable=True)
    likes = db.Column(db.Integer, default=0, nullable=False)

    user = db.relationship("User", back_populates="offered", foreign_keys=[user_id])
    book_likes = db.relationship("Like", back_populates="offered_book", cascade="all, delete-orphan")
    requests = db.relationship("ExchangeRequest", back_populates="offered_book", foreign_keys="ExchangeRequest.offered_book_id")

    @staticmethod
    def normalize_spanish(text):
        return _normalize_spanish(text)

    def _set_normalized(self):
        self.title_normalized = _normalize_spanish(self.title) if self.title else ""
        self.author_normalized = _normalize_spanish(self.author) if self.author else ""

    @property
    def cover_image_url(self):
        if self.cover_image:
            return f"/media/{self.cover_image}"
        return None

    @property
    def last_activity_date(self):
        if self.cover_uploaded_at:
            return max(self.created_at, self.cover_uploaded_at)
        return self.created_at

    @property
    def is_reserved(self):
        return self.status == BookStatus.RESERVED

    @property
    def notes_display(self):
        if self.is_reserved:
            return f"[RESERVADO]\n{self.notes}" if self.notes else "[RESERVADO]"
        return self.notes

    def delete(self):
        """Soft delete: mark as deleted and remove cover image from disk."""
        self._remove_cover_file()
        self.cover_image = None
        self.status = BookStatus.DELETED
        self.status_changed_at = datetime.now(timezone.utc)
        db.session.add(self)
        db.session.commit()

    def trade(self):
        """Mark as traded and remove cover image from disk."""
        self._remove_cover_file()
        self.cover_image = None
        self.status = BookStatus.TRADED
        self.status_changed_at = datetime.now(timezone.utc)
        db.session.add(self)
        db.session.commit()

    def reserve(self):
        """Toggle book reservation status between NEW and RESERVED."""
        if self.status == BookStatus.RESERVED:
            self.status = BookStatus.NEW
        else:
            self.status = BookStatus.RESERVED
        self.status_changed_at = datetime.now(timezone.utc)
        db.session.add(self)
        db.session.commit()

    def add_like(self, user):
        """Create a like from user, incrementing the counter. Silently ignores duplicates."""
        existing = db.session.execute(
            db.select(Like).where(Like.user_id == user.id, Like.offered_book_id == self.id)
        ).scalar_one_or_none()
        if existing is None:
            db.session.add(Like(user_id=user.id, offered_book_id=self.id))
            db.session.execute(
                db.update(OfferedBook).where(OfferedBook.id == self.id).values(likes=OfferedBook.likes + 1)
            )

    def toggle_like(self, user):
        """Toggle like from user. Returns True if now liked, False if unliked."""
        existing = db.session.execute(
            db.select(Like).where(Like.user_id == user.id, Like.offered_book_id == self.id)
        ).scalar_one_or_none()
        if existing is None:
            db.session.add(Like(user_id=user.id, offered_book_id=self.id))
            db.session.execute(
                db.update(OfferedBook).where(OfferedBook.id == self.id).values(likes=OfferedBook.likes + 1)
            )
            db.session.commit()
            return True
        else:
            db.session.delete(existing)
            db.session.execute(
                db.update(OfferedBook).where(OfferedBook.id == self.id, OfferedBook.likes > 0).values(likes=OfferedBook.likes - 1)
            )
            db.session.commit()
            return False

    def _remove_cover_file(self):
        if self.cover_image:
            try:
                media_folder = current_app.config.get("MEDIA_FOLDER", "media")
                file_path = os.path.normpath(os.path.join(media_folder, self.cover_image))
                if file_path.startswith(media_folder) and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass

    def __str__(self):
        return f"OfferedBook({self.title}, {self.author})"


class WantedBook(db.Model):
    __tablename__ = "wanted_book"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), default="")
    author = db.Column(db.String(200), nullable=False)
    title_normalized = db.Column(db.String(200), index=True, default="")
    author_normalized = db.Column(db.String(200), index=True, default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", back_populates="wanted")

    @staticmethod
    def normalize_spanish(text):
        return _normalize_spanish(text)

    def _set_normalized(self):
        self.title_normalized = _normalize_spanish(self.title) if self.title else ""
        self.author_normalized = _normalize_spanish(self.author) if self.author else ""

    def __str__(self):
        return f"WantedBook({self.title}, {self.author})"


class Like(db.Model):
    __tablename__ = "like"
    __table_args__ = (db.UniqueConstraint("user_id", "offered_book_id", name="unique_user_book_like"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    offered_book_id = db.Column(db.Integer, db.ForeignKey("offered_book.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", back_populates="likes")
    offered_book = db.relationship("OfferedBook", back_populates="book_likes")


class ExchangeRequest(db.Model):
    __tablename__ = "exchange_request"

    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    offered_book_id = db.Column(db.Integer, db.ForeignKey("offered_book.id"), nullable=True)
    book_title = db.Column(db.String(200), nullable=False)
    book_author = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    from_user = db.relationship("User", back_populates="sent_requests", foreign_keys=[from_user_id])
    to_user = db.relationship("User", back_populates="received_requests", foreign_keys=[to_user_id])
    offered_book = db.relationship("OfferedBook", back_populates="requests", foreign_keys=[offered_book_id])


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_available_books():
    """Return a select statement for books that are not deleted or traded."""
    return db.select(OfferedBook).where(
        OfferedBook.status.notin_([BookStatus.DELETED, BookStatus.TRADED])
    )


def get_traded_by(user):
    """Return traded books for a user, ordered by most recent first."""
    return db.session.execute(
        db.select(OfferedBook)
        .where(OfferedBook.user_id == user.id, OfferedBook.status == BookStatus.TRADED)
        .order_by(OfferedBook.status_changed_at.desc())
    ).scalars().all()


def get_books_for_user(user, search=None, wanted=False, photo=False, my_locations=False):
    """Return books available to the user with all filters applied."""
    stmt = get_available_books().join(User, OfferedBook.user_id == User.id)

    if getattr(user, "is_authenticated", False) and my_locations:
        user_areas = [loc.area for loc in user.locations]
        stmt = (
            stmt.join(UserLocation, User.id == UserLocation.user_id)
            .where(UserLocation.area.in_(user_areas))
            .distinct()
        )

    if search:
        normalized = _normalize_spanish(search)
        for word in normalized.split():
            stmt = stmt.where(
                db.or_(
                    OfferedBook.title_normalized.ilike(f"%{word}%"),
                    OfferedBook.author_normalized.ilike(f"%{word}%"),
                )
            )

    if wanted and getattr(user, "is_authenticated", False):
        wanted_books = db.session.execute(
            db.select(WantedBook).where(WantedBook.user_id == user.id)
        ).scalars().all()

        if not wanted_books:
            return []

        conditions = []
        for wb in wanted_books:
            if wb.title_normalized:
                conditions.append(db.and_(
                    OfferedBook.title_normalized.ilike(f"%{wb.title_normalized}%"),
                    OfferedBook.author_normalized.ilike(f"%{wb.author_normalized}%"),
                ))
            else:
                conditions.append(OfferedBook.author_normalized.ilike(f"%{wb.author_normalized}%"))

        stmt = stmt.where(db.or_(*conditions)).where(OfferedBook.user_id != user.id).distinct()

    if photo:
        stmt = stmt.where(OfferedBook.cover_image.isnot(None), OfferedBook.cover_image != "")

    last_activity = db.func.max(
        OfferedBook.created_at,
        db.func.coalesce(OfferedBook.cover_uploaded_at, OfferedBook.created_at),
    )
    stmt = stmt.order_by(last_activity.desc())

    books = db.session.execute(stmt).scalars().all()
    _annotate_books(books, user)
    return books


def get_books_for_profile(profile_user, viewing_user):
    """Return books for a profile page."""
    stmt = (
        get_available_books()
        .where(OfferedBook.user_id == profile_user.id)
        .order_by(OfferedBook.created_at.desc())
    )
    books = db.session.execute(stmt).scalars().all()
    viewing_id = getattr(viewing_user, "id", None)
    if viewing_id != profile_user.id:
        _annotate_books(books, viewing_user)
    return books


def get_recent_sent_requests(user, limit=10):
    """Return recent exchange requests sent by a user, most recent first."""
    return db.session.execute(
        db.select(ExchangeRequest)
        .where(ExchangeRequest.from_user_id == user.id)
        .order_by(ExchangeRequest.created_at.desc())
        .limit(limit)
    ).scalars().all()


def get_recent_received_requests(user, limit=10):
    """Return recent exchange requests received by a user, most recent first."""
    return db.session.execute(
        db.select(ExchangeRequest)
        .where(ExchangeRequest.to_user_id == user.id)
        .order_by(ExchangeRequest.created_at.desc())
        .limit(limit)
    ).scalars().all()


def _annotate_books(books, user):
    """Attach already_requested and already_liked as Python attributes on each book."""
    if not books:
        return

    if getattr(user, "is_authenticated", False):
        expiry_days = current_app.config.get("EXCHANGE_REQUEST_EXPIRY_DAYS", 15)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=expiry_days)
        book_ids = [b.id for b in books]

        requested_ids = set(
            db.session.execute(
                db.select(ExchangeRequest.offered_book_id).where(
                    ExchangeRequest.from_user_id == user.id,
                    ExchangeRequest.offered_book_id.in_(book_ids),
                    ExchangeRequest.created_at >= cutoff_date,
                )
            ).scalars().all()
        )

        liked_ids = set(
            db.session.execute(
                db.select(Like.offered_book_id).where(
                    Like.user_id == user.id,
                    Like.offered_book_id.in_(book_ids),
                )
            ).scalars().all()
        )

        for book in books:
            book.already_requested = book.id in requested_ids
            book.already_liked = book.id in liked_ids
    else:
        for book in books:
            book.already_requested = False
            book.already_liked = False
