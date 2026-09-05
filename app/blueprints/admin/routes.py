from functools import wraps
from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import ApplicationCommentForm, BlacklistForm, CompanyForm, JobPostingForm
from app.models import (
    Answer,
    Application,
    ApplicationComment,
    BlacklistEntry,
    Company,
    JobPosting,
    JobPostingView,
    Question,
    QuestionOption,
    User,
)
from app.utils.ai_audit import AIAuditError, audit_application
from app.utils.job_ai import generate_job_description, suggest_questions

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@bp.route("/")
@login_required
@admin_required
def dashboard():
    stats = {
        "postings": JobPosting.query.count(),
        "published": JobPosting.query.filter_by(is_published=True).count(),
        "applications": Application.query.count(),
        "candidates": User.query.filter_by(role=User.ROLE_CANDIDATE).count(),
        "blacklisted": BlacklistEntry.query.count(),
    }
    latest_applications = Application.query.order_by(Application.created_at.desc()).limit(8).all()
    return render_template("admin/dashboard.html", stats=stats, latest_applications=latest_applications)


# ---------------------------------------------------------------------------
# Datos de la empresa
# ---------------------------------------------------------------------------
@bp.route("/empresa", methods=["GET", "POST"])
@login_required
@admin_required
def company():
    company = Company.query.first()
    if company is None:
        company = Company()
        db.session.add(company)
        db.session.commit()

    form = CompanyForm(obj=company)
    if form.validate_on_submit():
        form.populate_obj(company)
        db.session.commit()
        flash("Datos de la empresa actualizados.", "success")
        return redirect(url_for("admin.company"))

    return render_template("admin/company.html", form=form)


# ---------------------------------------------------------------------------
# Puestos
# ---------------------------------------------------------------------------
@bp.route("/puestos")
@login_required
@admin_required
def postings():
    all_postings = JobPosting.query.order_by(JobPosting.created_at.desc()).all()
    return render_template("admin/postings.html", postings=all_postings)


@bp.route("/puestos/nuevo", methods=["GET", "POST"])
@login_required
@admin_required
def new_posting():
    form = JobPostingForm()

    if form.validate_on_submit():
        posting = JobPosting(
            title=form.title.data,
            department=form.department.data,
            location=form.location.data,
            employment_type=form.employment_type.data,
            description=form.description.data,
            is_published=form.is_published.data,
        )
        db.session.add(posting)
        db.session.flush()
        _save_questions(posting)
        db.session.commit()
        flash("Puesto creado correctamente.", "success")
        return redirect(url_for("admin.postings"))

    return render_template("admin/posting_form.html", form=form, posting=None, questions=[])


@bp.route("/puestos/<int:posting_id>/editar", methods=["GET", "POST"])
@login_required
@admin_required
def edit_posting(posting_id):
    posting = JobPosting.query.get_or_404(posting_id)
    form = JobPostingForm(obj=posting)

    if form.validate_on_submit():
        posting.title = form.title.data
        posting.department = form.department.data
        posting.location = form.location.data
        posting.employment_type = form.employment_type.data
        posting.description = form.description.data
        posting.is_published = form.is_published.data
        deleted_answers = _save_questions(posting, replace=True)
        db.session.commit()
        flash("Puesto actualizado correctamente.", "success")
        if deleted_answers:
            flash(
                f"Se eliminaron {deleted_answers} respuesta(s) de postulaciones anteriores porque las "
                "preguntas a las que correspondían fueron modificadas o eliminadas.",
                "warning",
            )
        return redirect(url_for("admin.postings"))

    return render_template("admin/posting_form.html", form=form, posting=posting, questions=posting.questions.all())


@bp.route("/ia/generar-descripcion", methods=["POST"])
@login_required
@admin_required
def ai_generate_description():
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Escribe primero el título del puesto."}), 400
    try:
        description = generate_job_description(title)
        return jsonify({"description": description})
    except AIAuditError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Error generando descripción con IA")
        return jsonify({"error": "Ocurrió un error al generar la descripción con IA."}), 500


