"""WSGI entrypoint for production servers (gunicorn/uwsgi)."""

import os

from dotenv import load_dotenv

from app import create_app

load_dotenv()

app = create_app(os.environ.get("FLASK_CONFIG") or "production")

