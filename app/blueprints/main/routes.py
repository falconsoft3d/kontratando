from flask import Blueprint, render_template

from app.extensions import db
from app.models import Company, JobPosting, JobPostingView

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    company = Company.query.first()
    postings = (
        JobPosting.query.filter_by(is_published=True)
        .order_by(JobPosting.created_at.desc())
        .all()
    )
    return render_template("main/index.html", company=company, postings=postings)


@bp.route("/puestos/<int:posting_id>")
def job_detail(posting_id):
    posting = JobPosting.query.filter_by(id=posting_id, is_published=True).first_or_404()
    db.session.add(JobPostingView(job_posting_id=posting.id))
    db.session.commit()
    return render_template("main/job_detail.html", posting=posting)
