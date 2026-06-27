from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from src.config.settings import settings

# Create engine. SQLite needs check_same_thread=False for concurrent access
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db() -> None:
    """Initializes tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
    # Gracefully add 'subtype' column to 'sessions' table if not exists (SQLite-friendly)
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN subtype VARCHAR"))
    except Exception:
        pass # If already exists or other database, ignore
    # Gracefully add 'active_mode' column to 'sessions' table if not exists
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN active_mode VARCHAR DEFAULT 'PLAN'"))
    except Exception:
        pass
    # Gracefully add 'auto_execute' column to 'sessions' table if not exists
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN auto_execute BOOLEAN DEFAULT 0"))
    except Exception:
        pass

def get_db():
    """Dependency for obtaining database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
