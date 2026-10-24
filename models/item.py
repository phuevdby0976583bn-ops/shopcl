from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, CheckConstraint, Enum
from sqlalchemy.orm import relationship
from wtforms import TextAreaField

from enums.item_type import ItemType
from models.base import Base


class Item(Base):
    __tablename__ = 'items'

    id = Column(Integer, primary_key=True)
    item_type = Column(Enum(ItemType), default=ItemType.DIGITAL, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    category = relationship("Category", back_populates="items")
    subcategory_id = Column(Integer, ForeignKey("subcategories.id", ondelete="CASCADE"), nullable=False)
    subcategory = relationship("Subcategory", back_populates="items")
    private_data = Column(String, nullable=True, unique=False)
    price = Column(Float, nullable=False)
    is_sold = Column(Boolean, nullable=False, default=False)
    is_new = Column(Boolean, nullable=False, default=True)
    description = Column(String, nullable=False)

    __table_args__ = (
        CheckConstraint('price > 0', name='check_price_positive'),
    )

    def __repr__(self):
        return f"Item ID:{self.id}"


class ItemDTO(BaseModel):
    id: int | None = None
    item_type: ItemType = ItemType.DIGITAL
    category_id: int | None = None
    category_name: str | None = None
    subcategory_id: int | None = None
    subcategory_name: str | None = None
    private_data: str | None = None
    price: float | None = None
    is_sold: bool | None = None
    is_new: bool | None = None
    description: str | None = None


class ItemAvailabilityDTO(BaseModel):
    item_type: ItemType
    category_id: int
    subcategory_id: int
    price: float
    description: str
    available_qty: int


class ItemAdmin(ModelView, model=Item):
    name = "Kho hàng"
    name_plural = "Kho hàng"
    icon = "fa-solid fa-box-archive"
    column_labels = {
        "id": "ID",
        "category": "Danh mục chính",
        "subcategory": "Loại clone (Mục con)",
        "private_data": "Tài khoản clone (1 nick / dòng)",
        "price": "Giá bán ($)",
        "is_sold": "Đã bán",
        "is_new": "Hàng mới",
        "description": "Mô tả sản phẩm"
    }
    column_exclude_list = [Item.category_id, Item.subcategory_id, Item.item_type]
    column_formatters = {
        Item.private_data: lambda m, a: (
            f"UID: {m.private_data.split('|')[0]} | {m.private_data[:20]}..."
            if (m.private_data and '|' in m.private_data)
            else (f"{m.private_data[:25]}..." if m.private_data else "")
        ),
        Item.description: lambda m, a: f"{m.description[:25]}..." if m.description else ""
    }
    column_searchable_list = [Item.private_data]
    column_sortable_list = [
        Item.id,
        Item.item_type,
        Item.is_sold,
        Item.is_new,
        Item.price,
        Item.description
    ]
    can_delete = True
    can_create = True
    can_edit = True
    can_export = True

    form_overrides = {
        "private_data": TextAreaField,
        "description": TextAreaField,
    }
    form_widget_args = {
        "private_data": {
            "rows": 12,
            "placeholder": (
                "💡 DÁN 1 HOẶC 1.000+ TÀI KHOẢN TẠI ĐÂY (Mỗi dòng 1 nick: UID|Pass|2FA...)\n"
                "⚡ Hệ thống tự động tách dòng và nạp tất cả tài khoản vào kho hàng!\n"
                "Ví dụ:\n"
                "10008892182|Pass123|2FA_CODE|mail@domain.com|mailpass\n"
                "10008892183|Pass456|2FA_CODE|mail@domain.com|mailpass\n\n"
                "👉 Mẹo: Bạn có thể vào menu '⚡ Nạp Hàng Loạt (1000+)' bên trái để chọn file .txt trực tiếp!"
            ),
            "style": "font-family: Consolas, monospace; font-size: 13px; line-height: 1.4;"
        },
        "description": {
            "rows": 3,
            "placeholder": "Mô tả sản phẩm (ví dụ: Clone Facebook ngâm 6 tháng, 2FA đầy đủ, bao login)"
        }
    }

    async def insert_model(self, request, data: dict):
        if not data.get("item_type"):
            data["item_type"] = ItemType.DIGITAL
        from sqladmin._queries import Query
        raw_text = data.get("private_data") or ""
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

        if len(lines) <= 1:
            return await Query(self).insert(data, request)

        from services.facebook import is_facebook_product, is_facebook_clone, scan_and_filter_facebook_raw_lines
        import config

        cat_obj = data.get("category")
        subcat_obj = data.get("subcategory")
        cat_name = getattr(cat_obj, "name", "")
        subcat_name = getattr(subcat_obj, "name", "")

        is_fb = is_facebook_product(cat_name, subcat_name) or any(
            is_facebook_clone(l) for l in lines[:10]
        )
        should_check = getattr(config, 'FB_AUTO_CHECK_ON_UPLOAD', True)
        should_delete = getattr(config, 'FB_AUTO_DELETE_DIE_ON_UPLOAD', True)

        if is_fb and should_check:
            clean_lines, dead_lines, stats = await scan_and_filter_facebook_raw_lines(
                lines, check_live=True, delete_die=should_delete
            )
            lines = clean_lines

        if not lines:
            data["private_data"] = "NONE (Tất cả tài khoản DIE đã bị loại bỏ)"
            return await Query(self).insert(data, request)

        data["private_data"] = lines[0]
        first_obj = await Query(self).insert(data, request)

        if len(lines) > 1:
            from db import get_db_session, session_commit
            cat_id = getattr(first_obj, "category_id", None) or getattr(data.get("category"), "id", None)
            subcat_id = getattr(first_obj, "subcategory_id", None) or getattr(data.get("subcategory"), "id", None)

            extra_items = [
                Item(
                    item_type=first_obj.item_type,
                    category_id=cat_id,
                    subcategory_id=subcat_id,
                    private_data=line,
                    price=first_obj.price,
                    is_sold=first_obj.is_sold,
                    is_new=first_obj.is_new,
                    description=first_obj.description
                )
                for line in lines[1:]
            ]
            async with get_db_session() as session:
                session.add_all(extra_items)
                await session_commit(session)

        return first_obj

    async def get_object_for_delete(self, value):
        obj = await super().get_object_for_delete(value)
        if obj is None:
            return Item(id=int(value) if str(value).isdigit() else 0)
        return obj

    async def delete_model(self, request, pk):
        try:
            await super().delete_model(request, pk)
        except Exception:
            pass
