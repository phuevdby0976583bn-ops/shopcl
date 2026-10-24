import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any, List, Optional, Tuple
import aiohttp
import requests
import config

if TYPE_CHECKING:
    from models.item import ItemDTO
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def check_uid_live(uid: str) -> str:
    """
    Kiểm tra trạng thái LIVE/DIE của UID Facebook (đồng bộ bằng requests).
    """
    url = f"https://graph.facebook.com/{uid}/picture?type=normal&redirect=false"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        res = requests.get(url, headers=headers, timeout=5)
        data = res.json()

        # Nếu tài khoản chết hoặc không tồn tại, Graph API trả về error
        if "error" in data:
            return "DIE"

        image_url = data.get("data", {}).get("url", "")
        if "static.xx.fbcdn.net" in image_url or "rsrc.php" in image_url or "gif" in image_url:
            return "DIE"

        return "LIVE"
    except Exception as e:
        return f"ERROR: {str(e)}"


async def check_uid_live_async(uid: str, session: Optional[aiohttp.ClientSession] = None) -> str:
    """
    Kiểm tra trạng thái LIVE/DIE của UID Facebook bất đồng bộ (async).
    Dành cho Aiogram và FastAPI để xử lý hàng loạt tài khoản cực nhanh mà không block bot.
    """
    url = f"https://graph.facebook.com/{uid}/picture?type=normal&redirect=false"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Encoding": "gzip, deflate"
    }

    should_close = False
    if session is None:
        session = aiohttp.ClientSession()
        should_close = True

    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with session.get(url, headers=headers, timeout=timeout) as response:
            data = await response.json(content_type=None)

            if "error" in data:
                return "DIE"

            image_url = data.get("data", {}).get("url", "")
            if "static.xx.fbcdn.net" in image_url or "rsrc.php" in image_url or "gif" in image_url:
                return "DIE"

            return "LIVE"
    except Exception as e:
        return f"ERROR: {str(e)}"
    finally:
        if should_close:
            await session.close()


def extract_uid(text: Optional[str]) -> Optional[str]:
    """
    Trích xuất UID Facebook từ chuỗi định dạng clone phổ biến:
    - UID|PASS|2FA|MAIL|PASSMAIL...
    - UID:PASS...
    - Cookie chứa c_user=UID...
    - Link facebook.com/UID...
    - Chuỗi số UID thuần túy
    - Email|Pass|UID|2FA...
    """
    if not text:
        return None

    text = text.strip()

    # 1. Cookie chứa c_user=1000xxxx
    c_user_match = re.search(r'c_user=(\d+)', text)
    if c_user_match:
        return c_user_match.group(1)

    # 2. Link profile facebook.com/1000xxxx hoặc facebook.com/profile.php?id=1000xxxx
    url_match = re.search(r'facebook\.com/(?:profile\.php\?id=)?(\d+)', text)
    if url_match:
        return url_match.group(1)

    # 3. Phân tách theo ký tự phân cách thông dụng
    parts = re.split(r'[:|;\t\s]', text)
    parts = [p.strip() for p in parts if p.strip()]
    if parts:
        first = parts[0]
        if first.isdigit():
            return first

    # 4. Quét các phần tử tiếp theo nếu phần đầu là email/username
    for p in parts[1:]:
        if p.isdigit() and len(p) >= 4:
            return p

    return None


def is_facebook_clone(private_data: Optional[str]) -> bool:
    """Kiểm tra xem dữ liệu mặt hàng có phải là clone Facebook có UID hay không."""
    return extract_uid(private_data) is not None


def is_facebook_product(category_name: Optional[str] = None, subcategory_name: Optional[str] = None, private_data: Optional[str] = None) -> bool:
    """
    Kiểm tra xem một mặt hàng / danh mục có phải là Facebook Clone hay không:
    - Kiểm tra từ khóa trong category/subcategory name (facebook, fb, via, clone, bm, meta, nick fb...)
    - Hoặc kiểm tra xem private_data có chứa UID Facebook hợp lệ hay không.
    """
    raw_keywords = getattr(config, 'FB_CATEGORY_KEYWORDS', 'facebook, fb, clone, via, bm') or 'facebook, fb, clone, via, bm'
    keywords = [kw.strip().lower() for kw in raw_keywords.split(',') if kw.strip()]
    if not keywords:
        keywords = ['facebook', 'fb', 'via', 'clone', 'bm']

    if category_name:
        c_lower = category_name.lower()
        if any(kw in c_lower for kw in keywords):
            return True

    if subcategory_name:
        s_lower = subcategory_name.lower()
        if any(kw in s_lower for kw in keywords):
            return True

    if private_data and is_facebook_clone(private_data):
        return True

    return False


