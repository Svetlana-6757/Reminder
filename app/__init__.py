import os

from flask import Flask

from config import DATA_DIR, DB_PATH, TIMEZONE, SECRET_KEY, BASE_URL
from .models import db
from .assets import ensure_assets
from .seed import seed_defaults


def create_app():
    os.makedirs(DATA_DIR, exist_ok=True)

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + DB_PATH.replace('\\', '/')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TIMEZONE'] = TIMEZONE
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['BASE_URL'] = BASE_URL

    db.init_app(app)
    with app.app_context():
        db.create_all()
        ensure_assets(app)
        seed_defaults()

    from .routes.main import main_bp
    from .routes.api import api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    @app.context_processor
    def inject_settings():
        from .models import Setting
        return {
            'app_name': Setting.get('app_name', 'Напоминания'),
            'app_icon': Setting.get('app_icon', '💊'),
        }

    from .scheduler import SchedulerManager
    sched = SchedulerManager(app)
    sched.start()
    app.scheduler = sched

    return app
