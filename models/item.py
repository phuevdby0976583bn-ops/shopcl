from typing import Any
from markupsafe import Markup
try:
    from sqladmin import action
except ImportError:
    def action(*args, **kwargs):
        return lambda fn: fn
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
    price = Column(Float, nullable=True, default=0.0)
    is_sold = Column(Boolean, nullable=False, default=False)
    is_new = Column(Boolean, nullable=False, default=True)
    description = Column(String, nullable=True, default="")

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
        Item.description: lambda m, a: f"{m.description[:25]}..." if m.description else "",
        Item.is_sold: lambda m, a: Markup(
            '<span class="badge bg-danger text-white"><i class="fa-solid fa-check me-1"></i> Đã bán</span>'
            if m.is_sold
            else '<span class="badge bg-success text-white"><i class="fa-solid fa-box-open me-1"></i> Chưa bán</span>'
        ),
        Item.is_new: lambda m, a: Markup(
            '<span class="badge bg-secondary text-white"><i class="fa-solid fa-minus me-1"></i> Đã xuất kho</span>'
            if m.is_sold
            else '<span class="badge bg-primary text-white"><i class="fa-solid fa-sparkles me-1"></i> Hàng mới</span>'
        )
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
    can_view_details = True
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
        "price": {
            "step": "0.01",
            "min": "0",
            "placeholder": "💡 TÙY CHỌN: Để trống sẽ tự động lấy Giá bán từ Danh mục con đã chọn"
        },
        "description": {
            "rows": 3,
            "placeholder": "💡 TÙY CHỌN: Để trống sẽ tự động lấy Mô tả từ Danh mục con đã chọn"
        }
    }

    
    def list_query(self, request) -> Any:
        from sqlalchemy import select
        query = select(Item)
        status = request.query_params.get("status", "").lower() if hasattr(request, "query_params") else ""
        if status == "sold":
            query = query.where(Item.is_sold == True)
        elif status in ("new", "available", "unsold"):
            query = query.where(Item.is_sold == False)
        return query

    def count_query(self, request) -> Any:
        from sqlalchemy import func, select
        query = select(func.count(Item.id)).select_from(Item)
        status = request.query_params.get("status", "").lower() if hasattr(request, "query_params") else ""
        if status == "sold":
            query = query.where(Item.is_sold == True)
        elif status in ("new", "available", "unsold"):
            query = query.where(Item.is_sold == False)
        return query

    async def update_model(self, request, pk: str, data: dict):
        if data.get("is_sold") is True:
            data["is_new"] = False
        elif data.get("is_new") is True and data.get("is_sold") is not True:
            data["is_sold"] = False
        return await super().update_model(request, pk, data)

    @action(
        name="mark_sold",
        label="🏷️ Đánh dấu ĐÃ BÁN",
        confirmation_message="Bạn có chắc muốn chuyển các nick đã chọn thành trạng thái ĐÃ BÁN?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def mark_as_sold(self, request):
        from starlette.responses import RedirectResponse
        from sqlalchemy import update
        pks = request.query_params.get("pks", "").split(",")
        valid_ids = [int(pk) for pk in pks if pk.strip().isdigit()]
        if valid_ids:
            async with self.session_maker() as session:
                await session.execute(
                    update(Item).where(Item.id.in_(valid_ids)).values(is_sold=True, is_new=False)
                )
                await session.commit()
        referer = request.headers.get("Referer") or "/admin/item/list"
        return RedirectResponse(referer, status_code=302)

    @action(
        name="mark_new",
        label="✨ Đánh dấu HÀNG MỚI (Chưa bán)",
        confirmation_message="Bạn có chắc muốn chuyển các nick đã chọn thành HÀNG MỚI (Chưa bán)?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def mark_as_new(self, request):
        from starlette.responses import RedirectResponse
        from sqlalchemy import update
        pks = request.query_params.get("pks", "").split(",")
        valid_ids = [int(pk) for pk in pks if pk.strip().isdigit()]
        if valid_ids:
            async with self.session_maker() as session:
                await session.execute(
                    update(Item).where(Item.id.in_(valid_ids)).values(is_sold=False, is_new=True)
                )
                await session.commit()
        referer = request.headers.get("Referer") or "/admin/item/list"
        return RedirectResponse(referer, status_code=302)

    async def insert_model(self, request, data: dict):
        if not data.get("item_type"):
            data["item_type"] = ItemType.DIGITAL
        from sqladmin._queries import Query
        raw_text = data.get("private_data") or ""
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

        if not lines:
            raise ValueError("Vui lòng nhập ít nhất 1 tài khoản clone!")

        from services.facebook import (
            is_facebook_product,
            is_facebook_clone,
            scan_and_filter_facebook_raw_lines,
            extract_uid,
            check_uid_live_async,
            get_existing_uids_from_db
        )
        import config

        cat_obj = data.get("category")
        subcat_obj = data.get("subcategory")
        cat_name = getattr(cat_obj, "name", "")
        subcat_name = getattr(subcat_obj, "name", "")

        # TỰ ĐỘNG LẤY GIÁ BÁN & MÔ TẢ TỪ MỤC CON NẾU ĐỂ TRỐNG
        subcat_price = getattr(subcat_obj, "price", None)
        subcat_desc = getattr(subcat_obj, "description", None)

        user_price = data.get("price")
        if (user_price is None or str(user_price).strip() == "" or float(user_price or 0) <= 0):
            if subcat_price and float(subcat_price) > 0:
                data["price"] = float(subcat_price)
            else:
                data["price"] = 0.02
        else:
            data["price"] = float(user_price)
            if subcat_obj and (not subcat_price or float(subcat_price) <= 0):
                from models.subcategory import Subcategory
                from sqlalchemy import update
                async with self.session_maker() as session:
                    await session.execute(
                        update(Subcategory).where(Subcategory.id == subcat_obj.id).values(price=float(user_price))
                    )
                    await session.commit()

        user_desc = data.get("description")
        if not user_desc or not str(user_desc).strip():
            if subcat_desc and str(subcat_desc).strip():
                data["description"] = str(subcat_desc)
            else:
                data["description"] = f"Clone Facebook - {subcat_name}" if subcat_name else "Clone Facebook chất lượng cao"
        else:
            data["description"] = str(user_desc).strip()

        is_fb = is_facebook_product(cat_name, subcat_name) or any(
            is_facebook_clone(l) for l in lines[:10]
        )
        should_check = getattr(config, 'FB_AUTO_CHECK_ON_UPLOAD', True)
        should_delete = getattr(config, 'FB_AUTO_DELETE_DIE_ON_UPLOAD', True)
        should_filter_dups = getattr(config, 'FB_FILTER_DUPLICATE_UIDS', True)

        # TRƯỜNG HỢP 1: NGƯỜI DÙNG NHẬP 1 TÀI KHOẢN DUY NHẤT
        if len(lines) == 1:
            line = lines[0]
            uid = extract_uid(line)
            if uid and should_filter_dups:
                existing_uids = await get_existing_uids_from_db()
                if str(uid) in existing_uids:
                    raise ValueError(f"Tài khoản UID {uid} đã tồn tại trong kho hàng! Hệ thống từ chối thêm nick trùng lặp.")
            if is_fb and uid and should_check:
                status = await check_uid_live_async(uid)
                if status == "DIE" and should_delete:
                    raise ValueError(f"Tài khoản UID {uid} đã bị DIE (khóa/checkpoint)! Không thể thêm tài khoản DIE vào kho.")
            data["private_data"] = line
            return await Query(self).insert(data, request)

        # TRƯỜNG HỢP 2: DÁN NHIỀU DÒNG (HÀNG LOẠT 2 - 1000+ DÒNG)
        clean_lines, dead_lines, stats = await scan_and_filter_facebook_raw_lines(
            lines,
            check_live=(is_fb and should_check),
            delete_die=should_delete,
            filter_duplicates=should_filter_dups
        )

        if not clean_lines:
            dup_count = stats.get("duplicates", 0)
            die_count = stats.get("die", 0)
            raise ValueError(
                f"Không có tài khoản nào được thêm! ({dup_count} nick trùng UID, {die_count} nick DIE)."
            )

        data["private_data"] = clean_lines[0]
        first_obj = await Query(self).insert(data, request)

        if len(clean_lines) > 1:
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
                for line in clean_lines[1:]
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
