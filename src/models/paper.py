from sqlalchemy import Column, DateTime, String, Text, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Paper(Base):
    __tablename__ = "papers"

    id = Column(String, primary_key=True)  # arXiv ID
    title = Column(String(500), nullable=False)
    abstract = Column(Text)
    full_text = Column(Text)
    authors = Column(Text)  # JSON string
    categories = Column(String(200))
    published_date = Column(DateTime)
    pdf_url = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
