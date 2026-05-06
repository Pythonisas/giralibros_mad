import os
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from flask_mail import Message
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from extensions import db, mail
from books.forms import (
    LoginForm,
    OfferedBookForm,
    PasswordResetForm,
    PasswordResetRequestForm,
    ProfileEditForm,
    RegistrationForm,
    WantedBookForm,
)
from books.models import (
    BookStatus,
    ExchangeRequest,
    OfferedBook,
    User,
    UserLocation,
    UserProfile,
    WantedBook,
    get_books_for_profile,
    get_books_for_user,
    get_recent_received_requests,
    get_recent_sent_requests,
    get_traded_by,
)

views = Blueprint("views", __name__)


# ---------------------------------------------------------------------------
# Media serving
# ---------------------------------------------------------------------------


@views.route("/media/<path:filename>")
def media(filename):
    media_folder = current_app.config.get("MEDIA_FOLDER", "media")
    return send_from_directory(os.path.abspath(media_folder), filename)


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------


@views.route("/")
def list_books():
    # Redirect to profile setup if authenticated but no locations set
    if current_user.is_authenticated and not current_user.locations:
        return redirect(url_for("views.profile_edit"))

    search = request.args.get("search", "").strip()
    # Detect filter params by presence in query string (value may be empty string)
    wanted = "wanted" in request.args
    photo = "photo" in request.args
    my_locations = "my_locations" in request.args
    page = request.args.get("page", 1, type=int)

    per_page = current_app.config.get("BOOKS_PER_PAGE", 20)
    page = max(1, page)

    total, page_books = get_books_for_user(
        current_user,
        search=search or None,
        wanted=wanted,
        photo=photo,
        my_locations=my_locations,
        page=page,
        per_page=per_page,
    )

    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
        _, page_books = get_books_for_user(
            current_user,
            search=search or None,
            wanted=wanted,
            photo=photo,
            my_locations=my_locations,
            page=page,
            per_page=per_page,
        )

    has_next = page < total_pages
    has_offered = False
    if current_user.is_authenticated:
        has_offered = any(
            b.status == BookStatus.NEW for b in current_user.offered
        )

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if is_ajax:
        html = render_template("_book_list.html", offered_books=page_books)
        return jsonify({
            "html": html,
            "has_next": has_next,
            "next_page": page + 1 if has_next else None,
        })

    return render_template(
        "home.html",
        offered_books=page_books,
        total=total,
        page=page,
        total_pages=total_pages,
        has_next=has_next,
        has_offered=has_offered,
        search=search,
        wanted=wanted,
        photo=photo,
        my_locations=my_locations,
    )


