from flask import Flask
from flask_cors import CORS
import os

from src.config import Settings
from src.db.sqlite import init_app as init_db_app
from src.routes import face_bp, weather_bp, recommend_bp, stats_bp


def create_app() -> Flask:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
    )
    CORS(app)

    settings = Settings.load()
    app.config["SETTINGS"] = settings

    init_db_app(app)

    app.register_blueprint(face_bp)
    app.register_blueprint(weather_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(recommend_bp)

    @app.get("/health")
    def health():
        return {"ok": True}

    return app