@bp.route("/ia/proponer-preguntas", methods=["POST"])
@login_required
@admin_required
def ai_suggest_questions():
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    description = (payload.get("description") or "").strip()
    count = payload.get("count", 5)
    if not title:
        return jsonify({"error": "Escribe primero el título del puesto."}), 400
    try:
        questions = suggest_questions(title, description, count)
        return jsonify({"questions": questions})
    except AIAuditError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Error proponiendo preguntas con IA")
        return jsonify({"error": "Ocurrió un error al proponer preguntas con IA."}), 500


def _save_questions(posting, replace=False):
    """Analiza los bloques de preguntas enviados desde el formulario (q_type_N, q_text_N, q_options_N[]).

    Devuelve la cantidad de respuestas de postulaciones anteriores que se eliminaron (si las había).
    """
    deleted_answers = 0
    if replace:
        old_questions = Question.query.filter_by(job_posting_id=posting.id).all()
        old_question_ids = [question.id for question in old_questions]
        if old_question_ids:
            # Las respuestas quedarían huérfanas si se borra la pregunta que respondían.
            deleted_answers = Answer.query.filter(Answer.question_id.in_(old_question_ids)).delete(
                synchronize_session=False
            )
        # Se borra pregunta por pregunta (no con un DELETE masivo) para que el cascade de
        # QuestionOption se aplique correctamente y no viole la llave foránea.
        for question in old_questions:
            db.session.delete(question)
        db.session.flush()

    indexes = sorted(
        {key.split("q_text_", 1)[1] for key in request.form if key.startswith("q_text_")},
        key=lambda value: int(value),
    )

    order_index = 0
    for idx in indexes:
        text = request.form.get(f"q_text_{idx}", "").strip()
        if not text:
            continue
        question_type = request.form.get(f"q_type_{idx}", Question.TYPE_TEXT)
        if question_type not in Question.TYPES:
            question_type = Question.TYPE_TEXT

        question = Question(
            job_posting_id=posting.id,
            text=text,
            question_type=question_type,
            order_index=order_index,
        )
        db.session.add(question)
        order_index += 1

        if question_type == Question.TYPE_CHOICE:
            db.session.flush()
            option_texts = [
                option.strip() for option in request.form.getlist(f"q_options_{idx}[]") if option.strip()
            ]
            for opt_index, option_text in enumerate(option_texts):
                db.session.add(
                    QuestionOption(question_id=question.id, text=option_text, order_index=opt_index)
                )

    return deleted_answers


@bp.route("/puestos/<int:posting_id>/publicar", methods=["POST"])
@login_required
@admin_required
def toggle_publish(posting_id):
    posting = JobPosting.query.get_or_404(posting_id)
    posting.is_published = not posting.is_published
    db.session.commit()
    estado = "publicado" if posting.is_published else "despublicado"
    flash(f"El puesto '{posting.title}' fue {estado}.", "success")
    return redirect(url_for("admin.postings"))


@bp.route("/puestos/<int:posting_id>/eliminar", methods=["POST"])
@login_required
@admin_required
def delete_posting(posting_id):
    posting = JobPosting.query.get_or_404(posting_id)
    db.session.delete(posting)
    db.session.commit()
    flash("Puesto eliminado.", "info")
    return redirect(url_for("admin.postings"))


# ---------------------------------------------------------------------------
# Postulaciones
# ---------------------------------------------------------------------------
@bp.route("/postulaciones")
@login_required
@admin_required
def applications():
    apps = Application.query.order_by(Application.created_at.desc()).all()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    kpis = {
        "views_today": JobPostingView.query.filter(JobPostingView.viewed_at >= today_start).count(),
        "views_total": JobPostingView.query.count(),
        "applications_today": Application.query.filter(Application.created_at >= today_start).count(),
        "applications_total": Application.query.count(),
    }

    return render_template("admin/applications.html", applications=apps, kpis=kpis)


@bp.route("/postulaciones/<int:application_id>")
@login_required
@admin_required
def application_detail(application_id):
    application = Application.query.get_or_404(application_id)
    comment_form = ApplicationCommentForm()
    return render_template(
        "admin/application_detail.html", application=application, comment_form=comment_form
    )


@bp.route("/postulaciones/<int:application_id>/comentarios", methods=["POST"])
@login_required
@admin_required
def add_comment(application_id):
    application = Application.query.get_or_404(application_id)
    comment_form = ApplicationCommentForm()
    if comment_form.validate_on_submit():
        db.session.add(
            ApplicationComment(
                application_id=application.id,
                author_id=current_user.id,
                body=comment_form.body.data.strip(),
            )
        )
        db.session.commit()
        flash("Comentario agregado. Se tendrá en cuenta en la próxima auditoría de IA.", "success")
    else:
        flash("El comentario no puede estar vacío.", "danger")
    return redirect(url_for("admin.application_detail", application_id=application.id))


