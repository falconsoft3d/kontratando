import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(os.path.dirname(basedir), ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-insegura-cambiar")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://kontratando:kontratando@localhost:5432/kontratando",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(os.path.dirname(basedir), os.environ.get("UPLOAD_FOLDER", "uploads"))
    ALLOWED_RESUME_EXTENSIONS = {"pdf"}
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH_MB", 8)) * 1024 * 1024

    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@kontratando.com")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "CambiaEstaClave123!")

    WTF_CSRF_ENABLED = True
