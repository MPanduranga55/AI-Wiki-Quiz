import os
from contextlib import contextmanager

import dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


# Load environment variables from backend/.env (if present) before reading DATABASE_URL
dotenv.load_dotenv()

# We only allow MySQL connections. The URL must start with mysql+pymysql://...
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or not DATABASE_URL.startswith("mysql"):
    raise RuntimeError(
        "DATABASE_URL must be set to a MySQL URL, e.g. "
        "'mysql+pymysql://root:Pandu%401005@localhost:3306/ai_quiz'"
    )

# Create the SQLAlchemy engine that talks to MySQL.
engine = create_engine(DATABASE_URL)

# SessionLocal is a factory for DB sessions; each request gets its own session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is the parent class for all ORM models.
Base = declarative_base()


@contextmanager
def get_session():
    """Yield a database session and make sure it closes after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


