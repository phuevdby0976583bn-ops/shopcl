from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
import config
from db import get_db_session, session_commit
from enums.item_type import ItemType
from models.category import Category
from models.subcategory import Subcategory
from models.item import Item

api_router = APIRouter(prefix="/api", tags=["API Upload Hàng Tự Động"])


class BulkUploadRequest(BaseModel):
    category_name: str
    subcategory_name: str
    price: float
    description: str = "Tài khoản chất lượng cao"
    items: list[str]


@api_router.post("/items/bulk-upload")
async def bulk_upload_items(payload: BulkUploadRequest, x_api_key: str = Header(None)):
    # Kiem tra quyen truy cap bang mat khau Admin
    valid_keys = [config.SQLADMIN_RAW_PASSWORD, config.JWT_SECRET_KEY]
    if not x_api_key or x_api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai ma X-API-KEY! Vui long truyen dung mat khau Admin cua ban."
        )

    if not payload.items:
        raise HTTPException(status_code=400, detail="Danh sach items rong!")

    async with get_db_session() as session:
        # 1. Tim hoac tu dong tao Category
        cat_stmt = select(Category).where(Category.name == payload.category_name.strip())
        cat_res = await session.execute(cat_stmt)
        category = cat_res.scalar_one_or_none()
        if not category:
            category = Category(name=payload.category_name.strip(), media_id="0no_image_default")
            session.add(category)
            await session.flush()

        # 2. Tim hoac tu dong tao Subcategory
        subcat_stmt = select(Subcategory).where(
            Subcategory.name == payload.subcategory_name.strip(),
            Subcategory.id.in_(
                select(Item.subcategory_id).where(Item.category_id == category.id)
            ) if False else Subcategory.name == payload.subcategory_name.strip()
        )
        subcat_res = await session.execute(subcat_stmt)
        subcategory = subcat_res.scalar_one_or_none()
        if not subcategory:
            subcategory = Subcategory(name=payload.subcategory_name.strip(), media_id="0no_image_default")
            session.add(subcategory)
            await session.flush()

        # 3. Tao danh sach Items nap vao kho
        items_to_add = []
        for line in payload.items:
            clean_line = line.strip()
            if clean_line:
                item = Item(
                    item_type=ItemType.DIGITAL,
                    category_id=category.id,
                    subcategory_id=subcategory.id,
                    private_data=clean_line,
                    price=float(payload.price),
                    is_sold=False,
                    is_new=True,
                    description=payload.description
                )
                items_to_add.append(item)

        session.add_all(items_to_add)
        await session_commit(session)

        return {
            "status": "success",
            "message": f"Da nap thanh cong {len(items_to_add)} san pham vao kho!",
            "category_id": category.id,
            "category_name": category.name,
            "subcategory_id": subcategory.id,
            "subcategory_name": subcategory.name,
            "uploaded_count": len(items_to_add),
            "price_per_item": payload.price
        }


@api_router.get("/inventory/status")
async def inventory_status(x_api_key: str = Header(None)):
    valid_keys = [config.SQLADMIN_RAW_PASSWORD, config.JWT_SECRET_KEY]
    if not x_api_key or x_api_key not in valid_keys:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai ma X-API-KEY!")

    async with get_db_session() as session:
        stmt = select(Category)
        categories = (await session.execute(stmt)).scalars().all()

        result = []
        for cat in categories:
            items_stmt = select(Item).where(Item.category_id == cat.id, Item.is_sold == False)
            unsold_items = (await session.execute(items_stmt)).scalars().all()
            result.append({
                "category_id": cat.id,
                "category_name": cat.name,
                "in_stock_qty": len(unsold_items)
            })

        return {"inventory": result}
