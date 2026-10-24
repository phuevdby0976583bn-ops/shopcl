from fastapi import APIRouter, Header, HTTPException, status, Request
from typing import Any
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


@api_router.get("/binancepay/status")
async def binance_pay_status(x_api_key: str = Header(None)):
    valid_keys = [config.SQLADMIN_RAW_PASSWORD, config.JWT_SECRET_KEY]
    if not x_api_key or x_api_key not in valid_keys:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai ma X-API-KEY!")

    is_configured = bool(config.BINANCE_API_KEY and config.BINANCE_API_SECRET)
    from models.binance_pay import BinancePayOrder
    from sqlalchemy import func

    async with get_db_session() as session:
        stmt_pending = select(func.count(BinancePayOrder.id)).where(BinancePayOrder.status == "PENDING")
        pending_cnt = (await session.execute(stmt_pending)).scalar_one()

        stmt_comp = select(func.count(BinancePayOrder.id)).where(BinancePayOrder.status == "COMPLETED")
        completed_cnt = (await session.execute(stmt_comp)).scalar_one()

        return {
            "status": "success",
            "is_configured": is_configured,
            "binance_uid": config.BINANCE_UID,
            "pending_orders": pending_cnt,
            "completed_orders": completed_cnt
        }


@api_router.post("/binancepay/check-now")
async def binance_pay_check_now(x_api_key: str = Header(None)):
    valid_keys = [config.SQLADMIN_RAW_PASSWORD, config.JWT_SECRET_KEY]
    if not x_api_key or x_api_key not in valid_keys:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai ma X-API-KEY!")

    from services.binance_pay import BinancePayService
    from bot import bot

    async with get_db_session() as session:
        credited = await BinancePayService.process_and_credit_transactions(bot, session)
        return {
            "status": "success",
            "credited_count": len(credited),
            "credited": credited
        }


class SettingsUpdateRequest(BaseModel):
    settings: dict[str, Any]


@api_router.post("/settings/save")
async def save_settings_endpoint(payload: SettingsUpdateRequest, request: Request, x_api_key: str = Header(None)):
    token = request.session.get("token") if hasattr(request, "session") else None
    from utils.utils import decode_token
    is_session_valid = bool(token and decode_token(token))
    valid_keys = [config.SQLADMIN_RAW_PASSWORD, config.JWT_SECRET_KEY]
    is_api_key_valid = bool(x_api_key and x_api_key in valid_keys)

    if not is_session_valid and not is_api_key_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ch?a ??ng nh?p Admin ho?c sai API Key!")

    from services.settings import SettingsService
    async with get_db_session() as session:
        result = await SettingsService.save_settings(payload.settings, session)
        return {
            "status": "success",
            "message": "?? l?u c?i ??t th?nh c?ng v?o Database Supabase! C?u h?nh c? hi?u l?c ngay l?p t?c.",
            "saved_keys": result.get("saved_keys", [])
        }


@api_router.get("/settings/current")
async def get_settings_endpoint(request: Request, x_api_key: str = Header(None)):
    token = request.session.get("token") if hasattr(request, "session") else None
    from utils.utils import decode_token
    is_session_valid = bool(token and decode_token(token))
    valid_keys = [config.SQLADMIN_RAW_PASSWORD, config.JWT_SECRET_KEY]
    is_api_key_valid = bool(x_api_key and x_api_key in valid_keys)

    if not is_session_valid and not is_api_key_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ch?a ??ng nh?p Admin ho?c sai API Key!")

    from services.settings import SettingsService
    async with get_db_session() as session:
        return await SettingsService.get_all_settings(session)