@views.route("/about/")
@login_required
def about():
    registered_users = db.session.execute(
        db.select(db.func.count(User.id)).where(User.profile.has())
    ).scalar()
    offered_books = db.session.execute(
        db.select(db.func.count(OfferedBook.id)).where(OfferedBook.status == BookStatus.NEW)
    ).scalar()
    traded_books = db.session.execute(
        db.select(db.func.count(OfferedBook.id)).where(OfferedBook.status == BookStatus.TRADED)
    ).scalar()
    recent_requests = db.session.execute(
        db.select(db.func.count(ExchangeRequest.id)).where(
            ExchangeRequest.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
        )
    ).scalar()
    return render_template(
        "about.html",
        registered_users=registered_users,
        offered_books=offered_books,
        traded_books=traded_books,
        recent_requests=recent_requests,
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@views.route("/register/", methods=["GET", "POST"])
def register():
    if not current_app.config.get("REGISTRATION_ENABLED", True):
        flash("El registro está deshabilitado.", "warning")
        return redirect(url_for("views.list_books"))

    if current_user.is_authenticated:
        return redirect(url_for("views.list_books"))

    if request.method == "POST" and request.form.get("website"):
        abort(403)

    form = RegistrationForm()
    if form.validate_on_submit():
        username_exists = db.session.execute(
            db.select(User).where(User.username == form.username.data)
        ).scalar_one_or_none()
        email_exists = db.session.execute(
            db.select(User).where(User.email == form.email.data)
        ).scalar_one_or_none()

        if username_exists:
            form.username.errors.append("Este usuario ya está registrado.")
        elif email_exists:
            form.email.errors.append("Este email ya está registrado.")
        else:
            user = User(username=form.username.data, email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.flush()

            profile = UserProfile(user_id=user.id, contact_email=user.email)
            db.session.add(profile)
            db.session.commit()

            _send_verification_email(user)
            return render_template(
                "registration/registration_confirmation.html",
                email=form.email.data,
            )

    return render_template("registration/register.html", form=form)


@views.route("/login/", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("views.list_books"))

    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.email.data.strip()
        user = db.session.execute(
            db.select(User).where(
                db.or_(User.email == identifier, User.username == identifier)
            )
        ).scalar_one_or_none()

        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash("Tu cuenta no está activa. Verificá tu email.", "warning")
                return render_template("registration/login.html", form=form)
            login_user(user, remember=form.remember_me.data)
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            next_url = request.args.get("next") or ""
            return redirect(_safe_next(next_url))
        else:
            flash("Usuario o contraseña incorrectos.", "danger")

    return render_template("registration/login.html", form=form)


@views.route("/logout/", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("views.login"))


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


@views.route("/verify-email/<token>/")
def verify_email(token):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        max_age = 60 * 60 * 24 * 7  # 7 days
        user_id = serializer.loads(token, salt="email-verification", max_age=max_age)
    except (SignatureExpired, BadSignature):
        flash("El enlace de verificación es inválido o ha expirado.", "danger")
        return redirect(url_for("views.list_books"))

    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    user.is_active = True
    db.session.commit()
    flash("¡Tu email fue verificado! Ya podés iniciar sesión.", "success")
    return redirect(url_for("views.login"))


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


@views.route("/password-reset/", methods=["GET", "POST"])
def password_reset_request():
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = db.session.execute(
            db.select(User).where(User.email == form.email.data)
        ).scalar_one_or_none()
        if user:
            _send_password_reset_email(user)
        flash(
            "Si ese email está registrado, recibirás un enlace para restablecer tu contraseña.",
            "info",
        )
        return redirect(url_for("views.password_reset_done"))
    return render_template("registration/password_reset.html", form=form)


@views.route("/password-reset/done/")
def password_reset_done():
    return render_template("registration/password_reset_done.html")


@views.route("/password-reset/<token>/", methods=["GET", "POST"])
def password_reset_confirm(token):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        user_id = serializer.loads(
            token,
            salt="password-reset",
            max_age=current_app.config.get("PASSWORD_RESET_MAX_AGE", 3600),
        )
    except (SignatureExpired, BadSignature):
        flash("El enlace de restablecimiento es inválido o ha expirado.", "danger")
        return redirect(url_for("views.password_reset_request"))

    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    form = PasswordResetForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Contraseña restablecida. Ahora podés iniciar sesión.", "success")
        return redirect(url_for("views.password_reset_complete"))

    return render_template("registration/password_reset_confirm.html", form=form, token=token)


@views.route("/password-reset/complete/")
def password_reset_complete():
    return render_template("registration/password_reset_complete.html")


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


@views.route("/profile/edit/", methods=["GET", "POST"])
@login_required
def profile_edit():
    profile = current_user.profile
    if profile is None:
        profile = UserProfile(user_id=current_user.id, contact_email=current_user.email)
        db.session.add(profile)
        db.session.commit()

    form = ProfileEditForm(obj=profile)
    if request.method == "GET":
        form.locations.data = [loc.area for loc in current_user.locations]

    if form.validate_on_submit():
        if form.website.data:
            return redirect(url_for("views.list_books"))

        # Detect first-time setup (no locations set yet)
        is_first_setup = len(current_user.locations) == 0

        # Update User fields from raw form data
        first_name = request.form.get("first_name", "").strip()
        if first_name:
            current_user.first_name = first_name

        # Contact email: accept either WTForms field or raw "email" input
        contact_email = form.contact_email.data or request.form.get("email", "").strip()
        if contact_email:
            profile.contact_email = contact_email
        profile.alternate_contact = form.alternate_contact.data or request.form.get("alternate_contact", "")
        profile.about = form.about.data or request.form.get("about", "")

        UserLocation.query.filter_by(user_id=current_user.id).delete()
        for area in form.locations.data or []:
            db.session.add(UserLocation(user_id=current_user.id, area=area))

        picture_file = form.profile_picture.data
        if picture_file and picture_file.filename:
            filename = _save_profile_picture(picture_file, current_user.id)
            if filename:
                if profile.profile_picture:
                    _delete_media_file(profile.profile_picture)
                profile.profile_picture = filename

        db.session.commit()
        flash("Perfil actualizado.", "success")
        if is_first_setup:
            return redirect(url_for("views.list_books"))
        return redirect(url_for("views.profile", username=current_user.username))

    return render_template(
        "profile_edit.html",
        form=form,
        profile=profile,
        locations=current_user.locations,
    )


@views.route("/profile/<username>/")
@login_required
def profile(username):
    user = db.session.execute(
        db.select(User).where(User.username == username)
    ).scalar_one_or_none()
    if not user:
        abort(404)

    books = get_books_for_profile(user, current_user)
    traded = get_traded_by(user)
    sent = get_recent_sent_requests(user)
    received = get_recent_received_requests(user)
    has_offered = any(b.status == BookStatus.NEW for b in books)
    is_own_profile = current_user.is_authenticated and current_user.id == user.id

    wanted_books = (
        db.session.execute(
            db.select(WantedBook).where(WantedBook.user_id == user.id).order_by(WantedBook.created_at.desc())
        ).scalars().all()
        if is_own_profile else []
    )

    return render_template(
        "profile.html",
        profile_user=user,
        offered_books=books,
        traded_books=traded,
        sent_requests=sent,
        received_requests=received,
        has_offered=has_offered,
        is_own_profile=is_own_profile,
        wanted_books=wanted_books,
        traded_books_count=len(traded),
        books_per_page=current_app.config.get("BOOKS_PER_PAGE", 20),
    )


# ---------------------------------------------------------------------------
# Offered books
# ---------------------------------------------------------------------------


@views.route("/my-books/", methods=["GET", "POST"])
@login_required
def my_offered_books():
    editing_book = None
    book_id = request.args.get("book_id", type=int)
    if book_id:
        editing_book = db.session.get(OfferedBook, book_id)
        if editing_book and editing_book.user_id != current_user.id:
            abort(403)

    form = OfferedBookForm(obj=editing_book)

    if form.validate_on_submit():
        if book_id and editing_book:
            editing_book.title = form.title.data
            editing_book.author = form.author.data
            editing_book.notes = form.notes.data
            editing_book._set_normalized()

            cover_file = form.cover_image.data
            if cover_file and cover_file.filename:
                filename = _save_book_cover(cover_file, editing_book.id)
                if filename:
                    if editing_book.cover_image:
                        _delete_media_file(editing_book.cover_image)
                    editing_book.cover_image = filename
                    editing_book.cover_uploaded_at = datetime.now(timezone.utc)

            db.session.commit()
            flash("Libro actualizado.", "success")
        else:
            book = OfferedBook(
                user_id=current_user.id,
                title=form.title.data,
                author=form.author.data,
                notes=form.notes.data or "",
            )
            book._set_normalized()
            db.session.add(book)
            db.session.flush()

            cover_file = form.cover_image.data
            if cover_file and cover_file.filename:
                filename = _save_book_cover(cover_file, book.id)
                if filename:
                    book.cover_image = filename
                    book.cover_uploaded_at = datetime.now(timezone.utc)

            db.session.commit()
            flash("Libro agregado.", "success")

        return redirect(url_for("views.my_offered_books"))

    user_books = (
        db.session.execute(
            db.select(OfferedBook)
            .where(
                OfferedBook.user_id == current_user.id,
                OfferedBook.status.notin_([BookStatus.DELETED, BookStatus.TRADED]),
            )
            .order_by(OfferedBook.created_at.desc())
        )
        .scalars()
        .all()
    )

    return render_template(
        "my_offered_books.html",
        form=form,
        offered_books=user_books,
        editing_book=editing_book,
    )


@views.route("/my-books/upload-photo/<int:book_id>/", methods=["POST"])
@login_required
def upload_book_photo(book_id):
    book = db.session.get(OfferedBook, book_id)
    if not book or book.user_id != current_user.id:
        abort(403)

    photo = request.files.get("cover_image")
    if not photo or not photo.filename:
        return jsonify({"error": "No se envió ningún archivo."}), 400

    filename = _save_book_cover(photo, book_id)
    if not filename:
        return jsonify({"error": "Formato de imagen inválido."}), 400

    if book.cover_image:
        _delete_media_file(book.cover_image)

    book.cover_image = filename
    book.cover_uploaded_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({"image_url": book.cover_image_url})


@views.route("/my-books/delete/<int:book_id>/", methods=["POST"])
@login_required
def delete_offered_book(book_id):
    book = db.session.get(OfferedBook, book_id)
    if not book or book.user_id != current_user.id:
        abort(403)
    book.delete()
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True}), 200
    flash("Libro eliminado.", "success")
    return redirect(url_for("views.my_offered_books"))