@bp.route("/postulaciones/<int:application_id>/curriculum")
@login_required
@admin_required
def download_resume(application_id):
    application = Application.query.get_or_404(application_id)
    if not application.candidate.resume_path:
        abort(404)
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"], application.candidate.resume_path, as_attachment=True
    )


@bp.route("/postulaciones/respuestas/<int:answer_id>/archivo")
@login_required
@admin_required
def download_answer_file(answer_id):
    answer = Answer.query.get_or_404(answer_id)
    if not answer.answer_file_path:
        abort(404)
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"], answer.answer_file_path, as_attachment=True
    )


@bp.route("/postulaciones/<int:application_id>/re-auditar", methods=["POST"])
@login_required
@admin_required
def reaudit_application(application_id):
    application = Application.query.get_or_404(application_id)
    candidate = application.candidate
    posting = application.job_posting
    qa_pairs = [
        {"question": answer.question.text, "answer": answer.display_answer}
        for answer in application.answers
    ]
    reviewer_comments = [comment.body for comment in application.comments]
    try:
        result = audit_application(posting, candidate.resume_text or "", qa_pairs, reviewer_comments)
        application.ai_score = result["score"]
        application.ai_feedback = result["feedback"]
        application.ai_psychological_summary = result.get("psychological_summary")
        application.ai_audited_at = db.func.now()
        db.session.commit()
        flash("Auditoría de IA actualizada.", "success")
    except AIAuditError as exc:
        flash(str(exc), "danger")
    except Exception:
        current_app.logger.exception("Error al ejecutar la auditoría de IA")
        flash("Ocurrió un error al ejecutar la auditoría de IA.", "danger")
    return redirect(url_for("admin.application_detail", application_id=application.id))


@bp.route("/postulaciones/<int:application_id>/estado/<string:new_status>", methods=["POST"])
@login_required
@admin_required
def set_application_status(application_id, new_status):
    if new_status not in {
        Application.STATUS_PENDING,
        Application.STATUS_REVIEWED,
        Application.STATUS_ACCEPTED,
        Application.STATUS_REJECTED,
    }:
        abort(400)
    application = Application.query.get_or_404(application_id)
    application.status = new_status
    db.session.commit()
    flash("Estado de la postulación actualizado.", "success")
    return redirect(url_for("admin.application_detail", application_id=application.id))


# ---------------------------------------------------------------------------
# Lista negra
# ---------------------------------------------------------------------------
@bp.route("/lista-negra", methods=["GET", "POST"])
@login_required
@admin_required
def blacklist():
    form = BlacklistForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if BlacklistEntry.is_email_blacklisted(email):
            flash("Ese correo ya está en la lista negra.", "warning")
        else:
            db.session.add(
                BlacklistEntry(
                    email=email,
                    first_name=form.first_name.data,
                    last_name=form.last_name.data,
                    reason=form.reason.data,
                )
            )
            # Si el usuario ya existía, se invalida su cuenta automáticamente.
            existing_user = User.query.filter(db.func.lower(User.email) == email).first()
            if existing_user:
                existing_user.is_blacklisted = True
                existing_user.is_active_account = False
            db.session.commit()
            flash("Correo agregado a la lista negra.", "success")
        return redirect(url_for("admin.blacklist"))

    entries = BlacklistEntry.query.order_by(BlacklistEntry.created_at.desc()).all()
    return render_template("admin/blacklist.html", form=form, entries=entries)


@bp.route("/lista-negra/<int:entry_id>/eliminar", methods=["POST"])
@login_required
@admin_required
def remove_blacklist(entry_id):
    entry = BlacklistEntry.query.get_or_404(entry_id)
    user = User.query.filter(db.func.lower(User.email) == entry.email.lower()).first()
    if user:
        user.is_blacklisted = False
        user.is_active_account = True
    db.session.delete(entry)
    db.session.commit()
    flash("Correo eliminado de la lista negra.", "info")
    return redirect(url_for("admin.blacklist"))
