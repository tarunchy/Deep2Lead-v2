import click
from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config.settings import SECRET_KEY, DATABASE_URL
from models.db_models import db, User


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    Migrate(app, db)
    CORS(app)
    Limiter(get_remote_address, app=app, default_limits=["200/hour"])

    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)

    from api.auth import bp as auth_bp
    from api.experiments import bp as exp_bp
    from api.feed import bp as feed_bp
    from api.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(exp_bp)
    app.register_blueprint(feed_bp)
    app.register_blueprint(admin_bp)

    @app.cli.command("create-admin")
    @click.argument("username")
    @click.argument("password")
    @click.option("--cohort", default="Faculty")
    def create_admin(username, password, cohort):
        """Create an admin account. Usage: flask create-admin <username> <password>"""
        with app.app_context():
            if User.query.filter_by(username=username).first():
                click.echo(f"User '{username}' already exists.")
                return
            user = User(
                username=username,
                display_name=username,
                role="admin",
                cohort=cohort,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            click.echo(f"Admin '{username}' created successfully.")

    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=5018)
