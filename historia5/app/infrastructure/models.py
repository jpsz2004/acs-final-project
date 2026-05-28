from __future__ import annotations

from sqlalchemy import Column, Float, ForeignKey, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    jobs = relationship("JobModel", back_populates="user", cascade="all, delete-orphan", lazy="selectin")


class JobModel(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False)

    user = relationship("UserModel", back_populates="jobs")
    texts = relationship("TextModel", back_populates="job", cascade="all, delete-orphan", lazy="joined")


class TextModel(Base):
    __tablename__ = "texts"

    id = Column(String(36), primary_key=True)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    language = Column(String(32), nullable=True)
    sentiment = Column(String(32), nullable=True)
    score = Column(Float, nullable=False, default=0.0)
    status = Column(String(32), nullable=False)
    error = Column(Text, nullable=True)

    job = relationship("JobModel", back_populates="texts")
