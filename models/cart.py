from typing import Any
from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

from models.base import Base


class Cart(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship("User", back_populates="cart", uselist=False)
    cart_items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")

    def __repr__(self):
        return f"Cart ID:{self.id}"


class CartDTO(BaseModel):
    id: int | None = None
    user_id: int | None = None


class CartAdmin(ModelView, model=Cart):
    name = "Giỏ hàng"
    name_plural = "Giỏ hàng"
    icon = "fa-solid fa-basket-shopping"
    column_labels = {
        "id": "ID",
        "user": "Khách hàng"
    }
    column_sortable_list = [Cart.id]
    column_exclude_list = [Cart.user_id, Cart.cart_items]
    can_delete = True
    can_view_details = True
    can_edit = True
    can_create = False
    can_export = True

    async def delete_model(self, request, pk: Any) -> None:
        from models.cartItem import CartItem
        from sqlalchemy import delete
        async with self.session_maker() as session:
            await session.execute(delete(CartItem).where(CartItem.cart_id == int(pk)))
            await session.execute(delete(Cart).where(Cart.id == int(pk)))
            await session.commit()
