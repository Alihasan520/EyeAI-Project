from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        if url.startswith("sqlite:///"):
            db_path = Path(url.removeprefix("sqlite:///"))
            if str(db_path) != ":memory:":
                db_path.parent.mkdir(parents=True, exist_ok=True)
        kwargs = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, future=True, connect_args=kwargs)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )

    def create_all(self) -> None:
        from eyeai.product import models  # noqa: F401

        Base.metadata.create_all(self.engine)
        self._ensure_v11_columns()

    def _ensure_v11_columns(self) -> None:
        """Add display IDs when upgrading an existing Product Backend V1 database."""
        table_names = {
            "users",
            "patients",
            "visits",
            "predictions",
            "doctor_notes",
            "alerts",
            "reports",
        }
        inspector = inspect(self.engine)
        existing_tables = set(inspector.get_table_names())
        with self.engine.begin() as connection:
            for table_name in sorted(table_names & existing_tables):
                columns = {column["name"] for column in inspector.get_columns(table_name)}
                if "display_id" not in columns:
                    connection.execute(
                        text(
                            f'ALTER TABLE "{table_name}" '
                            'ADD COLUMN display_id VARCHAR(40)'
                        )
                    )
                connection.execute(
                    text(
                        f'CREATE UNIQUE INDEX IF NOT EXISTS '
                        f'"ux_{table_name}_display_id" '
                        f'ON "{table_name}" (display_id)'
                    )
                )

    @contextmanager
    def session(self) -> Iterator[Session]:
        database_session = self.session_factory()
        try:
            yield database_session
            database_session.commit()
        except Exception:
            database_session.rollback()
            raise
        finally:
            database_session.close()