@views.route("/my-books/trade/<int:book_id>/", methods=["POST"])
@login_required
def trade_offered_book(book_id):
    book = db.session.get(OfferedBook, book_id)
    if not book or book.user_id != current_user.id:
        abort(403)
    book.trade()
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True}), 200
    flash("Libro marcado como intercambiado.", "success")
    return redirect(url_for("views.my_offered_books"))


@views.route("/my-books/reserve/<int:book_id>/", methods=["POST"])
@login_required
def reserve_offered_book(book_id):
    book = db.session.get(OfferedBook, book_id)
    if not book or book.user_id != current_user.id:
        abort(403)
    book.reserve()
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True}), 200
    return redirect(url_for("views.my_offered_books"))


# ---------------------------------------------------------------------------
# Wanted books
# ---------------------------------------------------------------------------


@views.route("/my-wanted/", methods=["GET", "POST"])
@login_required
def my_wanted_books():
    form = WantedBookForm()
    if form.validate_on_submit():
        book = WantedBook(
            user_id=current_user.id,
            title=form.title.data or "",
            author=form.author.data,
        )
        book._set_normalized()
        db.session.add(book)
        db.session.commit()
        flash("Libro buscado agregado.", "success")
        return redirect(url_for("views.my_wanted_books"))

    user_books = (
        db.session.execute(
            db.select(WantedBook)
            .where(WantedBook.user_id == current_user.id)
            .order_by(WantedBook.created_at.desc())
        )
        .scalars()
        .all()
    )
    return render_template("my_wanted_books.html", form=form, wanted_books=user_books)


