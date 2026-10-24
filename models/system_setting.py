from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, func
from models.base import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"SystemSetting({self.key}={self.value})"
