from enum import StrEnum

from sqlalchemy import Enum, MetaData
from sqlalchemy.orm import DeclarativeBase

from forest_bot.domain.enums import DocStatus, ExtractionMethod, FileKind, ScopeLevel

# Deterministic constraint names, so Alembic migrations can refer to them.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    # Store the enum's values ("pending"), not its member names ("PENDING").
    return Enum(enum_cls, name=name, values_callable=lambda cls: [m.value for m in cls])


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {
        ScopeLevel: _pg_enum(ScopeLevel, "scope_level"),
        DocStatus: _pg_enum(DocStatus, "doc_status"),
        FileKind: _pg_enum(FileKind, "file_kind"),
        ExtractionMethod: _pg_enum(ExtractionMethod, "extraction_method"),
    }
