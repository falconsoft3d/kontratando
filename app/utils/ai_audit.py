import json

from flask import current_app
from openai import OpenAI


class AIAuditError(Exception):
    pass


def _get_client() -> OpenAI:
    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key:
        raise AIAuditError(
            "No se configuró OPENAI_API_KEY. Defínela en el archivo .env para habilitar la auditoría con IA."
        )
    return OpenAI(api_key=api_key)


def audit_application(job_posting, resume_text: str, qa_pairs: list, reviewer_comments: list | None = None) -> dict:
    """Usa un modelo de OpenAI para calificar el CV y las respuestas de un candidato.

    Devuelve un dict: {"score": float 0-100, "feedback": str}
    """
    client = _get_client()
    model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")

    qa_text = "\n".join(
        f"Pregunta: {qa['question']}\nRespuesta: {qa['answer'] or '(sin respuesta)'}" for qa in qa_pairs
    )

    comments_text = "\n".join(f"- {comment}" for comment in (reviewer_comments or []))

    system_prompt = (
        "Eres un reclutador experto de Recursos Humanos con formación en psicología organizacional. "
        "Evalúas de forma objetiva y profesional el currículum, las respuestas de un candidato y las notas "
        "internas del equipo de contratación (por ejemplo, comentarios de entrevistas) para un puesto específico. "
        "Responde EXCLUSIVAMENTE en formato JSON válido con las claves: "
        "'score' (número entero de 1 a 100, donde 1 es un candidato totalmente inadecuado y 100 es un candidato "
        "ideal; nunca uses 0), "
        "'feedback' (texto breve en español explicando fortalezas, debilidades y recomendación final sobre la "
        "idoneidad para el puesto), y "
        "'psychological_summary' (un resumen psicológico breve y profesional en español, basado únicamente en las "
        "respuestas del candidato a las preguntas del puesto, describiendo rasgos de personalidad, estilo de "
        "comunicación, motivación y posibles señales de alerta observadas; no es un diagnóstico clínico, es solo "
        "una orientación para el reclutador)."
    )

    user_prompt = (
        f"Puesto: {job_posting.title}\n"
        f"Descripción del puesto:\n{job_posting.description}\n\n"
        f"Currículum del candidato (texto extraído del PDF):\n{resume_text or '(no se adjuntó currículum)'}\n\n"
        f"Preguntas y respuestas del candidato:\n{qa_text or '(sin preguntas asignadas)'}\n\n"
        f"Comentarios internos del equipo de contratación (entrevistas u otras notas):\n"
        f"{comments_text or '(sin comentarios registrados)'}\n\n"
        "Evalúa la idoneidad del candidato para este puesto, teniendo en cuenta también los comentarios internos, "
        "y elabora el resumen psicológico solicitado basándote en sus respuestas."
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    content = response.choices[0].message.content
    try:
        data = json.loads(content)
        score = float(data.get("score", 0))
        feedback = str(data.get("feedback", "")).strip()
        psychological_summary = str(data.get("psychological_summary", "")).strip()
    except (ValueError, TypeError, json.JSONDecodeError):
        score = 1.0
        feedback = "No se pudo interpretar la respuesta de la IA."
        psychological_summary = ""

    score = max(1.0, min(100.0, score))
    return {"score": score, "feedback": feedback, "psychological_summary": psychological_summary}
