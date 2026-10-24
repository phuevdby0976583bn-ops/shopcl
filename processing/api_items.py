from fastapi import APIRouter, Header, HTTPException, status, Request
from typing import Any, Optional
from pydantic import BaseModel
from sqlalchemy import select
import config
from db import get_db_session, session_commit
from enums.item_type import ItemType
from models.category import Category
from models.subcategory import Subcategory
from models.item import Item

api_router = APIRouter(prefix="/api", tags=["API Upload Hàng Tự Động & Check Live"])


def is_request_authorized(request: Request, x_api_key: Optional[str] = None) -> bool:
    """Xác thực request qua X-API-KEY header hoặc qua Cookie Session của Admin."""
    valid_keys = [config.SQLADMIN_RAW_PASSWORD, config.JWT_SECRET_KEY]
    if x_api_key and x_api_key in valid_keys:
        return True

    token = None
    try:
        session_dict = request.scope.get("session")
        if isinstance(session_dict, dict):
            token = session_dict.get("token")
        if not token:
            try:
                token = request.session.get("token")
            except (AssertionError, AttributeError, Exception):
                token = None
    except Exception:
        token = None

    if token:
        from utils.utils import decode_token
        if decode_token(token):
            return True

    return False


class BulkUploadRequest(BaseModel):
    category_name: str
    subcategory_name: str
    price: float
    description: str = "Tài khoản chất lượng cao"
    items: list[str]
    is_facebook: Optional[bool] = None
    check_live: Optional[bool] = None
    delete_die: Optional[bool] = None


@api_router.post("/items/bulk-upload")
async def bulk_upload_items(payload: BulkUploadRequest, request: Request, x_api_key: str = Header(None)):
    if not is_request_authorized(request, x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai mã X-API-KEY hoặc chưa đăng nhập Admin!"
        )

    if not payload.items:
        raise HTTPException(status_code=400, detail="Danh sách items rỗng!")

    from services.facebook import is_facebook_product, is_facebook_clone, scan_and_filter_facebook_raw_lines

    if payload.is_facebook is not None:
        is_fb = payload.is_facebook
    else:
        is_fb = is_facebook_product(payload.category_name, payload.subcategory_name) or any(
            is_facebook_clone(line) for line in payload.items[:10]
        )

    should_check_live = (
        payload.check_live if payload.check_live is not None
        else getattr(config, 'FB_AUTO_CHECK_ON_UPLOAD', True)
    )
    should_delete_die = (
        payload.delete_die if payload.delete_die is not None
        else getattr(config, 'FB_AUTO_DELETE_DIE_ON_UPLOAD', True)
    )

    clean_lines = [line.strip() for line in payload.items if line and line.strip()]
    dead_lines = []
    stats = {"total": len(clean_lines), "live": len(clean_lines), "die": 0, "deleted": 0}

    if is_fb and should_check_live:
        clean_lines, dead_lines, stats = await scan_and_filter_facebook_raw_lines(
            payload.items,
            check_live=True,
            delete_die=should_delete_die
        )

    async with get_db_session() as session:
        # 1. Tìm hoặc tự động tạo Category
        cat_stmt = select(Category).where(Category.name == payload.category_name.strip())
        cat_res = await session.execute(cat_stmt)
        category = cat_res.scalar_one_or_none()
        if not category:
            category = Category(name=payload.category_name.strip(), media_id="0no_image_default")
            session.add(category)
            await session.flush()

        # 2. Tìm hoặc tự động tạo Subcategory
        subcat_stmt = select(Subcategory).where(
            Subcategory.name == payload.subcategory_name.strip()
        )
        subcat_res = await session.execute(subcat_stmt)
        subcategory = subcat_res.scalar_one_or_none()
        if not subcategory:
            subcategory = Subcategory(name=payload.subcategory_name.strip(), media_id="0no_image_default")
            session.add(subcategory)
            await session.flush()

        # 3. Tạo danh sách Items nạp vào kho
        items_to_add = []
        for line in clean_lines:
            item = Item(
                item_type=ItemType.DIGITAL,
                category_id=category.id,
                subcategory_id=subcategory.id,
                private_data=line,
                price=float(payload.price),
                is_sold=False,
                is_new=True,
                description=payload.description
            )
            items_to_add.append(item)

        if items_to_add:
            session.add_all(items_to_add)
            await session_commit(session)

        msg = (
            f"Đã quét và nạp thành công {len(items_to_add)} tài khoản LIVE vào kho! (Đã lọc bỏ {len(dead_lines)} tài khoản DIE)"
            if is_fb and should_check_live and should_delete_die and dead_lines
            else f"Đã nạp thành công {len(items_to_add)} sản phẩm vào kho!"
        )

        return {
            "status": "success",
            "message": msg,
            "is_facebook": is_fb,
            "total_submitted": len(payload.items),
            "live_count": stats.get("live", len(items_to_add)),
            "die_count": stats.get("die", 0),
            "dead_removed_count": len(dead_lines) if should_delete_die else 0,
            "uploaded_count": len(items_to_add),
            "category_id": category.id,
            "category_name": category.name,
            "subcategory_id": subcategory.id,
            "subcategory_name": subcategory.name,
            "price_per_item": payload.price
        }


