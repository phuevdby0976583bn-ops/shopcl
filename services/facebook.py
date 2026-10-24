import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any, List, Optional, Tuple
import aiohttp
import requests

if TYPE_CHECKING:
    from models.item import ItemDTO

logger = logging.getLogger(__name__)


def check_uid_live(uid: str) -> str:
    """
    Kiểm tra trạng thái LIVE/DIE của UID Facebook (đồng bộ bằng requests).
    Hàm chuẩn theo yêu cầu của bạn, được tối ưu thêm để bắt link avatar rỗng dạng .jpg và rsrc.php.
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

        # Kiểm tra URL avatar nếu trả về ảnh rỗng mặc định
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
    """
    if not text:
        return None

    text = text.strip()

    # Định dạng phổ biến nhất: UID|... hoặc UID:... hoặc UID;...
    first_part = re.split(r'[:|;,\s]', text)[0].strip()
    if first_part.isdigit():
        return first_part

    # Định dạng Cookie có c_user=1000xxxx
    c_user_match = re.search(r'c_user=(\d+)', text)
    if c_user_match:
        return c_user_match.group(1)

    # Link profile facebook.com/1000xxxx hoặc facebook.com/profile.php?id=1000xxxx
    url_match = re.search(r'facebook\.com/(?:profile\.php\?id=)?(\d+)', text)
    if url_match:
        return url_match.group(1)

    return None


def is_facebook_clone(private_data: Optional[str]) -> bool:
    """Kiểm tra xem dữ liệu mặt hàng có phải là clone Facebook có UID hay không."""
    return extract_uid(private_data) is not None


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
        # Chia thành từng batch nhỏ để không kiểm tra thừa nếu đã đủ số lượng
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
                    # Gặp lỗi mạng hoặc timeout -> tạm coi là không an toàn, bỏ qua không cấp cho khách
                    logger.warning(f"Check live UID {extract_uid(item.private_data)} error: {status}")
                    dead_items.append(item)

    return live_items, dead_items
