import os

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import ApplicationForm
from app.models import Answer, Application, JobPosting, Question, QuestionOption
from app.utils.ai_audit import AIAuditError, audit_application
from app.utils.resume_parser import allowed_resume_file, extract_text_from_pdf, save_resume_file

bp = Blueprint("candidate", __name__, url_prefix="/postulacion")


def candidate_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or current_user.is_admin:
            flash("Debes ingresar con una cuenta de candidato.", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


@bp.route("/<int:posting_id>", methods=["GET", "POST"])
@login_required
@candidate_required
def apply(posting_id):
    posting = JobPosting.query.filter_by(id=posting_id, is_published=True).first_or_404()

    existing = Application.query.filter_by(
        job_posting_id=posting.id, candidate_id=current_user.id
    ).first()
    if existing:
        flash("Ya te postulaste a este puesto.", "info")
        return redirect(url_for("candidate.my_applications"))

    form = ApplicationForm()
    questions = posting.questions.all()

    if form.validate_on_submit():
        resume_path = current_user.resume_path
        resume_text = current_user.resume_text or ""

        resume_file = form.resume.data
        if resume_file and resume_file.filename:
            if not allowed_resume_file(
                resume_file.filename, current_app.config["ALLOWED_RESUME_EXTENSIONS"]
            ):
                flash("El currículum debe ser un archivo PDF.", "danger")
                return render_template(
                    "candidate/apply.html", posting=posting, form=form, questions=questions
                )
            resume_path = save_resume_file(
                resume_file, current_app.config["UPLOAD_FOLDER"], f"user{current_user.id}"
            )
            full_path = os.path.join(current_app.config["UPLOAD_FOLDER"], resume_path)
            resume_text = extract_text_from_pdf(full_path)
            current_user.resume_path = resume_path
            current_user.resume_text = resume_text

        application = Application(job_posting_id=posting.id, candidate_id=current_user.id)
        db.session.add(application)
        db.session.flush()

        qa_pairs = []
        for question in questions:
            answer = Answer(application_id=application.id, question_id=question.id)

            if question.question_type == Question.TYPE_CHOICE:
                option_id = request.form.get(f"answer_{question.id}")
                option = QuestionOption.query.get(int(option_id)) if option_id else None
                answer.selected_option_id = option.id if option else None
                display_answer = option.text if option else "(sin respuesta)"
            elif question.question_type == Question.TYPE_FILE:
                uploaded_file = request.files.get(f"answer_file_{question.id}")
                if uploaded_file and uploaded_file.filename:
                    stored_name = save_resume_file(
                        uploaded_file,
                        current_app.config["UPLOAD_FOLDER"],
                        f"app{application.id}_q{question.id}",
                    )
                    answer.answer_file_path = stored_name
                    display_answer = f"Archivo adjunto: {uploaded_file.filename}"
                else:
                    display_answer = "(sin archivo adjunto)"
            else:
                answer_text = request.form.get(f"answer_{question.id}", "").strip()
                answer.answer_text = answer_text
                display_answer = answer_text or "(sin respuesta)"

            db.session.add(answer)
            qa_pairs.append({"question": question.text, "answer": display_answer})

        db.session.commit()

        try:
            result = audit_application(posting, resume_text, qa_pairs)
            application.ai_score = result["score"]
            application.ai_feedback = result["feedback"]
            application.ai_psychological_summary = result.get("psychological_summary")
            application.ai_audited_at = db.func.now()
            db.session.commit()
        except AIAuditError as exc:
            current_app.logger.warning("Auditoría IA no realizada: %s", exc)
        except Exception:
            current_app.logger.exception("Error al ejecutar la auditoría de IA")

        flash("¡Postulación enviada con éxito!", "success")
        return redirect(url_for("candidate.my_applications"))

    return render_template("candidate/apply.html", posting=posting, form=form, questions=questions)


@bp.route("/mis-postulaciones")
@login_required
@candidate_required
def my_applications():
    applications = (
        Application.query.filter_by(candidate_id=current_user.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    return render_template("candidate/my_applications.html", applications=applications)
