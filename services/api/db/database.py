import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.api.db.models import Base


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://aerotwin:aerotwin_dev_password@localhost:5432/aerotwin",
)

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


Base.metadata.create_all(bind=engine)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)
