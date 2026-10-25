from typing import Any
from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, String, Float, Boolean, Integer
from sqlalchemy.orm import relationship

from models.base import Base


class ShippingOption(Base):
    __tablename__ = "shipping_options"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    price = Column(Float, nullable=False)
    is_disabled = Column(Boolean, default=False)
    buys = relationship("Buy", back_populates="shipping_option")

    def __repr__(self):
        return self.name


class ShippingOptionDTO(BaseModel):
    id: int | None = None
    name: str | None = None
    price: float | None = None
    is_disabled: bool = False


class ShippingOptionAdmin(ModelView, model=ShippingOption):
    name = "Vận chuyển"
    name_plural = "Vận chuyển"
    icon = "fa-solid fa-truck"
    column_labels = {
        "id": "ID",
        "name": "Phương thức",
        "price": "Phí ship ($)",
        "is_disabled": "Tạm dừng dùng"
    }
    column_exclude_list = [ShippingOption.buys]
    column_searchable_list = [ShippingOption.name]
    column_sortable_list = [ShippingOption.name,
                            ShippingOption.price,
                            ShippingOption.is_disabled]
    can_delete = True
    can_view_details = True
    can_edit = True
    can_create = True
    can_export = True

    async def delete_model(self, request, pk: Any) -> None:
        from models.buy import Buy
        from sqlalchemy import update, delete
        async with self.session_maker() as session:
            await session.execute(update(Buy).where(Buy.shipping_option_id == int(pk)).values(shipping_option_id=None))
            await session.execute(delete(ShippingOption).where(ShippingOption.id == int(pk)))
            await session.commit()
