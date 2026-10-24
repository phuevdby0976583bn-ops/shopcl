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
    can_delete = False
    can_edit = False
    can_create = False
    can_export = False
