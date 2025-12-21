import sqlite3
from flask import g, current_app


def get_db() -> sqlite3.Connection:
    """
    Flask request context 단위로 sqlite connection 재사용
    """
    if "db_conn" not in g:
        settings = current_app.config["SETTINGS"]
        conn = sqlite3.connect(settings.sqlite_db_path)
        conn.row_factory = sqlite3.Row
        g.db_conn = conn
    return g.db_conn


def close_db(_e=None) -> None:
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