@views.route("/my-wanted/delete/<int:book_id>/", methods=["POST"])
@login_required
def delete_wanted_book(book_id):
    book = db.session.get(WantedBook, book_id)
    if not book or book.user_id != current_user.id:
        abort(403)
    db.session.delete(book)
    db.session.commit()
    flash("Libro eliminado.", "success")
    return redirect(url_for("views.my_wanted_books"))


# ---------------------------------------------------------------------------
# Exchange requests
# ---------------------------------------------------------------------------


@views.route("/request-exchange/<int:book_id>/", methods=["POST"])
@login_required
def request_exchange(book_id):
    book = db.session.get(OfferedBook, book_id)
    if not book or book.status in [BookStatus.DELETED, BookStatus.TRADED]:
        abort(404)
    if book.user_id == current_user.id:
        abort(403)

    # Require at least one offered book
    requester_available = [b for b in current_user.offered if b.status == BookStatus.NEW]
    if not requester_available:
        return jsonify({"error": "Tenés que agregar tus libros antes de enviar solicitudes."}), 400

    # Check daily limit
    daily_limit = current_app.config.get("EXCHANGE_REQUEST_DAILY_LIMIT", 25)
    today_count = db.session.execute(
        db.select(db.func.count(ExchangeRequest.id)).where(
            ExchangeRequest.from_user_id == current_user.id,
            ExchangeRequest.created_at >= datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
        )
    ).scalar()
    if today_count >= daily_limit:
        return jsonify({"error": "Alcanzaste el límite de pedidos diario."}), 429

    # Check if already requested (within expiry window)
    expiry_days = current_app.config.get("EXCHANGE_REQUEST_EXPIRY_DAYS", 15)
    cutoff = datetime.now(timezone.utc) - timedelta(days=expiry_days)
    already = db.session.execute(
        db.select(ExchangeRequest).where(
            ExchangeRequest.from_user_id == current_user.id,
            ExchangeRequest.offered_book_id == book.id,
            ExchangeRequest.created_at >= cutoff,
        )
    ).scalar_one_or_none()
    if already:
        return jsonify({"error": "Ya enviaste una solicitud para este libro."}), 400

    er = ExchangeRequest(
        from_user_id=current_user.id,
        to_user_id=book.user_id,
        offered_book_id=book.id,
        book_title=book.title,
        book_author=book.author,
    )
    db.session.add(er)
    db.session.flush()

    try:
        _send_exchange_request_email(er)
    except Exception:
        current_app.logger.exception("Failed to send exchange request email for book %s", book.id)
        db.session.rollback()
        return jsonify({"error": "Error enviando el email de solicitud."}), 500

    db.session.commit()
    return jsonify({"message": "Solicitud de intercambio enviada."}), 201


