"""데이터베이스 스키마 마이그레이션 - AI 분류 필드 추가"""
import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app import create_app, db
from sqlalchemy import text

def _normalize_db_uri(db_value: str | None) -> str | None:
    if not db_value:
        return None
    db_uri = db_value.strip()
    if db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql+psycopg://", 1)
    elif db_uri.startswith("postgresql://"):
        db_uri = db_uri.replace("postgresql://", "postgresql+psycopg://", 1)
    if not db_uri.startswith("postgresql+psycopg://"):
        raise RuntimeError(
            "--db must be a PostgreSQL URI (postgresql+psycopg://...). "
            "Non-PostgreSQL DB path/URI is no longer supported."
        )
    return db_uri


def migrate(db_uri: str | None = None, config_name: str = "default"):
    app = create_app(
        config_name,
        db_uri_override=db_uri,
        skip_migration_check=True,
    )
    with app.app_context():
        # Add new columns to questions table
        columns_to_add = [
            "ALTER TABLE questions ADD COLUMN ai_suggested_lecture_id INTEGER REFERENCES lectures(id)",
            "ALTER TABLE questions ADD COLUMN ai_final_lecture_id INTEGER REFERENCES lectures(id)",
            "ALTER TABLE questions ADD COLUMN ai_suggested_lecture_title_snapshot VARCHAR(300)",
            "ALTER TABLE questions ADD COLUMN ai_confidence FLOAT",
            "ALTER TABLE questions ADD COLUMN ai_reason TEXT",
            "ALTER TABLE questions ADD COLUMN ai_model_name VARCHAR(100)",
            "ALTER TABLE questions ADD COLUMN ai_classified_at TIMESTAMP",
            "ALTER TABLE questions ADD COLUMN classification_status VARCHAR(20) DEFAULT 'manual'",
        ]
        
        for col_sql in columns_to_add:
            try:
                db.session.execute(text(col_sql))
                col_name = col_sql.split("ADD COLUMN ")[1].split()[0]
                print(f"Added: {col_name}")
            except Exception as e:
                db.session.rollback()
                col_name = col_sql.split("ADD COLUMN ")[1].split()[0]
                msg = str(e).lower()
                if "duplicate column" in msg or "already exists" in msg:
                    print(f"Already exists: {col_name}")
                else:
                    print(f"Skipped {col_name}: {e}")
        
        # Create classification_jobs table if not exists
        db.create_all()
        print('Created classification_jobs table if not exists')
        
        db.session.commit()
        print('Schema migration complete!')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db",
        help="PostgreSQL URI override (postgresql+psycopg://...).",
    )
    parser.add_argument(
        "--config",
        default="default",
        help="Config name: development|production|local_admin|default",
    )
    args = parser.parse_args()
    migrate(_normalize_db_uri(args.db), config_name=args.config)
