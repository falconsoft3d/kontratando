import json

from flask import current_app

from app.utils.ai_audit import AIAuditError, _get_client

QUESTION_TYPES = {"text", "choice", "file"}


def generate_job_description(title: str) -> str:
    """Genera una descripción de puesto profesional a partir de un título."""
    client = _get_client()
    model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")

    system_prompt = (
        "Eres un especialista en reclutamiento que redacta descripciones de puesto profesionales, "
        "claras y atractivas en español, en un tono serio similar a las publicaciones de LinkedIn."
    )
    user_prompt = (
        f"Redacta una descripción completa para el puesto '{title}': incluye responsabilidades principales, "
        "requisitos (experiencia, habilidades, formación) y lo que ofrece la empresa. "
        "Devuelve únicamente el texto de la descripción en párrafos claros, sin encabezados markdown ni viñetas "
        "con símbolos especiales."
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.5,
    )
    return (response.choices[0].message.content or "").strip()


def suggest_questions(title: str, description: str, count: int) -> list:
    """Usa IA para proponer preguntas de filtro para un puesto.

    Devuelve una lista de dicts: {"text": str, "type": "text"|"choice"|"file", "options": [str, ...]}
    """
    client = _get_client()
    model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")
    count = max(1, min(int(count or 5), 15))

    system_prompt = (
        "Eres un especialista en reclutamiento. Propones preguntas de filtro para candidatos a un puesto. "
        "Responde EXCLUSIVAMENTE en formato JSON válido con la clave 'questions': una lista de objetos con "
        "'text' (la pregunta en español), 'type' (uno de: 'text', 'choice', 'file') y 'options' (lista de "
        "strings; solo se usa si type es 'choice', en los demás casos debe ser una lista vacía). "
        "Usa 'text' para preguntas abiertas relevantes, 'choice' para preguntas cerradas con 2 a 5 opciones "
        "claras y excluyentes, y usa 'file' como máximo en una pregunta y solo si tiene sentido pedir un "
        "adjunto (por ejemplo, portafolio, certificado o licencia)."
    )
    user_prompt = (
        f"Puesto: {title}\n"
        f"Descripción del puesto: {description or '(sin descripción proporcionada)'}\n\n"
        f"Propón exactamente {count} preguntas de filtro relevantes para evaluar candidatos a este puesto."
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )

    content = response.choices[0].message.content
    try:
        data = json.loads(content)
        raw_questions = data.get("questions", [])
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise AIAuditError("No se pudo interpretar la respuesta de la IA.") from exc

    questions = []
    for item in raw_questions[:count]:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        q_type = item.get("type", "text")
        if q_type not in QUESTION_TYPES:
            q_type = "text"
        options = [str(opt).strip() for opt in item.get("options", []) if str(opt).strip()] if q_type == "choice" else []
        questions.append({"text": text, "type": q_type, "options": options})

    return questions
