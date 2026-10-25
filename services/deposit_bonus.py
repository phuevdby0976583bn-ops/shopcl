import logging
from typing import List, Tuple
from enums.language import Language
import config

logger = logging.getLogger(__name__)


class DepositBonusService:
    @staticmethod
    def is_enabled() -> bool:
        val = getattr(config, "DEPOSIT_BONUS_ENABLED", False)
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "1", "yes")

    @staticmethod
    def parse_tiers() -> List[Tuple[float, float]]:
        """
        Phân tích chuỗi cài đặt mốc thưởng nạp.
        Hỗ trợ định dạng: '100:2, 200:5, 300:6' hoặc xuống dòng '100:2\n200:5'
        Trả về danh sách [(100.0, 2.0), (200.0, 5.0), ...] được sắp xếp tăng dần.
        """
        raw = str(getattr(config, "DEPOSIT_BONUS_TIERS", "") or "").strip()
        if not raw:
            return []

        tiers = []
        cleaned = raw.replace("\n", ",").replace(";", ",")
        for part in cleaned.split(","):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                sub = part.split(":", 1)
            elif "-" in part:
                sub = part.split("-", 1)
            else:
                continue
            try:
                min_amt = float(sub[0].replace("$", "").replace("USDT", "").replace("usdt", "").strip())
                pct = float(sub[1].replace("%", "").strip())
                if min_amt > 0 and pct > 0:
                    tiers.append((min_amt, pct))
            except Exception:
                continue

        tiers.sort(key=lambda x: x[0])
        return tiers

    @staticmethod
    def get_bonus_rate(amount: float) -> float:
        """
        Trả về % thưởng (ví dụ 5.0 nghĩa là +5%) tương ứng với số tiền nạp.
        Trả về 0.0 nếu khuyến mãi đang TẮT hoặc không đạt mốc tối thiểu.
        """
        if not DepositBonusService.is_enabled() or amount <= 0:
            return 0.0

        tiers = DepositBonusService.parse_tiers()
        bonus_pct = 0.0
        for min_amt, pct in tiers:
            if amount >= min_amt:
                bonus_pct = pct
        return bonus_pct

    @staticmethod
    def calculate_bonus(amount: float) -> Tuple[float, float]:
        """
        Trả về (bonus_amount, bonus_pct).
        Ví dụ: Nạp 100 USDT được thưởng 2% -> Trả về (2.0, 2.0).
        """
        pct = DepositBonusService.get_bonus_rate(amount)
        if pct <= 0:
            return 0.0, 0.0
        bonus_amt = round(amount * (pct / 100.0), 2)
        return bonus_amt, pct

    @staticmethod
    def get_bonus_display_text(language: Language = Language.VI) -> str:
        """
        Trả về chuỗi hiển thị bảng thưởng nạp cho khách xem.
        Nếu khuyến mãi đang TẮT, trả về chuỗi rỗng "" (không hiển thị gì).
        """
        if not DepositBonusService.is_enabled():
            return ""

        tiers = DepositBonusService.parse_tiers()
        if not tiers:
            return ""

        headers = {
            Language.VI: ("🎁 <b>Thưởng nạp qua bot:</b>", "• {amt} USDT trở lên: +{pct:g}%", "• {amt} USDT: +{pct:g}%"),
            Language.EN: ("🎁 <b>Deposit bonus:</b>", "• {amt}+ USDT: +{pct:g}%", "• {amt} USDT: +{pct:g}%"),
            Language.HI: ("🎁 <b>जमा बोनस:</b>", "• {amt}+ USDT या अधिक: +{pct:g}%", "• {amt} USDT: +{pct:g}%"),
            Language.ZH: ("🎁 <b>充值额外奖励：</b>", "• {amt} USDT 以上: +{pct:g}%", "• {amt} USDT: +{pct:g}%"),
            Language.FR: ("🎁 <b>Bonus de dépôt :</b>", "• {amt}+ USDT ou plus : +{pct:g}%", "• {amt} USDT : +{pct:g}%"),
            Language.DE: ("🎁 <b>Einzahlungsbonus:</b>", "• {amt}+ USDT oder mehr: +{pct:g}%", "• {amt} USDT: +{pct:g}%"),
            Language.IT: ("🎁 <b>Bonus di deposito:</b>", "• {amt}+ USDT o più: +{pct:g}%", "• {amt} USDT: +{pct:g}%"),
            Language.ES: ("🎁 <b>Bono por depósito:</b>", "• {amt}+ USDT o más: +{pct:g}%", "• {amt} USDT: +{pct:g}%")
        }
        hdr, last_pat, pat = headers.get(language, headers[Language.EN])
        lines = [hdr]
        for idx, (min_amt, pct) in enumerate(tiers):
            amt_str = f"{min_amt:,.0f}" if language != Language.VI else f"{min_amt:,.0f}".replace(",", ".")
            if idx == len(tiers) - 1:
                lines.append(last_pat.format(amt=amt_str, pct=pct))
            else:
                lines.append(pat.format(amt=amt_str, pct=pct))
        return "\n".join(lines)
