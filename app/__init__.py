import os

from flask import Flask

from config import (DATA_DIR, DB_PATH, ICON_DIR, MED_PHOTO_DIR, TIMEZONE,
                    SECRET_KEY, BASE_URL)
from .models import db, ensure_schema
from .assets import ensure_assets
from .seed import seed_defaults


def create_app():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(MED_PHOTO_DIR, exist_ok=True)

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + DB_PATH.replace('\\', '/')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TIMEZONE'] = TIMEZONE
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['BASE_URL'] = BASE_URL

    db.init_app(app)
    with app.app_context():
        db.create_all()
        ensure_schema()
        ensure_assets(app)
        seed_defaults()

    from .routes.main import main_bp
    from .routes.api import api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    @app.context_processor
    def inject_settings():
        import os
        from .models import Setting
        custom = os.path.join(DATA_DIR, 'icons', 'custom-icon.png')
        use_custom = os.path.exists(custom)
        version = Setting.get('icon_version', '')
        return {
            'app_name': Setting.get('app_name', 'Напоминания'),
            'app_icon': Setting.get('app_icon', '💊'),
            'app_icon_url': (f'/icon-192.png?v={version}') if use_custom else None,
            'icon_version': version,
        }

    from .scheduler import SchedulerManager
    sched = SchedulerManager(app)
    sched.start()
    app.scheduler = sched

    return app
