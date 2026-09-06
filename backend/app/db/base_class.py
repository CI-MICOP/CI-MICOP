"""Shared SQLAlchemy declarative base.

All ORM models (backend/app/db_models/) inherit from this Base so that
Base.metadata carries the complete set of tables for Alembic autogenerate
and for Base.metadata.create_all() in tests.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