async def filter_live_facebook_items(
    candidate_items: List[Any],
    required_qty: int,
    concurrency_limit: int = 10
) -> Tuple[List[Any], List[Any]]:
    """
    Kiểm tra danh sách tài khoản candidate:
    - Trả về (live_items, dead_items)
    - Dừng ngay khi đã gom đủ required_qty tài khoản LIVE
    - Sử dụng semaphore giới hạn concurrency để không bị Facebook rate limit
    """
    live_items: List[Any] = []
    dead_items: List[Any] = []

    semaphore = asyncio.Semaphore(concurrency_limit)

    async def _check_item(item: Any, session: aiohttp.ClientSession) -> Tuple[Any, str]:
        uid = extract_uid(item.private_data)
        if not uid:
            # Không trích xuất được UID -> coi như item thường, xem là LIVE
            return item, "LIVE"
        async with semaphore:
            status = await check_uid_live_async(uid, session)
            return item, status

    async with aiohttp.ClientSession() as session:
        batch_size = max(required_qty * 2, 10)
        for i in range(0, len(candidate_items), batch_size):
            if len(live_items) >= required_qty:
                break

            batch = candidate_items[i:i + batch_size]
            tasks = [_check_item(item, session) for item in batch]
            results = await asyncio.gather(*tasks)

            for item, status in results:
                if status == "LIVE":
                    if len(live_items) < required_qty:
                        live_items.append(item)
                elif status == "DIE":
                    dead_items.append(item)
                else:
                    # Gặp lỗi mạng hoặc timeout -> tạm coi là không an toàn để giao cho khách
                    logger.warning(f"Check live UID {extract_uid(item.private_data)} error: {status}")
                    dead_items.append(item)

    return live_items, dead_items


async def get_existing_uids_from_db(session: Any = None) -> set[str]:
    """
    Lấy danh sách tất cả các UID Facebook đã có trong bảng items (kho hàng)
    để phục vụ việc kiểm tra và chặn trùng lặp khi nạp hàng.
    """
    from db import get_db_session
    from models.item import Item
    from sqlalchemy import select

    async def _fetch(sess):
        stmt = select(Item.private_data).where(Item.private_data.is_not(None))
        res = await sess.execute(stmt)
        uids = set()
        for row in res.scalars().all():
            if not row:
                continue
            u = extract_uid(row)
            if u:
                uids.add(str(u))
        return uids

    if session is not None:
        return await _fetch(session)
    else:
        async with get_db_session() as sess:
            return await _fetch(sess)


