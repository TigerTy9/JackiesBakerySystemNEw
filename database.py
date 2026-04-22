import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Inside Docker, 'db' is the hostname of the postgres container
# Format: postgresql://user:password@hostname:port/dbname
DATABASE_URL = "postgresql://ty_admin:westen6growling9crystals6truly4renee3turning9vile6ignited2police@db:5432/bakery_saas"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()