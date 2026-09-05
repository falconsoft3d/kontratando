import os

import pdfplumber
from werkzeug.utils import secure_filename


def allowed_resume_file(filename: str, allowed_extensions: set) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def save_resume_file(file_storage, upload_folder: str, prefix: str) -> str:
    """Guarda el PDF del currículum y devuelve la ruta relativa almacenada."""
    os.makedirs(upload_folder, exist_ok=True)
    filename = secure_filename(file_storage.filename)
    stored_name = f"{prefix}_{filename}"
    full_path = os.path.join(upload_folder, stored_name)
    file_storage.save(full_path)
    return stored_name


def extract_text_from_pdf(full_path: str) -> str:
    text_parts = []
    try:
        with pdfplumber.open(full_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
    except Exception:
        return ""
    return "\n".join(text_parts).strip()
