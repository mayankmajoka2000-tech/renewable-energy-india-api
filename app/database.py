import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "renewable_energy_india.db")
DEFAULT_SQLITE_URL = f"sqlite:///{DB_PATH}"

# Set DATABASE_URL (e.g. postgresql://user:pass@host:5432/dbname) to run
# against Postgres in production. Falls back to the bundled SQLite file for
# local/dev use — no config needed to just run it.
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_SQLITE_URL)

# The DB file itself isn't committed to git (it's ~119MB, over GitHub's
# 100MB limit -- see README), so a fresh clone has no data/ directory at
# all. sqlite3 fails with "unable to open database file" if the parent
# directory doesn't exist, so create it defensively before the engine
# ever tries to open a connection.
if DATABASE_URL.startswith("sqlite"):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import Base
    Base.metadata.create_all(bind=engine)