# ---------------------------------------------------------------------------
# Likes
# ---------------------------------------------------------------------------


@views.route("/like/<int:book_id>/", methods=["POST"])
@login_required
def like_book(book_id):
    book = db.session.execute(
        db.select(OfferedBook).where(
            OfferedBook.id == book_id,
            OfferedBook.status.notin_([BookStatus.DELETED, BookStatus.TRADED]),
        )
    ).scalar_one_or_none()
    if not book:
        abort(404)
    if book.user_id == current_user.id:
        return jsonify({"error": "No podés dar like a tus propios libros."}), 400
    is_liked = book.toggle_like(current_user)
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"likes": book.likes, "liked": is_liked})
    return redirect(request.referrer or url_for("views.list_books"))


# ---------------------------------------------------------------------------
# Email helpers
# ---------------------------------------------------------------------------


def _get_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def _send_verification_email(user):
    token = _get_serializer().dumps(user.id, salt="email-verification")
    verification_url = url_for("views.verify_email", token=token, _external=True)
    msg = Message(
        subject="Verificá tu email en GiraLibros",
        recipients=[user.email],
        html=render_template(
            "emails/verification_email.html",
            username=user.username,
            verification_url=verification_url,
        ),
        body=render_template(
            "emails/verification_email.txt",
            username=user.username,
            verification_url=verification_url,
        ),
    )
    mail.send(msg)


def _send_password_reset_email(user):
    token = _get_serializer().dumps(user.id, salt="password-reset")
    reset_url = url_for("views.password_reset_confirm", token=token, _external=True)
    msg = Message(
        subject="Restablecé tu contraseña en GiraLibros",
        recipients=[user.email],
        html=render_template(
            "emails/password_reset.html",
            username=user.username,
            reset_url=reset_url,
        ),
        body=render_template(
            "emails/password_reset.txt",
            username=user.username,
            reset_url=reset_url,
        ),
    )
    mail.send(msg)


def _send_exchange_request_email(exchange_request):
    to_user = exchange_request.to_user
    requester = exchange_request.from_user
    book = exchange_request.offered_book

    requester_books = [
        b for b in requester.offered if b.status == BookStatus.NEW
    ]
    requester_profile = requester.profile

    reply_to = requester.profile.contact_email if requester.profile else None
    msg = Message(
        subject=f"Solicitud de intercambio de {requester.username}",
        recipients=[to_user.email],
        reply_to=reply_to,
        html=render_template(
            "emails/exchange_request.html",
            to_user=to_user,
            requester=requester,
            requester_books=requester_books,
            requester_profile=requester_profile,
            book=book,
        ),
        body=render_template(
            "emails/exchange_request.txt",
            to_user=to_user,
            requester=requester,
            requester_books=requester_books,
            requester_profile=requester_profile,
            book=book,
        ),
    )
    mail.send(msg)


