"""Base declarativa compartilhada por todos os modelos ORM."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Classe base para todos os modelos SQLAlchemy do projeto."""
