"""애플리케이션 엔트리포인트."""

import os

from dotenv import load_dotenv

from app import create_app


def _ensure_database_url() -> None:
    """Prefer explicit DATABASE_URL; otherwise build a local Postgres URI."""
    if os.environ.get("DATABASE_URL"):
        return

    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    db_name = os.environ.get("POSTGRES_DB")
    if not (user and password and db_name):
        return

    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port = os.environ.get("POSTGRES_PORT", "5432")
    os.environ["DATABASE_URL"] = (
        f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}"
    )


# Load docker defaults first, then allow local .env to override.
load_dotenv(".env.docker")
load_dotenv(".env", override=True)
_ensure_database_url()

# 앱 인스턴스 생성
app = create_app(os.environ.get("FLASK_CONFIG") or "default")

if __name__ == "__main__":
    flask_config = os.environ.get("FLASK_CONFIG", "default")
    debug = flask_config != "production" and os.environ.get(
        "FLASK_DEBUG", "0"
    ).lower() in ("1", "true", "yes", "on")
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=debug, port=port)