async def deduplicate_facebook_raw_lines(
    lines: List[str],
    existing_uids: Optional[set[str]] = None,
    session: Any = None,
    check_db: bool = True
) -> Tuple[List[str], List[str], dict]:
    """
    Lọc bỏ các dòng tài khoản Facebook bị trùng UID:
    1. Trùng lặp giữa các dòng trong chính danh sách gửi lên (internal duplicate).
    2. Trùng lặp với các UID Facebook ĐÃ CÓ trong kho hàng (database duplicate).

    Trả về:
    - unique_lines: danh sách các dòng hợp lệ duy nhất.
    - duplicate_lines: danh sách các dòng bị loại bỏ do trùng lặp UID.
    - stats: thống kê chi tiết {total, unique, duplicates, internal_duplicates, db_duplicates}
    """
    cleaned_input = [line.strip() for line in lines if line and line.strip()]
    if not cleaned_input:
        return [], [], {
            "total": 0, "unique": 0, "duplicates": 0,
            "internal_duplicates": 0, "db_duplicates": 0
        }

    known_uids = set(existing_uids) if existing_uids is not None else set()
    if check_db and existing_uids is None:
        try:
            known_uids = await get_existing_uids_from_db(session=session)
        except Exception as e:
            logger.warning(f"Could not fetch existing UIDs from DB for deduplication: {e}")
            known_uids = set()

    seen_batch_uids = set()
    seen_batch_lines = set()
    unique_lines = []
    duplicate_lines = []
    internal_dup = 0
    db_dup = 0

    for line in cleaned_input:
        uid = extract_uid(line)
        if uid:
            uid_str = str(uid)
            if uid_str in seen_batch_uids:
                internal_dup += 1
                duplicate_lines.append(line)
                continue
            if uid_str in known_uids:
                db_dup += 1
                duplicate_lines.append(line)
                continue
            seen_batch_uids.add(uid_str)
            known_uids.add(uid_str)
            unique_lines.append(line)
        else:
            # Mặt hàng không trích xuất được UID -> lọc trùng theo nguyên chuỗi
            if line in seen_batch_lines:
                internal_dup += 1
                duplicate_lines.append(line)
                continue
            seen_batch_lines.add(line)
            unique_lines.append(line)

    stats = {
        "total": len(cleaned_input),
        "unique": len(unique_lines),
        "duplicates": len(duplicate_lines),
        "internal_duplicates": internal_dup,
        "db_duplicates": db_dup
    }
    return unique_lines, duplicate_lines, stats


async def scan_and_filter_facebook_raw_lines(
    lines: List[str],
    check_live: bool = True,
    delete_die: bool = True,
    concurrency_limit: int = 15,
    filter_duplicates: bool = True,
    session: Any = None
) -> Tuple[List[str], List[str], dict]:
    """
    Quét danh sách các dòng clone Facebook:
    - Tự động lọc trùng UID (cả trùng lặp trong file và trùng với kho hàng DB).
    - Tự động check LIVE qua Graph API và loại bỏ nick DIE.
    """
    cleaned_input = [line.strip() for line in lines if line and line.strip()]
    if not cleaned_input:
        return [], [], {"total": 0, "unique": 0, "duplicates": 0, "live": 0, "die": 0, "deleted": 0}

    # BƯỚC 1: LỌC TRÙNG UID (Không check LIVE những dòng trùng lặp để tiết kiệm request)
    duplicate_lines = []
    dup_stats = {"duplicates": 0, "internal_duplicates": 0, "db_duplicates": 0}
    if filter_duplicates:
        unique_lines, duplicate_lines, dup_stats = await deduplicate_facebook_raw_lines(
            cleaned_input, session=session, check_db=True
        )
    else:
        unique_lines = cleaned_input

    if not unique_lines:
        return [], duplicate_lines, {
            "total": len(cleaned_input),
            "unique": 0,
            "duplicates": len(duplicate_lines),
            "live": 0,
            "die": 0,
            "deleted": 0,
            **dup_stats
        }

    # BƯỚC 2: CHECK LIVE CÁC DÒNG HỢP LỆ VÀ KHÔNG TRÙNG
    if not check_live:
        return unique_lines, duplicate_lines, {
            "total": len(cleaned_input),
            "unique": len(unique_lines),
            "duplicates": len(duplicate_lines),
            "live": len(unique_lines),
            "die": 0,
            "deleted": 0,
            **dup_stats
        }

    live_lines = []
    dead_lines = []
    semaphore = asyncio.Semaphore(concurrency_limit)

    async def _check_line(line: str, http_session: aiohttp.ClientSession):
        uid = extract_uid(line)
        if not uid:
            return line, "LIVE", None
        async with semaphore:
            status = await check_uid_live_async(uid, http_session)
            return line, status, uid

    async with aiohttp.ClientSession() as http_session:
        tasks = [_check_line(line, http_session) for line in unique_lines]
        results = await asyncio.gather(*tasks)

    for line, status, uid in results:
        if status == "LIVE":
            live_lines.append(line)
        elif status == "DIE":
            dead_lines.append(line)
        else:
            logger.warning(f"Check live UID {uid} got error '{status}', keeping line safely.")
            live_lines.append(line)

    kept_lines = live_lines if delete_die else unique_lines
    stats = {
        "total": len(cleaned_input),
        "unique": len(unique_lines),
        "duplicates": len(duplicate_lines),
        "live": len(live_lines),
        "die": len(dead_lines),
        "deleted": len(dead_lines) if delete_die else 0,
        **dup_stats
    }
    return kept_lines, dead_lines, stats


