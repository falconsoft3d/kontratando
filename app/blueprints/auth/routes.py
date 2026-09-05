from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.forms import LoginForm, RegisterForm
from app.models import BlacklistEntry, User

bp = Blueprint("auth", __name__, url_prefix="/cuenta")


@bp.route("/registro", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter(db.func.lower(User.email) == email).first():
            flash("Ya existe una cuenta registrada con ese correo.", "danger")
            return render_template("auth/register.html", form=form)

        is_first_user = User.query.count() == 0
        is_blacklisted = not is_first_user and BlacklistEntry.is_email_blacklisted(email)

        user = User(
            name=form.name.data.strip(),
            email=email,
            phone=form.phone.data,
            role=User.ROLE_ADMIN if is_first_user else User.ROLE_CANDIDATE,
            is_blacklisted=is_blacklisted,
            is_active_account=not is_blacklisted,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        if is_first_user:
            flash("Cuenta creada como administrador (primera cuenta del sistema). Ya puedes iniciar sesión.", "success")
            return redirect(url_for("auth.login"))

        if is_blacklisted:
            # Cuenta invalidada automáticamente por estar en la lista negra interna.
            flash(
                "Tu cuenta fue creada pero no puede utilizarse. Contacta a la empresa si crees que es un error.",
                "danger",
            )
            return redirect(url_for("auth.login"))

        flash("Cuenta creada correctamente. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@bp.route("/ingresar", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter(db.func.lower(User.email) == email).first()

        if user is None or not user.check_password(form.password.data):
            flash("Correo o contraseña incorrectos.", "danger")
        elif user.is_blacklisted or not user.is_active_account:
            flash("Esta cuenta está inhabilitada y no puede iniciar sesión.", "danger")
        else:
            login_user(user)
            flash(f"Bienvenido, {user.name}.", "success")
            next_page = request.args.get("next")
            if user.is_admin:
                return redirect(next_page or url_for("admin.dashboard"))
            return redirect(next_page or url_for("main.index"))

    return render_template("auth/login.html", form=form)


@bp.route("/salir")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("main.index"))
