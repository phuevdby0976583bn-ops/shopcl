from typing import Any
from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Integer, Column, String
from sqlalchemy.orm import relationship

from models.base import Base


class Category(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True, index=True)
    media_id = Column(String, nullable=False)
    items = relationship("Item", back_populates="category")
    cart_items = relationship("CartItem", back_populates="category")

    def __repr__(self):
        return self.name


class CategoryDTO(BaseModel):
    id: int | None = None
    name: str | None = None
    media_id: str | None = None


class CategoryAdmin(ModelView, model=Category):
    name = "Danh mục"
    name_plural = "Danh mục"
    icon = "fa-solid fa-folder"
    column_labels = {
        "id": "ID",
        "name": "Tên danh mục chính"
    }
    column_searchable_list = [Category.name]
    column_sortable_list = [Category.id, Category.name]
    column_exclude_list = [Category.items,
                           Category.media_id,
                           Category.cart_items]
    can_delete = True
    can_view_details = True
    can_edit = True
    can_create = True
    can_export = True

    async def delete_model(self, request, pk: Any) -> None:
        from models.cartItem import CartItem
        from models.item import Item
        from sqlalchemy import delete
        async with self.session_maker() as session:
            await session.execute(delete(CartItem).where(CartItem.category_id == int(pk)))
            await session.execute(delete(Item).where(Item.category_id == int(pk)))
            await session.execute(delete(Category).where(Category.id == int(pk)))
            await session.commit()
