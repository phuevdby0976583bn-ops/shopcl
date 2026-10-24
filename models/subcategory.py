from typing import Any
from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Integer, Column, String
from sqlalchemy.orm import relationship

from models.base import Base


class Subcategory(Base):
    __tablename__ = 'subcategories'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True)
    media_id = Column(String, nullable=False)
    items = relationship("Item", back_populates="subcategory")
    cart_items = relationship("CartItem", back_populates="subcategory")

    def __repr__(self):
        return self.name


class SubcategoryDTO(BaseModel):
    id: int | None = None
    name: str | None = None
    media_id: str | None = None


class SubcategoryAdmin(ModelView, model=Subcategory):
    name = "Danh mục con"
    name_plural = "Danh mục con"
    icon = "fa-solid fa-folder-open"
    column_labels = {
        "id": "ID",
        "name": "Tên danh mục con"
    }
    column_searchable_list = [Subcategory.name]
    column_sortable_list = [Subcategory.id,
                            Subcategory.name]
    column_exclude_list = [Subcategory.items,
                           Subcategory.media_id,
                           Subcategory.cart_items]
    can_delete = True
    can_edit = True
    can_create = True
    can_export = True

    async def delete_model(self, request, pk: Any) -> None:
        from models.cartItem import CartItem
        from models.item import Item
        from sqlalchemy import delete
        async with self.session_maker() as session:
            await session.execute(delete(CartItem).where(CartItem.subcategory_id == int(pk)))
            await session.execute(delete(Item).where(Item.subcategory_id == int(pk)))
            await session.execute(delete(Subcategory).where(Subcategory.id == int(pk)))
            await session.commit()
