from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from . import config
url = config.DATABASE_URL.replace("postgres://", "postgresql://", 1)
engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