class CheckUidRequest(BaseModel):
    data: str


@api_router.post("/facebook/check-uid")
async def check_uid_endpoint(payload: CheckUidRequest, request: Request, x_api_key: str = Header(None)):
    if not is_request_authorized(request, x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai mã X-API-KEY hoặc chưa đăng nhập Admin!")

    from services.facebook import extract_uid, check_uid_live_async
    import aiohttp

    lines = [l.strip() for l in payload.data.splitlines() if l.strip()]
    if not lines:
        return {"status": "success", "results": [], "total": 0, "live": 0, "die": 0}

    results = []
    async with aiohttp.ClientSession() as session:
        for line in lines[:50]:  # Giới hạn 50 UID mỗi lần test tức thì
            uid = extract_uid(line)
            if uid:
                res_status = await check_uid_live_async(uid, session)
                results.append({"raw": line, "uid": uid, "status": res_status})
            else:
                results.append({"raw": line, "uid": None, "status": "UNKNOWN"})

    live_cnt = sum(1 for r in results if r["status"] == "LIVE")
    die_cnt = sum(1 for r in results if r["status"] == "DIE")

    return {
        "status": "success",
        "results": results,
        "total": len(results),
        "live": live_cnt,
        "die": die_cnt
    }


@api_router.get("/facebook/scan-stock")
async def scan_stock_endpoint(request: Request, x_api_key: str = Header(None)):
    if not is_request_authorized(request, x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai mã X-API-KEY hoặc chưa đăng nhập Admin!")

    from services.facebook import scan_facebook_inventory
    async with get_db_session() as session:
        result = await scan_facebook_inventory(session, auto_delete_die=False)
        return {"status": "success", **result}


@api_router.post("/facebook/clean-die")
async def clean_die_endpoint(request: Request, x_api_key: str = Header(None)):
    if not is_request_authorized(request, x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai mã X-API-KEY hoặc chưa đăng nhập Admin!")

    from services.facebook import scan_facebook_inventory
    async with get_db_session() as session:
        result = await scan_facebook_inventory(session, auto_delete_die=True)
        return {
            "status": "success",
            "message": f"Đã quét và xóa thành công {result['deleted_count']} tài khoản DIE khỏi kho hàng!",
            **result
        }


@api_router.get("/inventory/status")
async def inventory_status(request: Request, x_api_key: str = Header(None)):
    if not is_request_authorized(request, x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai mã X-API-KEY!")

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
async def binance_pay_status(request: Request, x_api_key: str = Header(None)):
    if not is_request_authorized(request, x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai mã X-API-KEY!")

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
async def binance_pay_check_now(request: Request, x_api_key: str = Header(None)):
    if not is_request_authorized(request, x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai mã X-API-KEY!")

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
    if not is_request_authorized(request, x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập Admin hoặc sai API Key!")

    from services.settings import SettingsService
    async with get_db_session() as session:
        result = await SettingsService.save_settings(payload.settings, session)
        return {
            "status": "success",
            "message": "Đã lưu cài đặt thành công vào Database Supabase! Cấu hình có hiệu lực ngay lập tức.",
            "saved_keys": result.get("saved_keys", [])
        }


@api_router.get("/settings/current")
async def get_settings_endpoint(request: Request, x_api_key: str = Header(None)):
    if not is_request_authorized(request, x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập Admin hoặc sai API Key!")

    from services.settings import SettingsService
    async with get_db_session() as session:
        return await SettingsService.get_all_settings(session)


@api_router.get("/categories/list")
async def list_categories_and_subcategories(request: Request, x_api_key: str = Header(None)):
    if not is_request_authorized(request, x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập Admin!")

    async with get_db_session() as session:
        cats = (await session.execute(select(Category).order_by(Category.name))).scalars().all()
        subcats = (await session.execute(select(Subcategory).order_by(Subcategory.name))).scalars().all()
        return {
            "status": "success",
            "categories": [{"id": c.id, "name": c.name} for c in cats],
            "subcategories": [{"id": s.id, "name": s.name} for s in subcats]
        }
