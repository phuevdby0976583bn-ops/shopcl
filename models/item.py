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
        ),
        Item.price: lambda m, a: Markup(
            f'<span class="fw-bold text-success font-monospace">${float((m.subcategory.price if (not m.is_sold and m.subcategory and m.subcategory.price and float(m.subcategory.price) > 0) else m.price) or 0.02):g}</span>'
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
    page_size = 50
    page_size_options = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000]

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

        user_price = data.get("price")
        subcat_obj = data.get("subcategory")
        subcat_id = getattr(subcat_obj, "id", None) or (int(subcat_obj) if str(subcat_obj).isdigit() else None)
        if (user_price is None or str(user_price).strip() == "" or float(user_price or 0) <= 0) and subcat_id:
            from models.subcategory import Subcategory
            from sqlalchemy import select
            async with self.session_maker() as session:
                subcat_db = (await session.execute(select(Subcategory).where(Subcategory.id == subcat_id))).scalar_one_or_none()
                if subcat_db and subcat_db.price and float(subcat_db.price) > 0:
                    data["price"] = float(subcat_db.price)

        return await super().update_model(request, pk, data)

    @action(
        name="delete_selected",
        label="🗑️ Xoá các nick ĐÃ CHỌN (Nhanh)",
        confirmation_message="Bạn có chắc chắn muốn xoá vĩnh viễn các tài khoản đã chọn khỏi kho hàng?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def delete_selected(self, request):
        from starlette.responses import RedirectResponse
        from sqlalchemy import delete
        pks = request.query_params.get("pks", "").split(",")
        valid_ids = [int(pk) for pk in pks if pk.strip().isdigit()]
        if valid_ids:
            async with self.session_maker() as session:
                await session.execute(
                    delete(Item).where(Item.id.in_(valid_ids))
                )
                await session.commit()
        referer = request.headers.get("Referer") or "/admin/item/list"
        return RedirectResponse(referer, status_code=302)

    @action(
        name="mark_new",
        label="✨ Đặt lại: HÀNG MỚI (Chưa bán) (Các nick đã chọn)",
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

    @action(
        name="sync_subcat_price",
        label="💵 Đồng bộ giá theo Danh mục con",
        confirmation_message="Bạn có chắc muốn cập nhật lại giá của các nick đã chọn theo đúng giá của Danh mục con?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def sync_subcat_price(self, request):
        from starlette.responses import RedirectResponse
        from sqlalchemy import select
        from models.subcategory import Subcategory
        pks = request.query_params.get("pks", "").split(",")
        valid_ids = [int(pk) for pk in pks if pk.strip().isdigit()]
        if valid_ids:
            async with self.session_maker() as session:
                items_stmt = select(Item).where(Item.id.in_(valid_ids))
                items = (await session.execute(items_stmt)).scalars().all()
                for it in items:
                    if it.subcategory_id:
                        sub = (await session.execute(select(Subcategory).where(Subcategory.id == it.subcategory_id))).scalar_one_or_none()
                        if sub and sub.price and float(sub.price) > 0:
                            it.price = float(sub.price)
                await session.commit()
        referer = request.headers.get("Referer") or "/admin/item/list"
        return RedirectResponse(referer, status_code=302)

    @action(
        name="mark_sold",
        label="🏷️ Đặt lại: ĐÃ BÁN (Các nick đã chọn)",
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
        name="reset_all_unsold",
        label="🔄 Đặt lại TOÀN BỘ kho thành HÀNG MỚI (Chưa bán)",
        confirmation_message="Bạn có chắc chắn muốn đặt lại TẤT CẢ tài khoản trong kho thành Chưa bán (Hàng mới)?",
        add_in_detail=False,
        add_in_list=True,
    )
    async def reset_all_unsold(self, request):
        from starlette.responses import RedirectResponse
        from sqlalchemy import update
        async with self.session_maker() as session:
            await session.execute(
                update(Item).values(is_sold=False, is_new=True)
            )
            await session.commit()
        referer = request.headers.get("Referer") or "/admin/item/list"
        return RedirectResponse(referer, status_code=302)

    @action(
        name="mark_all_sold",
        label="🏷️ Đặt lại TOÀN BỘ kho thành ĐÃ BÁN",
        confirmation_message="Bạn có chắc chắn muốn chuyển TẤT CẢ tài khoản trong kho thành ĐÃ BÁN?",
        add_in_detail=False,
        add_in_list=True,
    )
    async def mark_all_sold(self, request):
        from starlette.responses import RedirectResponse
        from sqlalchemy import update
        async with self.session_maker() as session:
            await session.execute(
                update(Item).values(is_sold=True, is_new=False)
            )
            await session.commit()
        referer = request.headers.get("Referer") or "/admin/item/list"
        return RedirectResponse(referer, status_code=302)

    @action(
        name="delete_all_sold",
        label="🧹 Xoá TẤT CẢ tài khoản ĐÃ BÁN trong kho",
        confirmation_message="CẢNH BÁO: Thao tác này sẽ xoá vĩnh viễn tất cả nick ĐÃ BÁN trong kho (giữ lại nick chưa bán)?",
        add_in_detail=False,
        add_in_list=True,
    )
    async def delete_all_sold(self, request):
        from starlette.responses import RedirectResponse
        from sqlalchemy import delete
        async with self.session_maker() as session:
            await session.execute(
                delete(Item).where(Item.is_sold == True)
            )
            await session.commit()
        referer = request.headers.get("Referer") or "/admin/item/list"
        return RedirectResponse(referer, status_code=302)

    @action(
        name="scan_and_delete_die",
        label="⚡ Quét & Xoá tất cả nick Facebook DIE trong kho",
        confirmation_message="Hệ thống sẽ chạy kiểm tra toàn bộ nick Facebook chưa bán và xoá nick DIE khỏi kho. Tiếp tục?",
        add_in_detail=False,
        add_in_list=True,
    )
    async def scan_and_delete_die(self, request):
        from starlette.responses import RedirectResponse
        from services.facebook import scan_facebook_inventory
        async with self.session_maker() as session:
            await scan_facebook_inventory(session, auto_delete_die=True)
        referer = request.headers.get("Referer") or "/admin/item/list"
        return RedirectResponse(referer, status_code=302)

    @action(
        name="delete_all_inventory",
        label="⚠️ Xoá TOÀN BỘ kho hàng (Xoá trắng)",
        confirmation_message="CẢNH BÁO NGUY HIỂM: Thao tác này sẽ XOÁ TOÀN BỘ TẤT CẢ TÀI KHOẢN TRONG KHO HÀNG! Bạn có chắc chắn 100% muốn xoá sạch không?",
        add_in_detail=False,
        add_in_list=True,
    )
    async def delete_all_inventory(self, request):
        from starlette.responses import RedirectResponse
        from sqlalchemy import delete
        async with self.session_maker() as session:
            await session.execute(delete(Item))
            await session.commit()
        referer = request.headers.get("Referer") or "/admin/item/list"
        return RedirectResponse(referer, status_code=302)


    @action(
        name="view_all_uids",
        label="📋 Xem & Copy TOÀN BỘ UID trong kho",
        confirmation_message=None,
        add_in_detail=False,
        add_in_list=True,
    )
    async def view_all_uids(self, request):
        from starlette.responses import HTMLResponse
        from sqlalchemy import select
        async with self.session_maker() as session:
            stmt = select(Item.private_data).order_by(Item.id.asc())
            rows = (await session.execute(stmt)).scalars().all()
            uids = []
            for r in rows:
                if r:
                    uid = r.split("|")[0].strip()
                    if uid:
                        uids.append(uid)
            uids_text = "\n".join(uids)

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Toàn bộ UID trong kho ({len(uids)} nick)</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/core@latest/dist/css/tabler.min.css">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
        </head>
        <body class="p-4 bg-light">
            <div class="card shadow" style="max-width: 800px; margin: 30px auto;">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h3 class="card-title mb-0">📋 Toàn bộ UID Facebook trong kho ({len(uids)} tài khoản)</h3>
                    <a href="/admin/item/list" class="btn btn-sm btn-outline-secondary">⬅️ Quay lại Kho hàng</a>
                </div>
                <div class="card-body">
                    <div class="d-flex gap-2 mb-3">
                        <button class="btn btn-primary fw-bold" onclick="copyUids()">
                            <i class="fa-solid fa-copy me-1"></i> Sao chép tất cả ({len(uids)} UID)
                        </button>
                        <button class="btn btn-success fw-bold" onclick="downloadTxt()">
                            <i class="fa-solid fa-download me-1"></i> Tải file .txt
                        </button>
                        <span id="copied-msg" class="badge bg-success align-self-center py-2 px-3 fs-6 d-none">
                            ✅ Đã sao chép {len(uids)} UID vào Clipboard!
                        </span>
                    </div>
                    <textarea id="uid-area" class="form-control font-monospace" rows="22" readonly>{uids_text}</textarea>
                </div>
            </div>
            <script>
            function copyUids() {{
                const ta = document.getElementById('uid-area');
                ta.select();
                navigator.clipboard.writeText(ta.value).then(() => {{
                    const msg = document.getElementById('copied-msg');
                    msg.classList.remove('d-none');
                    setTimeout(() => msg.classList.add('d-none'), 3000);
                }});
            }}
            function downloadTxt() {{
                const text = document.getElementById('uid-area').value;
                const blob = new Blob([text], {{ type: 'text/plain;charset=utf-8' }});
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = 'danh_sach_uid_{len(uids)}_clone.txt';
                a.click();
            }}
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html)

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

        # Giai quyet ID hoac Object cho category va subcategory tu WTForms (QuerySelectField truyen PK)
        subcat_id = None
        if hasattr(subcat_obj, "id"):
            subcat_id = subcat_obj.id
        elif isinstance(subcat_obj, (int, str)) and str(subcat_obj).isdigit():
            subcat_id = int(subcat_obj)
        elif isinstance(subcat_obj, (tuple, list)) and subcat_obj and str(subcat_obj[0]).isdigit():
            subcat_id = int(subcat_obj[0])

        cat_id = None
        if hasattr(cat_obj, "id"):
            cat_id = cat_obj.id
        elif isinstance(cat_obj, (int, str)) and str(cat_obj).isdigit():
            cat_id = int(cat_obj)
        elif isinstance(cat_obj, (tuple, list)) and cat_obj and str(cat_obj[0]).isdigit():
            cat_id = int(cat_obj[0])

        from models.category import Category
        from models.subcategory import Subcategory
        from sqlalchemy import select

        async with self.session_maker() as session:
            if subcat_id and not hasattr(subcat_obj, "price"):
                subcat_db = (await session.execute(select(Subcategory).where(Subcategory.id == subcat_id))).scalar_one_or_none()
                if subcat_db:
                    subcat_obj = subcat_db
            if cat_id and not hasattr(cat_obj, "name"):
                cat_db = (await session.execute(select(Category).where(Category.id == cat_id))).scalar_one_or_none()
                if cat_db:
                    cat_obj = cat_db

        cat_name = getattr(cat_obj, "name", "")
        subcat_name = getattr(subcat_obj, "name", "")

        # TU DONG LAY GIA BAN & MO TA TU MUC CON
        subcat_price = getattr(subcat_obj, "price", None)
        subcat_desc = getattr(subcat_obj, "description", None)

        user_price = data.get("price")
        # Neu muc con da co gia: bat buoc mac dinh theo dung gia cua muc con
        if subcat_price and float(subcat_price) > 0:
            if user_price is None or str(user_price).strip() == "" or float(user_price or 0) <= 0:
                data["price"] = float(subcat_price)
            else:
                data["price"] = float(user_price)
        else:
            if user_price is not None and str(user_price).strip() != "" and float(user_price or 0) > 0:
                data["price"] = float(user_price)
                if subcat_id:
                    from sqlalchemy import update
                    async with self.session_maker() as session:
                        await session.execute(
                            update(Subcategory).where(Subcategory.id == subcat_id).values(price=float(user_price))
                        )
                        await session.commit()
            else:
                data["price"] = 0.02

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
            final_cat_id = getattr(first_obj, "category_id", None) or getattr(data.get("category"), "id", None) or cat_id
            final_subcat_id = getattr(first_obj, "subcategory_id", None) or getattr(data.get("subcategory"), "id", None) or subcat_id

            extra_items = [
                Item(
                    item_type=first_obj.item_type,
                    category_id=final_cat_id,
                    subcategory_id=final_subcat_id,
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