async def scan_facebook_inventory(
    session: Any,
    auto_delete_die: bool = False,
    concurrency_limit: int = 15
) -> dict:
    """
    Quét toàn bộ tài khoản clone Facebook chưa bán trong kho.
    - Đếm số lượng LIVE và DIE
    - Nếu auto_delete_die=True, xóa vĩnh viễn các tài khoản DIE khỏi DB
    """
    from repositories.item import ItemRepository
    from repositories.subcategory import SubcategoryRepository

    unsold_items = await ItemRepository.get_all_unsold_clones(session)
    fb_items = [item for item in unsold_items if is_facebook_clone(item.private_data)]

    if not fb_items:
        return {
            "total_scanned": 0,
            "live_count": 0,
            "die_count": 0,
            "die_items": [],
            "deleted_count": 0
        }

    semaphore = asyncio.Semaphore(concurrency_limit)
    live_items = []
    dead_items = []

    async def _check(item: Any, http_session: aiohttp.ClientSession):
        uid = extract_uid(item.private_data)
        async with semaphore:
            status = await check_uid_live_async(uid, http_session)
            return item, status, uid

    async with aiohttp.ClientSession() as http_session:
        tasks = [_check(item, http_session) for item in fb_items]
        results = await asyncio.gather(*tasks)

    for item, status, uid in results:
        if status == "LIVE":
            live_items.append(item)
        elif status == "DIE":
            dead_items.append({"id": item.id, "uid": uid, "private_data": item.private_data, "subcategory_id": item.subcategory_id})
        else:
            live_items.append(item)

    deleted_count = 0
    if dead_items and auto_delete_die:
        dead_ids = [d["id"] for d in dead_items]
        await ItemRepository.delete_items_by_ids(dead_ids, session)
        await session.commit()
        deleted_count = len(dead_ids)

    # Lấy tên subcategory cho các item die để hiển thị đẹp
    if dead_items:
        sub_ids = list({d["subcategory_id"] for d in dead_items})
        subcats = await SubcategoryRepository.get_by_ids(sub_ids, session)
        sub_map = {s.id: s.name for s in subcats}
        for d in dead_items:
            d["subcategory_name"] = sub_map.get(d["subcategory_id"], "Facebook")

    return {
        "total_scanned": len(fb_items),
        "live_count": len(live_items),
        "die_count": len(dead_items),
        "die_items": dead_items,
        "deleted_count": deleted_count
    }


async def clean_duplicate_inventory_uids(session: Any) -> dict:
    """
    Quét toàn bộ tài khoản chưa bán trong kho.
    Nếu phát hiện các bản ghi có cùng UID Facebook:
    - Giữ lại 1 bản ghi duy nhất (ID nhỏ nhất).
    - Xóa các bản ghi trùng lặp còn lại khỏi DB.
    """
    from repositories.item import ItemRepository
    from models.item import Item
    from sqlalchemy import delete

    unsold_items = await ItemRepository.get_all_unsold_clones(session)
    seen_uids: dict[str, int] = {}  # uid -> first item id
    duplicate_item_ids: list[int] = []

    for item in unsold_items:
        uid = extract_uid(item.private_data)
        if not uid:
            continue
        uid_str = str(uid)
        if uid_str in seen_uids:
            duplicate_item_ids.append(item.id)
        else:
            seen_uids[uid_str] = item.id

    if duplicate_item_ids:
        await session.execute(
            delete(Item).where(Item.id.in_(duplicate_item_ids))
        )
        await session.commit()
        logger.info(f"Cleaned {len(duplicate_item_ids)} duplicate Facebook clones from inventory.")

    return {
        "total_scanned": len(unsold_items),
        "unique_uids": len(seen_uids),
        "deleted_duplicates": len(duplicate_item_ids),
        "duplicate_ids": duplicate_item_ids
    }
