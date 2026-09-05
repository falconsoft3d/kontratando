from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    BooleanField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional


class RegisterForm(FlaskForm):
    name = StringField("Nombre completo", validators=[DataRequired(), Length(max=150)])
    email = StringField("Correo electrónico", validators=[DataRequired(), Email(), Length(max=150)])
    phone = StringField("Teléfono", validators=[Optional(), Length(max=50)])
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        "Confirmar contraseña", validators=[DataRequired(), EqualTo("password")]
    )
    submit = SubmitField("Crear cuenta")


class LoginForm(FlaskForm):
    email = StringField("Correo electrónico", validators=[DataRequired(), Email()])
    password = PasswordField("Contraseña", validators=[DataRequired()])
    submit = SubmitField("Ingresar")


class CompanyForm(FlaskForm):
    name = StringField("Nombre de la empresa", validators=[DataRequired(), Length(max=150)])
    tagline = StringField("Eslogan", validators=[Optional(), Length(max=255)])
    description = TextAreaField("Descripción", validators=[Optional()])
    website = StringField("Sitio web", validators=[Optional(), Length(max=255)])
    email = StringField("Correo de contacto", validators=[Optional(), Email(), Length(max=150)])
    phone = StringField("Teléfono", validators=[Optional(), Length(max=50)])
    address = StringField("Dirección", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Guardar datos de la empresa")


class JobPostingForm(FlaskForm):
    title = StringField("Título del puesto", validators=[DataRequired(), Length(max=150)])
    department = StringField("Área / Departamento", validators=[Optional(), Length(max=120)])
    location = StringField("Ubicación", validators=[Optional(), Length(max=120)])
    employment_type = SelectField(
        "Tipo de contrato",
        choices=[
            ("full_time", "Tiempo completo"),
            ("part_time", "Medio tiempo"),
            ("contract", "Por contrato"),
            ("internship", "Práctica / Pasantía"),
            ("remote", "Remoto"),
        ],
        validators=[Optional()],
    )
    description = TextAreaField("Descripción del puesto", validators=[DataRequired()])
    is_published = BooleanField("Publicar puesto")
    submit = SubmitField("Guardar puesto")


class BlacklistForm(FlaskForm):
    email = StringField("Correo electrónico", validators=[DataRequired(), Email(), Length(max=150)])
    first_name = StringField("Nombre", validators=[Optional(), Length(max=100)])
    last_name = StringField("Apellido", validators=[Optional(), Length(max=100)])
    reason = StringField("Motivo", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Agregar a lista negra")


class ApplicationForm(FlaskForm):
    resume = FileField(
        "Currículum (PDF)",
        validators=[Optional(), FileAllowed(["pdf"], "Solo se permiten archivos PDF")],
    )
    submit = SubmitField("Enviar postulación")


class ApplicationCommentForm(FlaskForm):
    body = TextAreaField("Comentario (entrevista, notas, etc.)", validators=[DataRequired()])
    submit = SubmitField("Agregar comentario")
