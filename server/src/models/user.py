import enum
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base


class UserRole(str, enum.Enum):
    ADMIN         = "ADMIN"
    BIZ_ADMIN     = "BIZ_ADMIN"
    SERVICE_OWNER = "SERVICE_OWNER"
    READ_ONLY     = "READ_ONLY"


class User(Base):
    __tablename__ = "users"

    id:              Mapped[int]      = mapped_column(primary_key=True, autoincrement=True)
    email:           Mapped[str]      = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name:       Mapped[str]      = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str]      = mapped_column(String(255), nullable=False)
    role:            Mapped[UserRole] = mapped_column(SAEnum(UserRole), nullable=False, default=UserRole.READ_ONLY)
    is_active:       Mapped[bool]     = mapped_column(Boolean, default=True, nullable=False)
    created_at:      Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at:      Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
