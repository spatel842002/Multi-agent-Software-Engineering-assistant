from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class RepositoryStatus(enum.StrEnum):
    PENDING = "pending"
    CLONING = "cloning"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class Repository(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repositories"

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RepositoryStatus] = mapped_column(
        Enum(RepositoryStatus, native_enum=False), default=RepositoryStatus.PENDING, index=True
    )
    status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    symbol_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)

    files: Mapped[list[IngestedFile]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )


class IngestedFile(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "ingested_files"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(64), default="text")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    repository: Mapped[Repository] = relationship(back_populates="files")
    symbols: Mapped[list[Symbol]] = relationship(back_populates="file", cascade="all, delete-orphan")


class SymbolKind(enum.StrEnum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"


class Symbol(UUIDPKMixin, Base):
    __tablename__ = "symbols"

    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingested_files.id", ondelete="CASCADE"), index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[SymbolKind] = mapped_column(Enum(SymbolKind, native_enum=False))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    qualified_name: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    docstring: Mapped[str | None] = mapped_column(Text, nullable=True)

    file: Mapped[IngestedFile] = relationship(back_populates="symbols")


class Chunk(UUIDPKMixin, Base):
    __tablename__ = "chunks"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingested_files.id", ondelete="CASCADE"), index=True
    )
    symbol_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("symbols.id", ondelete="SET NULL"), nullable=True
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Text-search vector is added via a raw Alembic migration (Postgres tsvector),
    # since SQLAlchemy's ORM layer doesn't model computed tsvector columns natively.
