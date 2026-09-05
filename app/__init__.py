import os

from flask import Flask

from app.config import Config
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.blueprints.main import bp as main_bp
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.admin import bp as admin_bp
    from app.blueprints.candidate import bp as candidate_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(candidate_bp)

    register_cli(app)

    @app.context_processor
    def inject_globals():
        from app.models import Company

        return {"site_company": Company.query.first()}

    return app


def register_cli(app):
    @app.cli.command("seed-admin")
    def seed_admin():
        """Crea el usuario administrador inicial si no existe ninguno."""
        from app.models import User

        if User.query.filter_by(role=User.ROLE_ADMIN).first():
            print("Ya existe un usuario administrador.")
            return

        admin = User(
            name="Administrador",
            email=app.config["ADMIN_EMAIL"].lower(),
            role=User.ROLE_ADMIN,
        )
        admin.set_password(app.config["ADMIN_PASSWORD"])
        db.session.add(admin)
        db.session.commit()
        print(f"Administrador creado: {admin.email}")
