from typing import Any
from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Integer, Column, String, Float
from sqlalchemy.orm import relationship

from models.base import Base


class Subcategory(Base):
    __tablename__ = 'subcategories'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True)
    price = Column(Float, nullable=True, default=0.0)
    description = Column(String, nullable=True, default="")
    media_id = Column(String, nullable=False, default="0no_image_default")
    items = relationship("Item", back_populates="subcategory")
    cart_items = relationship("CartItem", back_populates="subcategory")

    def __repr__(self):
        if self.price and float(self.price) > 0:
            return f"{self.name} (${float(self.price):g})"
        return self.name


class SubcategoryDTO(BaseModel):
    id: int | None = None
    name: str | None = None
    price: float | None = 0.0
    description: str | None = None
    media_id: str | None = None


class SubcategoryAdmin(ModelView, model=Subcategory):
    name = "Danh mục con"
    name_plural = "Danh mục con"
    icon = "fa-solid fa-folder-open"
    column_list = [
        Subcategory.id,
        Subcategory.name,
        Subcategory.price,
        Subcategory.description,
    ]
    column_labels = {
        "id": "ID",
        "name": "Tên danh mục con",
        "price": "Giá bán ($)",
        "description": "Mô tả sản phẩm",
        "media_id": "Media ID",
        "items": "Danh sách clone",
        "cart_items": "Trong giỏ hàng"
    }
    column_searchable_list = [Subcategory.name]
    column_sortable_list = [
        Subcategory.id,
        Subcategory.name,
        Subcategory.price
    ]

    form_excluded_columns = [
        Subcategory.items,
        Subcategory.cart_items
    ]
    form_widget_args = {
        "price": {
            "step": "0.01",
            "min": "0",
            "placeholder": "Nhập giá bán chung cho loại này (VD: 0.02, 0.25...)"
        },
        "description": {
            "placeholder": "Mô tả loại tài khoản này (VD: Clone Facebook ngâm 6 tháng, 2FA đầy đủ...)"
        }
    }
    can_delete = True
    can_edit = True
    can_create = True
    can_export = True

    async def after_model_change(self, data: dict, model: Any, is_created: bool, request) -> None:
        """Khi Admin sửa giá hoặc mô tả của Danh mục con, tự động đồng bộ sang tất cả các nick chưa bán!"""
        if model and hasattr(model, 'id'):
            from models.item import Item
            from sqlalchemy import update
            async with self.session_maker() as session:
                update_vals = {}
                if getattr(model, 'price', None) is not None and float(model.price) > 0:
                    update_vals['price'] = float(model.price)
                if getattr(model, 'description', None):
                    update_vals['description'] = str(model.description)
                if update_vals:
                    await session.execute(
                        update(Item)
                        .where(Item.subcategory_id == model.id, Item.is_sold == False)
                        .values(**update_vals)
                    )
                    await session.commit()

    async def delete_model(self, request, pk: Any) -> None:
        from models.cartItem import CartItem
        from models.item import Item
        from sqlalchemy import delete
        async with self.session_maker() as session:
            await session.execute(delete(CartItem).where(CartItem.subcategory_id == int(pk)))
            await session.execute(delete(Item).where(Item.subcategory_id == int(pk)))
            await session.execute(delete(Subcategory).where(Subcategory.id == int(pk)))
            await session.commit()
