from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class Company(db.Model):
    __tablename__ = "company"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, default="Mi Empresa")
    tagline = db.Column(db.String(255))
    description = db.Column(db.Text)
    website = db.Column(db.String(255))
    email = db.Column(db.String(150))
    phone = db.Column(db.String(50))
    address = db.Column(db.String(255))
    logo_path = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class BlacklistEntry(db.Model):
    __tablename__ = "blacklist_entry"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    @staticmethod
    def is_email_blacklisted(email: str) -> bool:
        if not email:
            return False
        return (
            BlacklistEntry.query.filter(
                db.func.lower(BlacklistEntry.email) == email.lower()
            ).first()
            is not None
        )


class User(UserMixin, db.Model):
    __tablename__ = "user"

    ROLE_ADMIN = "admin"
    ROLE_CANDIDATE = "candidate"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_CANDIDATE)

    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    is_blacklisted = db.Column(db.Boolean, default=False, nullable=False)

    phone = db.Column(db.String(50))
    resume_path = db.Column(db.String(255))
    resume_text = db.Column(db.Text)

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    applications = db.relationship(
        "Application", backref="candidate", lazy="dynamic", foreign_keys="Application.candidate_id"
    )

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        # Flask-Login usa esta propiedad para permitir o no el login
        return self.is_active_account and not self.is_blacklisted

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN


class JobPosting(db.Model):
    __tablename__ = "job_posting"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    department = db.Column(db.String(120))
    location = db.Column(db.String(120))
    employment_type = db.Column(db.String(60))
    description = db.Column(db.Text)
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    questions = db.relationship(
        "Question", backref="job_posting", lazy="dynamic",
        order_by="Question.order_index", cascade="all, delete-orphan"
    )
    applications = db.relationship(
        "Application", backref="job_posting", lazy="dynamic", cascade="all, delete-orphan"
    )
    views = db.relationship(
        "JobPostingView", backref="job_posting", lazy="dynamic", cascade="all, delete-orphan"
    )

    @property
    def applications_count(self):
        return self.applications.count()

    @property
    def views_count(self):
        return self.views.count()


class JobPostingView(db.Model):
    __tablename__ = "job_posting_view"

    id = db.Column(db.Integer, primary_key=True)
    job_posting_id = db.Column(db.Integer, db.ForeignKey("job_posting.id"), nullable=False)
    viewed_at = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)


class Question(db.Model):
    __tablename__ = "question"

    TYPE_TEXT = "text"
    TYPE_CHOICE = "choice"
    TYPE_FILE = "file"
    TYPES = (TYPE_TEXT, TYPE_CHOICE, TYPE_FILE)

    id = db.Column(db.Integer, primary_key=True)
    job_posting_id = db.Column(db.Integer, db.ForeignKey("job_posting.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), nullable=False, default=TYPE_TEXT)
    order_index = db.Column(db.Integer, default=0, nullable=False)

    options = db.relationship(
        "QuestionOption", backref="question", lazy="dynamic",
        order_by="QuestionOption.order_index", cascade="all, delete-orphan"
    )


class QuestionOption(db.Model):
    __tablename__ = "question_option"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    text = db.Column(db.String(255), nullable=False)
    order_index = db.Column(db.Integer, default=0, nullable=False)


class Application(db.Model):
    __tablename__ = "application"

    STATUS_PENDING = "pending"
    STATUS_REVIEWED = "reviewed"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"

    id = db.Column(db.Integer, primary_key=True)
    job_posting_id = db.Column(db.Integer, db.ForeignKey("job_posting.id"), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    status = db.Column(db.String(20), default=STATUS_PENDING, nullable=False)
    ai_score = db.Column(db.Float)
    ai_feedback = db.Column(db.Text)
    ai_psychological_summary = db.Column(db.Text)
    ai_audited_at = db.Column(db.DateTime(timezone=True))

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    answers = db.relationship(
        "Answer", backref="application", lazy="dynamic", cascade="all, delete-orphan"
    )
    comments = db.relationship(
        "ApplicationComment", backref="application", lazy="dynamic",
        order_by="ApplicationComment.created_at", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint("job_posting_id", "candidate_id", name="uq_application_job_candidate"),
    )


class Answer(db.Model):
    __tablename__ = "answer"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    answer_text = db.Column(db.Text)
    selected_option_id = db.Column(db.Integer, db.ForeignKey("question_option.id"))
    answer_file_path = db.Column(db.String(255))

    question = db.relationship("Question")
    selected_option = db.relationship("QuestionOption")

    @property
    def display_answer(self):
        if self.question.question_type == Question.TYPE_CHOICE:
            return self.selected_option.text if self.selected_option else "(sin respuesta)"
        if self.question.question_type == Question.TYPE_FILE:
            return self.answer_file_path or "(sin archivo adjunto)"
        return self.answer_text or "(sin respuesta)"


class ApplicationComment(db.Model):
    __tablename__ = "application_comment"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    author = db.relationship("User")
