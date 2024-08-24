from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import DATABASE_URI

# Create engine and base class
engine = create_engine(DATABASE_URI)
Base = declarative_base()

# Define models
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50))
    email = Column(String(100), unique=True)

class CVTemplate(Base):
    __tablename__ = 'cv_templates'
    id = Column(Integer, primary_key=True, index=True)
    template_name = Column(String(100))
    template_content = Column(Text)

# Create tables
Base.metadata.create_all(bind=engine)

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
