from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    BooleanField,
    EmailField,
    MultipleFileField,
    PasswordField,
    SelectMultipleField,
    StringField,
    TextAreaField,
    HiddenField,
    widgets,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Optional,
    ValidationError,
)


AREA_CHOICES = [
    ("CABA_CENTRO", "CABA Centro"),
    ("CABA_SUR", "CABA Sur"),
    ("CABA_NORTE", "CABA Norte"),
    ("GBA_NORTE", "GBA Norte"),
    ("GBA_OESTE", "GBA Oeste"),
    ("GBA_SUR", "GBA Sur"),
]


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class RegistrationForm(FlaskForm):
    username = StringField("Nombre de usuario", validators=[DataRequired(), Length(min=3, max=150)])
    email = EmailField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        "Confirmar contraseña",
        validators=[DataRequired(), EqualTo("password", message="Las contraseñas no coinciden")],
    )
    website = HiddenField()

    def validate_website(self, field):
        if field.data:
            raise ValidationError("Bot detectado.")


class LoginForm(FlaskForm):
    email = StringField("Email o usuario", validators=[DataRequired()])
    password = PasswordField("Contraseña", validators=[DataRequired()])
    remember_me = BooleanField("Recordarme")


class ProfileEditForm(FlaskForm):
    contact_email = EmailField("Email de contacto", validators=[Optional(), Email()])
    alternate_contact = StringField("Contacto alternativo", validators=[Optional(), Length(max=200)])
    about = TextAreaField("Sobre mí", validators=[Optional()])
    locations = MultiCheckboxField("Zonas", choices=AREA_CHOICES, validators=[Optional()])
    profile_picture = FileField(
        "Foto de perfil",
        validators=[FileAllowed(["jpg", "jpeg", "png", "webp"], "Solo imágenes")],
    )
    website = HiddenField()

    def validate_website(self, field):
        if field.data:
            raise ValidationError("Bot detectado.")


class OfferedBookForm(FlaskForm):
    title = StringField("Título", validators=[DataRequired(), Length(max=200)])
    author = StringField("Autor", validators=[DataRequired(), Length(max=200)])
    notes = TextAreaField("Notas", validators=[Optional()])
    cover_image = FileField(
        "Imagen de portada",
        validators=[FileAllowed(["jpg", "jpeg", "png", "webp"], "Solo imágenes")],
    )


class WantedBookForm(FlaskForm):
    title = StringField("Título", validators=[Optional(), Length(max=200)])
    author = StringField("Autor", validators=[DataRequired(), Length(max=200)])


class PasswordResetRequestForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email()])


class PasswordResetForm(FlaskForm):
    password = PasswordField("Nueva contraseña", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        "Confirmar contraseña",
        validators=[DataRequired(), EqualTo("password", message="Las contraseñas no coinciden")],
    )
