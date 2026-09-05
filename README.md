# Kontratando

Aplicación web para gestionar el proceso de contratación de una empresa, construida con **Flask** y **PostgreSQL**.

## Funcionalidades

- **Home** con los datos de la empresa y los puestos publicados.
- **Registro/login de candidatos**. Si el correo está en la lista negra, la cuenta se invalida automáticamente al registrarse.
- **Panel de administración**:
  - Editar los datos de la empresa.
  - Crear puestos, publicarlos o dejarlos como borrador.
  - Asignar preguntas personalizadas a cada puesto.
  - Gestionar la lista negra de candidatos.
  - Revisar postulaciones, con **auditoría automática por IA** (OpenAI) que califica el currículum (PDF) y las respuestas del candidato del 0 al 100 con retroalimentación.
- Estilo visual serio, inspirado en LinkedIn.

## Requisitos

- Python 3.11 o 3.12 (psycopg2-binary no soporta Python 3.14 aún).
- PostgreSQL en ejecución.

## Puesta en marcha

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edita .env con tu DATABASE_URL, SECRET_KEY y OPENAI_API_KEY

# Crea la base de datos en Postgres (ejemplo)
createdb kontratando

# Migraciones
flask --app run.py db init
flask --app run.py db migrate -m "Modelos iniciales"
flask --app run.py db upgrade

# Crea el usuario administrador inicial (usa ADMIN_EMAIL/ADMIN_PASSWORD del .env)
flask --app run.py seed-admin

# Ejecutar en desarrollo
flask --app run.py run --debug
```

Ingresa al panel en `/admin` con el usuario administrador creado.

## Variables de entorno relevantes

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Cadena de conexión a PostgreSQL |
| `SECRET_KEY` | Clave secreta de Flask |
| `OPENAI_API_KEY` | Llave de OpenAI usada para auditar CV y respuestas |
| `OPENAI_MODEL` | Modelo de OpenAI a usar (por defecto `gpt-4o-mini`) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Credenciales del administrador inicial (`seed-admin`) |
