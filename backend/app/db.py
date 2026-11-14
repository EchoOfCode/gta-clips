from sqlalchemy import create_engine, text
from app.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=3, max_overflow=2)


def check_database() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
