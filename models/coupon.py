from typing import Any
from datetime import datetime, timezone, timedelta

from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, DateTime, Enum, Boolean, String, Integer, Numeric
from sqlalchemy.orm import relationship

from enums.coupon_type import CouponType
from models.base import Base


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=True)
    code = Column(String(12), unique=True, nullable=False, index=True)
    type = Column(Enum(CouponType), nullable=False)
    value = Column(Numeric(10, 2), nullable=False)
    create_datetime = Column(DateTime(timezone=True), nullable=False)
    expire_datetime = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)
    usage_limit = Column(Integer, default=1)
    usage_count = Column(Integer, default=0)
    buys = relationship("Buy", back_populates="coupon")

    def __repr__(self):
        return f"Coupon: {self.name}"


class CouponDTO(BaseModel):
    id: int | None = None
    name: str | None = None
    code: str | None = None
    type: CouponType | None = None
    value: float | None = None
    create_datetime: datetime = datetime.now(tz=timezone.utc)
    expire_datetime: datetime = datetime.now(tz=timezone.utc) + timedelta(days=30)
    is_active: bool = True
    usage_limit: int = 1
    usage_count: int = 0


class CouponAdmin(ModelView, model=Coupon):
    name = "Mã giảm giá"
    name_plural = "Mã giảm giá"
    icon = "fa-solid fa-ticket"
    column_labels = {
        "id": "ID",
        "name": "Tên chương trình",
        "code": "Mã Coupon",
        "type": "Loại giảm giá",
        "value": "Giá trị giảm",
        "create_datetime": "Ngày tạo",
        "expire_datetime": "Ngày hết hạn",
        "is_active": "Kích hoạt",
        "usage_limit": "Giới hạn dùng",
        "usage_count": "Đã dùng"
    }
    column_exclude_list = [Coupon.buys]
    column_searchable_list = [Coupon.name]
    column_sortable_list = [Coupon.id,
                            Coupon.name,
                            Coupon.code,
                            Coupon.type,
                            Coupon.value,
                            Coupon.create_datetime,
                            Coupon.expire_datetime,
                            Coupon.is_active,
                            Coupon.usage_limit,
                            Coupon.usage_count]
    can_edit = True
    can_create = True
    can_delete = True
    can_view_details = True
    can_export = True

    async def delete_model(self, request, pk: Any) -> None:
        from models.buy import Buy
        from sqlalchemy import update, delete
        async with self.session_maker() as session:
            await session.execute(update(Buy).where(Buy.coupon_id == int(pk)).values(coupon_id=None))
            await session.execute(delete(Coupon).where(Coupon.id == int(pk)))
            await session.commit()