# ---------------------------------------------------------------------------
# File-handling helpers
# ---------------------------------------------------------------------------


def _save_book_cover(file_storage, book_id):
    """Save book cover image, resizing thumbnail. Returns relative path or None."""
    from PIL import Image
    import io

    max_size = current_app.config.get("BOOK_COVER_MAX_SIZE", 10 * 1024 * 1024)
    allowed = current_app.config.get(
        "BOOK_COVER_ALLOWED_TYPES", ["image/jpeg", "image/png", "image/webp"]
    )
    content = file_storage.read()
    if len(content) > max_size:
        return None

    content_type = file_storage.content_type or ""
    if content_type not in allowed:
        # Try guessing from filename extension
        ext = (file_storage.filename or "").rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            return None
        content_type = f"image/{ext}" if ext != "jpg" else "image/jpeg"

    try:
        from PIL import ImageOps
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        max_w = current_app.config.get("BOOK_COVER_THUMBNAIL_MAX_WIDTH", 400)
        max_h = current_app.config.get("BOOK_COVER_THUMBNAIL_MAX_HEIGHT", 600)
        img.thumbnail((max_w, max_h), Image.LANCZOS)

        import time
        folder = os.path.join(current_app.config.get("MEDIA_FOLDER", "media"), "covers")
        os.makedirs(folder, exist_ok=True)
        filename = f"cover_{book_id}_{time.time_ns()}.jpg"
        path = os.path.join(folder, filename)
        quality = current_app.config.get("BOOK_COVER_JPEG_QUALITY", 85)
        img.save(path, "JPEG", quality=quality)
        return f"covers/{filename}"
    except Exception:
        current_app.logger.exception("Failed to save book cover for book %s", book_id)
        return None


def _save_profile_picture(file_storage, user_id):
    """Save profile picture, resizing to square. Returns relative path or None."""
    from PIL import Image
    import io

    max_size = current_app.config.get("PROFILE_PICTURE_MAX_SIZE", 5 * 1024 * 1024)
    allowed = current_app.config.get(
        "PROFILE_PICTURE_ALLOWED_TYPES", ["image/jpeg", "image/png", "image/webp"]
    )
    content = file_storage.read()
    if len(content) > max_size:
        return None

    content_type = file_storage.content_type or ""
    if content_type not in allowed:
        ext = (file_storage.filename or "").rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            return None

    try:
        from PIL import ImageOps
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        max_dim = current_app.config.get("PROFILE_PICTURE_MAX_DIMENSION", 300)
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)

        folder = os.path.join(current_app.config.get("MEDIA_FOLDER", "media"), "profile_pics")
        os.makedirs(folder, exist_ok=True)
        filename = f"profile_{user_id}.jpg"
        path = os.path.join(folder, filename)
        quality = current_app.config.get("PROFILE_PICTURE_JPEG_QUALITY", 85)
        img.save(path, "JPEG", quality=quality)
        return f"profile_pics/{filename}"
    except Exception:
        current_app.logger.exception("Failed to save profile picture for user %s", user_id)
        return None


def _safe_next(target):
    """Return target if it is a safe same-host relative URL, else the book list."""
    from urllib.parse import urlparse, urljoin
    fallback = url_for("views.list_books")
    if not target:
        return fallback
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    if test.scheme in ("http", "https") and ref.netloc == test.netloc:
        return target
    return fallback


def _delete_media_file(relative_path):
    """Delete a file from the media folder."""
    if not relative_path:
        return
    try:
        media_folder = current_app.config.get("MEDIA_FOLDER", "media")
        abs_media = os.path.abspath(media_folder)
        abs_path = os.path.abspath(os.path.join(media_folder, relative_path))
        if abs_path.startswith(abs_media + os.sep) and os.path.isfile(abs_path):
            os.remove(abs_path)
    except Exception:
        current_app.logger.exception("Failed to delete media file: %s", relative_path)
