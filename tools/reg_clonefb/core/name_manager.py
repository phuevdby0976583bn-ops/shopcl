# -*- coding: utf-8 -*-

"""

core.name_manager

Hệ thống quản lý và sinh tên ngẫu nhiên đa quốc gia (Name Generator & Manager).

Hỗ trợ:

1. Tên Việt Nam (vi_VN)

2. Tên Tây / US-UK (en_US)

3. Tên Ấn Độ (hi_IN)

4. Tên Thái Lan (th_TH)

5. Tên Trung Quốc (zh_CN)

6. Tên Hàn Quốc (ko_KR)

7. Tên Nhật Bản (ja_JP)

8. Tên Indonesia (id_ID)

9. Tên Philippines (fil_PH)

10. Tên Brazil / Latin (pt_BR)

11. Tên Nga / Đông Âu (ru_RU)

12. Tên Ả Rập / Trung Đông (ar_SA)

13. Tên Toàn Cầu Hỗn Hợp (Mix ngẫu nhiên tất cả các quốc gia)

14. Tên từ File tùy chỉnh (names.txt), hỗ trợ ghép ngẫu nhiên Họ + Tên.

"""



import os

import re

import random

import threading

from typing import Dict, Any, List, Optional, Tuple

from dataclasses import dataclass



# Re-export all pools from core.name_pools for full backward compatibility

from core.name_pools import (

    HO_VIET, DEM_NAM_VIET, TEN_NAM_VIET, DEM_NU_VIET, TEN_NU_VIET,

    FIRST_NAMES_MALE_WESTERN, FIRST_NAMES_FEMALE_WESTERN, LAST_NAMES_WESTERN,

    FIRST_NAMES_MALE_INDIAN, FIRST_NAMES_FEMALE_INDIAN, LAST_NAMES_INDIAN,

    FIRST_NAMES_MALE_THAI, FIRST_NAMES_FEMALE_THAI, LAST_NAMES_THAI,

    FIRST_NAMES_MALE_CHINESE, FIRST_NAMES_FEMALE_CHINESE, LAST_NAMES_CHINESE,

    FIRST_NAMES_MALE_KOREAN, FIRST_NAMES_FEMALE_KOREAN, LAST_NAMES_KOREAN,

    FIRST_NAMES_MALE_JAPANESE, FIRST_NAMES_FEMALE_JAPANESE, LAST_NAMES_JAPANESE,

    FIRST_NAMES_MALE_INDONESIAN, FIRST_NAMES_FEMALE_INDONESIAN, LAST_NAMES_INDONESIAN,

    FIRST_NAMES_MALE_FILIPINO, FIRST_NAMES_FEMALE_FILIPINO, LAST_NAMES_FILIPINO,

    FIRST_NAMES_MALE_BRAZILIAN, FIRST_NAMES_FEMALE_BRAZILIAN, LAST_NAMES_BRAZILIAN,

    FIRST_NAMES_MALE_RUSSIAN, FIRST_NAMES_FEMALE_RUSSIAN, LAST_NAMES_RUSSIAN,

    FIRST_NAMES_MALE_ARABIC, FIRST_NAMES_FEMALE_ARABIC, LAST_NAMES_ARABIC,

)





@dataclass

class GeneratedName:

    full_name: str

    first_name: str

    last_name: str

    gender_val: int  # 2 = Nam, 1 = Nữ

    gender_str: str  # "Nam (2)" / "Nữ (1)"

    category: str    # "vietnamese", "western", "indian", "thai", "chinese", "korean", "japanese", "indonesian", "filipino", "brazilian", "russian", "arabic", "global", "file"

    display_tag: str





class NameManager:

    """Quản lý sinh tên thông minh hỗ trợ 12 quốc gia, mix toàn cầu và file tùy chỉnh."""



    FLAGGED_SURNAMES = {
        'chúc', 'sầm', 'sử', 'bố', 'bì', 'ca', 'cáp', 'ung', 'ngạc', 'phù',
        'sái', 'sư', 'cố', 'trác', 'cổ', 'chử', 'giản', 'hầu', 'phí', 'uông',
        'vi', 'vạn', 'bửu', 'bàng', 'liêu', 'cù', 'doãn', 'cấn', 'khuất',
        'mạc', 'bành', 'biện', 'giáp', 'đôn', 'thi', 'cung', 'ôn', 'quản',
        'đậu', 'nhữ', 'bạc', 'bào', 'bạt', 'cai', 'hách', 'khiếu', 'vưu',
        'hình', 'tất', 'biển', 'ấu', 'chiêm', 'đổng', 'xađồng', 'bhan',
        'nông', 'mã', 'tiêu', 'tào', 'lục', 'thân', 'tiết', 'bạch', 'thạch', 'giang',
        'đường', 'hồng', 'hùng', 'văn', 'ân', 'la', 'trang', 'kim', 'thịnh', 'đàm', 'hàn', 'tân'
    }

    SAFE_SURNAMES = [
        'Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Huỳnh', 'Phan', 'Vũ', 'Võ',
        'Đặng', 'Bùi', 'Đỗ', 'Hồ', 'Ngô', 'Dương', 'Lý', 'Đinh', 'Đoàn',
        'Lâm', 'Mai', 'Trịnh', 'Đào', 'Cao', 'Hà', 'Lưu', 'Lương', 'Thái',
        'Châu', 'Tạ', 'Phùng', 'Tô', 'Vương', 'Tăng', 'Quách', 'Nhan', 'Kiều',
        'Triệu', 'Hứa', 'Nghiêm', 'Chu', 'Tống', 'Diệp', 'Lại', 'Từ', 'Trương', 'Tôn'
    ]

    SAFE_FIRST_NAMES_MALE = [
        'Văn Nam', 'Minh Tuấn', 'Quốc Bảo', 'Hoàng Long', 'Thành Đạt', 'Minh Huy',
        'Đức Anh', 'Hải Đăng', 'Quang Vinh', 'Hữu Phước', 'Tuấn Kiệt', 'Thanh Tùng',
        'Gia Huy', 'Đình Trọng', 'Văn Hậu', 'Tiến Dũng', 'Quang Hải', 'Hùng Dũng',
        'Văn Toàn', 'Văn Minh', 'Đức Thịnh', 'Gia Bảo', 'Minh Khôi', 'Hải Nam',
        'Đăng Khoa', 'Trung Kiên', 'Việt Anh', 'Thành Trung', 'Quang Minh', 'Thanh Hải',
        'Văn Hưng', 'Đức Huy', 'Văn Đức', 'Hữu Long', 'Tuấn Tú', 'Minh Triết',
        'Anh Tuấn', 'Huy Nam', 'Quốc Huy', 'Quang Thắng', 'Minh Quân', 'Minh Trí',
        'Khánh Duy', 'Anh Dũng', 'Hoàng Nam', 'Tuấn Đạt', 'Bảo Nam', 'Bảo Long',
        'Huy Hoàng', 'Duy Mạnh', 'Xuân Trường', 'Công Phượng', 'Thanh Bình'
    ]

    DISALLOWED_NAME_TOKENS = {
        'quý', 'quy', 'bá', 'ba', 'chánh', 'chanh', 'sĩ', 'si', 'đại', 'dai',
        'thông', 'thong', 'đôn', 'don', 'đắc', 'dac', 'vượng', 'vuong', 'thiệu', 'thieu',
        'bằng', 'bang', 'chiến', 'chien', 'đạo', 'dao', 'thế', 'the', 'quan', 'tướng', 'tuong',
        'vương', 'chúa', 'chua', 'vua', 'thần', 'than', 'thánh', 'tiên', 'tien',
        'phật', 'phat', 'ông', 'ong', 'bà', 'chú', 'chu', 'bác', 'bac', 'ngài', 'ngai',
        'huynh', 'đệ', 'de', 'muội', 'muoi', 'tỷ', 'ty',
        'trúc', 'truc', 'nghi', 'dạ', 'da', 'cúc', 'cuc', 'nhựt', 'nhut', 'trực', 'truc',
        'hậu', 'hau', 'giáp', 'giap', 'tố', 'to', 'bắc', 'bac', 'lục', 'luc', 'tiêu', 'tieu',
        'tào', 'tao', 'mã', 'ma', 'nông', 'nong', 'ung', 'cù', 'cu', 'kỷ', 'ky', 'mẫn', 'man',
        'nghị', 'nghi', 'du', 'doanh', 'thạc', 'thac', 'khuyên', 'khuyen', 'sương', 'suong',
        'hảo', 'hao', 'huyên', 'mộc', 'moc', 'mây', 'may', 'nắng', 'nang', 'lụa', 'lua',
        'mến', 'men', 'miên', 'mien', 'nụ', 'nu', 'phấn', 'phan', 'sa', 'sam', 'sim', 'sâm',
        'tần', 'tan', 'xoan', 'cam', 'châm', 'cham'
    }

    SAFE_FIRST_NAMES_FEMALE = [
        'Thu Hà', 'Thị Mai', 'Phương Linh', 'Thảo Vy', 'Ngọc Ánh', 'Hồng Nhung',
        'Kim Ngân', 'Thanh Thảo', 'Khánh Linh', 'Bảo Ngọc', 'Quỳnh Anh', 'Minh Châu',
        'Mỹ Linh', 'Hải Yến', 'Như Quỳnh', 'Thùy Trang', 'Hương Giang', 'Bích Ngọc',
        'Thị Hương', 'Thu Trang', 'Ngọc Linh', 'Thị Lan', 'Thị Hoa', 'Thị Tuyết',
        'Thị Hằng', 'Thị Dung', 'Thanh Hằng', 'Thị Oanh', 'Thị Thúy', 'Thị Phương',
        'Hồng Hạnh', 'Thị Nga', 'Thị Loan', 'Mai Phương', 'Thị Thơ', 'Thị Huệ',
        'Thị Huyền', 'Thùy Linh', 'Phương Thảo', 'Thu Thủy', 'Ngọc Huyền', 'Diệu Linh',
        'Huyền Trang', 'Thanh Vân', 'Hoàng Yến', 'Tuyết Mai', 'Cẩm Tú', 'Thúy Hằng',
        'Thúy Vi', 'Quỳnh Nga', 'Hồng Vân', 'Thanh Hương', 'Phương Nga', 'Bích Thủy'
    ]

    @classmethod
    def sanitize_facebook_name(cls, first_name: str, last_name: str) -> Tuple[str, str, str]:
        """Chuẩn hóa Họ & Tên đảm bảo 100% tuân thủ Chính sách Tên của Facebook Meta."""
        def split_camel_case(s: str) -> str:
            res = []
            for i, c in enumerate(s):
                if i > 0 and c.isupper() and s[i-1].islower() and not s.startswith(('Mc', 'Mac')):
                    res.append(' ')
                res.append(c)
            return ''.join(res)

        def clean_text(s: str) -> str:
            s = split_camel_case(str(s or ''))
            s = ''.join(c if (c.isalpha() or c.isspace()) else ' ' for c in s)
            return ' '.join(s.split())

        fn_clean = clean_text(first_name)
        ln_clean = clean_text(last_name)

        ln_tokens = [t.capitalize() for t in ln_clean.split() if t]
        fn_tokens = [t.capitalize() for t in fn_clean.split() if t]

        # Lọc sạch từ ngữ chức danh, tiêu đề, tước hiệu theo chính sách Meta
        safe_surnames_filtered = [s for s in cls.SAFE_SURNAMES if s.lower() not in getattr(cls, 'DISALLOWED_NAME_TOKENS', set())]
        if not safe_surnames_filtered:
            safe_surnames_filtered = ['Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Huỳnh', 'Phan', 'Vũ', 'Đặng', 'Bùi']

        if not ln_tokens:
            final_last = random.choice(safe_surnames_filtered)
        else:
            cand_last = ln_tokens[0]
            if cand_last.lower() in getattr(cls, 'DISALLOWED_NAME_TOKENS', set()) or cand_last.lower() in cls.FLAGGED_SURNAMES or len(cand_last) < 2:
                final_last = random.choice(safe_surnames_filtered)
            else:
                final_last = cand_last

        # Lọc sạch từng token trong first_name
        safe_given_replacements = ['Nam', 'Huy', 'Phong', 'Dũng', 'Tuấn', 'Đạt', 'Long', 'Khoa', 'Minh', 'Tùng', 'Bảo', 'Khánh', 'Việt', 'Anh']
        clean_fn_tokens = []
        for t in fn_tokens:
            if t.lower() in getattr(cls, 'DISALLOWED_NAME_TOKENS', set()):
                clean_fn_tokens.append(random.choice(safe_given_replacements))
            else:
                clean_fn_tokens.append(t)
        fn_tokens = clean_fn_tokens

        if not fn_tokens:
            final_first = random.choice(cls.SAFE_FIRST_NAMES_MALE)
        elif len(fn_tokens) == 1:
            final_first = fn_tokens[0]
        elif len(fn_tokens) == 2:
            final_first = f'{fn_tokens[0]} {fn_tokens[1]}'
        else:
            final_first = f'{fn_tokens[-2]} {fn_tokens[-1]}'

        if final_first.lower() == final_last.lower():
            final_first = random.choice(['Huy', 'Nam', 'Bảo', 'Tuấn', 'Linh', 'Thảo'])

        has_viet = any(c in 'àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ' for c in f'{final_last} {final_first}'.lower()) or final_last in cls.SAFE_SURNAMES
        if has_viet:
            final_full = f'{final_last} {final_first}'
        else:
            final_full = f'{final_first} {final_last}'

        return final_full, final_first, final_last
    _file_cache: Dict[str, List[Tuple[str, str, str]]] = {}

    _cache_lock = threading.Lock()



    CATEGORIES = {

        "1": "vietnamese",

        "2": "western",

        "3": "indian",

        "4": "thai",

        "5": "chinese",

        "6": "korean",

        "7": "japanese",

        "8": "global",

        "9": "file",

        "10": "indonesian",

        "11": "filipino",

        "12": "brazilian",

        "13": "russian",

        "14": "arabic",

        "15": "file_mix",

        "file_mix": "file_mix",

        # Aliases

        "viet": "vietnamese",

        "vietnam": "vietnamese",

        "vietnamese": "vietnamese",

        "vi_vn": "vietnamese",

        "vi": "vietnamese",

        "tay": "western",

        "us": "western",

        "uk": "western",

        "western": "western",

        "en_us": "western",

        "en": "western",

        "an": "indian",

        "ando": "indian",

        "india": "indian",

        "indian": "indian",

        "hi_in": "indian",

        "hi": "indian",

        "thai": "thai",

        "thailand": "thai",

        "th_th": "thai",

        "th": "thai",

        "trung": "chinese",

        "trungquoc": "chinese",

        "china": "chinese",

        "chinese": "chinese",

        "zh_cn": "chinese",

        "zh": "chinese",

        "han": "korean",

        "hanquoc": "korean",

        "korea": "korean",

        "korean": "korean",

        "ko_kr": "korean",

        "ko": "korean",

        "nhat": "japanese",

        "nhatban": "japanese",

        "japan": "japanese",

        "japanese": "japanese",

        "ja_jp": "japanese",

        "ja": "japanese",

        "indo": "indonesian",

        "indonesia": "indonesian",

        "indonesian": "indonesian",

        "id_id": "indonesian",

        "id": "indonesian",

        "philippines": "filipino",

        "philippine": "filipino",

        "filipino": "filipino",

        "pinoy": "filipino",

        "fil_ph": "filipino",

        "ph": "filipino",

        "brazil": "brazilian",

        "brazilian": "brazilian",

        "latin": "brazilian",

        "latino": "brazilian",

        "pt_br": "brazilian",

        "br": "brazilian",

        "nga": "russian",

        "russia": "russian",

        "russian": "russian",

        "ru_ru": "russian",

        "ru": "russian",

        "arap": "arabic",

        "arập": "arabic",

        "arabic": "arabic",

        "arab": "arabic",

        "ar_sa": "arabic",

        "ar_ar": "arabic",

        "ar": "arabic",

        "mix": "global",

        "global": "global",

        "random": "global",

        "all": "global",

        "toancau": "global",

        "file": "file",

        "file_mix": "file_mix",

        "mix_file": "file_mix",

        "custom": "file",

        "auto": "auto_proxy",

        "auto_proxy": "auto_proxy",

        "proxy": "auto_proxy",

        "quoc gia": "auto_proxy",

        "quốc gia": "auto_proxy",

    }



    CATEGORY_LABELS = {

        "vietnamese": "🇻🇳 Tên Việt Nam (vi_VN)",

        "western": "🇺🇸 Tên Tây / US-UK (en_US)",

        "indian": "🇮🇳 Tên Ấn Độ (hi_IN)",

        "thai": "🇹🇭 Tên Thái Lan (th_TH)",

        "chinese": "🇨🇳 Tên Trung Quốc (zh_CN)",

        "korean": "🇰🇷 Tên Hàn Quốc (ko_KR)",

        "japanese": "🇯🇵 Tên Nhật Bản (ja_JP)",

        "indonesian": "🇮🇩 Tên Indonesia (id_ID)",

        "filipino": "🇵🇭 Tên Philippines (fil_PH)",

        "brazilian": "🇧🇷 Tên Brazil / Latin (pt_BR)",

        "russian": "🇷🇺 Tên Nga / Đông Âu (ru_RU)",

        "arabic": "🇸🇦 Tên Ả Rập / Trung Đông (ar_SA)",

        "auto_proxy": "🌍 Tự động theo Quốc gia Proxy (Khuyên dùng)",

        "global": "🌐 Tên Toàn Cầu (Mix tất cả)",

        "file_mix": "🎲 Lấy ngẫu nhiên Họ, Tên trong File (names.txt)",

        "file": "📁 Tên Tự Nhập theo dòng (Kho names.txt)",

    }



    CATEGORY_NAMES = {

        "vietnamese": "Việt Nam (Nguyễn Văn A, Trần Thị B...)",

        "western": "Tây / US-UK (John Smith, Emma Watson...)",

        "indian": "Ấn Độ / Indian (Aarav Sharma, Priya Patel...)",

        "thai": "Thái Lan (Somchai Prasert, Kanya Suksom...)",

        "chinese": "Trung Quốc (Wang Wei, Li Jing...)",

        "korean": "Hàn Quốc (Kim Min-jun, Park Seo-yeon...)",

        "japanese": "Nhật Bản (Sato Ren, Suzuki Hina...)",

        "indonesian": "Indonesia (Budi Wijaya, Putri Saputra...)",

        "filipino": "Philippines (Joshua Santos, Angel Reyes...)",

        "brazilian": "Brazil / Latin (Gabriel Silva, Julia Santos...)",

        "russian": "Nga / Đông Âu (Ivan Ivanov, Anna Smirnov...)",

        "arabic": "Ả Rập / Trung Đông (Mohammed Al-Mansoor, Fatima Al-Harbi...)",

        "auto_proxy": "Tự động theo Quốc gia Proxy (IP nước nào đặt tên nước đó)",

        "global": "Quốc tế Hỗn hợp (Mix ngẫu nhiên tất cả các nước)",

        "file_mix": "Ngẫu nhiên Họ + Tên từ File (names.txt)",

        "file": "Từ File tùy chỉnh (names.txt - Giữ nguyên dòng)",

    }



    @classmethod

    def normalize_category(cls, name_type: Optional[str]) -> str:

        if not name_type:

            return "vietnamese"

        key = str(name_type).lower().strip()

        if key in cls.CATEGORIES:

            return cls.CATEGORIES[key]



        # 1. Tu file tuy chinh & Ghep ngau nhien Ho + Ten tu file

        if "file" in key or "tùy" in key or "tuy" in key or "names.txt" in key or "kho" in key or "file_mix" in key:

            if "ghép" in key or "ghep" in key or "mix" in key or "ngẫu nhiên" in key or "ngau nhien" in key or "họ" in key:

                return "file_mix"

            return "file"



        # 2. Toan cau (Mix ngau nhien tat ca cac quoc gia)

        if "toàn cầu" in key or "toan cau" in key or "toancau" in key or "global" in key or "quốc tế" in key or "quoc te" in key:

            return "global"



        # 3. Tu dong theo IP Proxy

        if "auto" in key or "proxy" in key or "quốc gia" in key or "quoc gia" in key:

            return "auto_proxy"



        # 4. Cac quoc gia cu the

        if "việt" in key or "viet" in key:

            return "vietnamese"

        if "thái" in key or "thai" in key or "th_th" in key:

            return "thai"

        if "trung" in key or "china" in key or "chinese" in key or "zh_cn" in key:

            return "chinese"

        if "hàn" in key or "korea" in key or "korean" in key or "ko_kr" in key or "han quoc" in key:

            return "korean"

        if "nhật" in key or "japan" in key or "japanese" in key or "ja_jp" in key or "nhat ban" in key:

            return "japanese"

        if "ấn" in key or "ando" in key or "an do" in key or "indian" in key or "india" in key or "hi_in" in key:

            return "indian"

        if "tây" in key or "tay" in key or "western" in key or "us-uk" in key or "en_us" in key or "us" in key.split() or "uk" in key.split():

            return "western"

        if "indo" in key:

            return "indonesian"

        if "philip" in key or "filipino" in key or "pinoy" in key:

            return "filipino"

        if "brazil" in key or "latin" in key:

            return "brazilian"

        if "russia" in key or "russian" in key or "ru_ru" in key or bool(re.search(r'nga', key)):

            return "russian"

        if "ả rập" in key or "arap" in key or "arabic" in key or "arab" in key:

            return "arabic"

        if "mix" in key or "ngẫu nhiên" in key:

            return "global"

        return "vietnamese"



    @classmethod

    def load_names_from_file(cls, filepath: str = "names.txt", force_reload: bool = False) -> List[Tuple[str, str, str]]:

        """

        Đọc danh sách họ tên từ file văn bản.

        Trả về danh sách các tuple: (full_name, first_name, last_name).

        """

        with cls._cache_lock:

            if not force_reload and filepath in cls._file_cache and cls._file_cache[filepath]:

                return cls._file_cache[filepath]



            if not os.path.exists(filepath):

                cls._create_sample_names_file(filepath)



            items: List[Tuple[str, str, str]] = []

            try:

                with open(filepath, "r", encoding="utf-8-sig") as f:

                    for line in f:

                        line = line.strip()

                        if not line or line.startswith("#"):

                            continue



                        if "|" in line:

                            parts = [p.strip() for p in line.split("|", 1)]

                            first, last = parts[0], parts[1]

                            full = f"{first} {last}" if first and last else (first or last)

                        elif "," in line:

                            parts = [p.strip() for p in line.split(",", 1)]

                            first, last = parts[0], parts[1]

                            full = f"{first} {last}" if first and last else (first or last)

                        else:

                            tokens = line.split()

                            if len(tokens) == 1:

                                first, last, full = tokens[0], "Nguyen", tokens[0]

                            elif len(tokens) == 2:

                                first, last, full = tokens[0], tokens[1], line

                            else:

                                last = tokens[0]

                                first = " ".join(tokens[1:])

                                full = line



                        full, first, last = cls.sanitize_facebook_name(first, last)
                        items.append((full, first, last))

            except Exception:

                pass



            if not items:

                items = [

                    ("Nguyễn Văn Huy", "Văn Huy", "Nguyễn"),

                    ("John Smith", "John", "Smith"),

                    ("Somchai Prasert", "Somchai", "Prasert"),

                    ("Kim Min-jun", "Min-jun", "Kim"),

                ]



            cls._file_cache[filepath] = items

            return items



    @classmethod

    def save_names_to_file(cls, text: str, filepath: str = "names.txt") -> int:

        """Ghi nội dung mới vào file và làm mới bộ nhớ đệm cache."""

        try:

            with open(filepath, "w", encoding="utf-8") as f:

                f.write(text.strip() + "\n")

            items = cls.load_names_from_file(filepath, force_reload=True)

            return len(items)

        except Exception:

            return 0



    @classmethod

    def get_names_count(cls, filepath: str = "names.txt") -> int:

        """Lấy số lượng tên hợp lệ hiện có trong file."""

        items = cls.load_names_from_file(filepath)

        return len(items)



    @classmethod

    def _create_sample_names_file(cls, filepath: str) -> None:

        """Tạo file names.txt mẫu phong phú đa quốc gia nếu chưa tồn tại."""

        try:

            sample_content = (

                "# =====================================================================\n"

                "# DANH SÁCH HỌ TÊN ĐĂNG KÝ TÙY CHỈNH (CUSTOM NAMES FILE)\n"

                "# Mỗi dòng là một họ tên. Hỗ trợ các định dạng:\n"

                "# 1. Viết liền: John Smith hoặc Nguyễn Văn Nam\n"

                "# 2. Tách bằng dấu gạch đứng: First|Last (Ví dụ: Michael|Brown)\n"

                "# 3. Tách bằng dấu phẩy: First,Last (Ví dụ: Emma,Watson)\n"

                "# Khi reg, tool sẽ tự động bốc ngẫu nhiên một tên trong kho này.\n"

                "# Nếu bật 'Ghép ngẫu nhiên Họ+Tên', tool sẽ mix Họ từ dòng này với Tên từ dòng khác!\n"

                "# =====================================================================\n"

                "John Smith\n"

                "Emma Watson\n"

                "Michael Brown\n"

                "Sophia Davis\n"

                "Alexander Wilson\n"

                "Olivia Miller\n"

                "William Johnson\n"

                "Isabella Taylor\n"

                "David Anderson\n"

                "Emily Thomas\n"

                "James Martinez\n"

                "Aarav Sharma\n"

                "Priya Patel\n"

                "Rahul Kumar\n"

                "Ananya Singh\n"

                "Somchai Prasert\n"

                "Kanya Suksom\n"

                "Thanawat Saetang\n"

                "Ratana Wongsuwan\n"

                "Wang Wei\n"

                "Li Jing\n"

                "Zhang Fang\n"

                "Liu Jun\n"

                "Kim Min-jun\n"

                "Park Seo-yeon\n"

                "Lee Do-yun\n"

                "Choi Ji-woo\n"

                "Sato Ren\n"

                "Suzuki Hina\n"

                "Takahashi Haruto\n"

                "Tanaka Yui\n"

                "Budi Wijaya\n"

                "Putri Saputra\n"

                "Joshua Santos\n"

                "Angel Reyes\n"

                "Gabriel Silva\n"

                "Julia Santos\n"

                "Ivan Ivanov\n"

                "Anna Smirnova\n"

                "Mohammed Al-Mansoor\n"

                "Fatima Al-Harbi\n"

                "Nguyễn Quốc Huy\n"

                "Trần Thị Mai\n"

                "Lê Hoàng Nam\n"

                "Phạm Minh Đức\n"

                "Vũ Kim Hương\n"

            )

            with open(filepath, "w", encoding="utf-8") as f:

                f.write(sample_content)

        except Exception:

            pass



    @classmethod
    def generate_vietnamese_name(cls, gender_val: int = 2) -> Tuple[str, str, str]:
        safe_ho_pool = [h for h in cls.SAFE_SURNAMES if h.lower() not in getattr(cls, 'FLAGGED_SURNAMES', set())]
        ho = random.choice(safe_ho_pool if safe_ho_pool else cls.SAFE_SURNAMES)
        disallowed = getattr(cls, 'DISALLOWED_NAME_TOKENS', set())
        if gender_val == 2:  # Nam
            if random.random() < 0.85:
                first = random.choice(cls.SAFE_FIRST_NAMES_MALE)
            else:
                clean_ten = [t for t in ('Nam', 'Tuấn', 'Huy', 'Hoàng', 'Dũng', 'Long', 'Đạt', 'Khoa', 'Minh', 'Tùng', 'Bảo', 'Hải', 'Hùng', 'Phong', 'Sơn', 'Trung', 'Kiên', 'Thịnh', 'Đức', 'Quân', 'Thắng', 'Khánh', 'Việt', 'Trí', 'Toàn', 'Bình', 'Hiếu', 'Duy') if t != ho and t.lower() not in disallowed]
                first = random.choice(clean_ten)
            last = ho
        else:  # Nữ
            if random.random() < 0.85:
                first = random.choice(cls.SAFE_FIRST_NAMES_FEMALE)
            else:
                clean_ten = [t for t in ('Trang', 'Linh', 'Hương', 'Lan', 'Huyền', 'Nhi', 'Vy', 'Thảo', 'Hà', 'Ngân', 'Hoa', 'Tuyết', 'Mai', 'Quỳnh', 'Anh', 'Dung', 'Oanh', 'Hằng', 'Thư', 'Vân', 'Yến', 'Ngọc', 'Hạnh', 'Loan') if t != ho and t.lower() not in disallowed]
                first = random.choice(clean_ten)
            last = ho
        return cls.sanitize_facebook_name(first, last)
    @classmethod

    def generate_western_name(cls, gender_val: int = 2) -> Tuple[str, str, str]:

        first = random.choice(FIRST_NAMES_MALE_WESTERN) if gender_val == 2 else random.choice(FIRST_NAMES_FEMALE_WESTERN)

        last = random.choice(LAST_NAMES_WESTERN)

        full = f"{first} {last}"

        return full, first, last



    @classmethod

    def generate_indian_name(cls, gender_val: int = 2) -> Tuple[str, str, str]:

        first = random.choice(FIRST_NAMES_MALE_INDIAN) if gender_val == 2 else random.choice(FIRST_NAMES_FEMALE_INDIAN)

        last = random.choice(LAST_NAMES_INDIAN)

        full = f"{first} {last}"

        return full, first, last



    @classmethod

    def generate_thai_name(cls, gender_val: int = 2) -> Tuple[str, str, str]:

        first = random.choice(FIRST_NAMES_MALE_THAI) if gender_val == 2 else random.choice(FIRST_NAMES_FEMALE_THAI)

        last = random.choice(LAST_NAMES_THAI)

        full = f"{first} {last}"

        return full, first, last



    @classmethod

    def generate_chinese_name(cls, gender_val: int = 2) -> Tuple[str, str, str]:

        first = random.choice(FIRST_NAMES_MALE_CHINESE) if gender_val == 2 else random.choice(FIRST_NAMES_FEMALE_CHINESE)

        last = random.choice(LAST_NAMES_CHINESE)

        full = f"{last} {first}"

        return full, first, last



    @classmethod

    def generate_korean_name(cls, gender_val: int = 2) -> Tuple[str, str, str]:

        first = random.choice(FIRST_NAMES_MALE_KOREAN) if gender_val == 2 else random.choice(FIRST_NAMES_FEMALE_KOREAN)

        last = random.choice(LAST_NAMES_KOREAN)

        full = f"{last} {first}"

        return full, first, last



    @classmethod

    def generate_japanese_name(cls, gender_val: int = 2) -> Tuple[str, str, str]:

        first = random.choice(FIRST_NAMES_MALE_JAPANESE) if gender_val == 2 else random.choice(FIRST_NAMES_FEMALE_JAPANESE)

        last = random.choice(LAST_NAMES_JAPANESE)

        full = f"{last} {first}"

        return full, first, last



    @classmethod

    def generate_indonesian_name(cls, gender_val: int = 2) -> Tuple[str, str, str]:

        first = random.choice(FIRST_NAMES_MALE_INDONESIAN) if gender_val == 2 else random.choice(FIRST_NAMES_FEMALE_INDONESIAN)

        last = random.choice(LAST_NAMES_INDONESIAN)

        full = f"{first} {last}"

        return full, first, last



    @classmethod

    def generate_filipino_name(cls, gender_val: int = 2) -> Tuple[str, str, str]:

        first = random.choice(FIRST_NAMES_MALE_FILIPINO) if gender_val == 2 else random.choice(FIRST_NAMES_FEMALE_FILIPINO)

        last = random.choice(LAST_NAMES_FILIPINO)

        full = f"{first} {last}"

        return full, first, last



    @classmethod

    def generate_brazilian_name(cls, gender_val: int = 2) -> Tuple[str, str, str]:

        first = random.choice(FIRST_NAMES_MALE_BRAZILIAN) if gender_val == 2 else random.choice(FIRST_NAMES_FEMALE_BRAZILIAN)

        last = random.choice(LAST_NAMES_BRAZILIAN)

        full = f"{first} {last}"

        return full, first, last



    @classmethod

    def generate_russian_name(cls, gender_val: int = 2) -> Tuple[str, str, str]:

        first = random.choice(FIRST_NAMES_MALE_RUSSIAN) if gender_val == 2 else random.choice(FIRST_NAMES_FEMALE_RUSSIAN)

        last = random.choice(LAST_NAMES_RUSSIAN)

        full = f"{first} {last}"

        return full, first, last



    @classmethod

    def generate_arabic_name(cls, gender_val: int = 2) -> Tuple[str, str, str]:

        first = random.choice(FIRST_NAMES_MALE_ARABIC) if gender_val == 2 else random.choice(FIRST_NAMES_FEMALE_ARABIC)

        last = random.choice(LAST_NAMES_ARABIC)

        full = f"{first} {last}"

        return full, first, last



    @classmethod

    def generate_global_name(cls, gender_val: int = 2) -> Tuple[str, str, str, str]:

        pool = [

            ("vietnamese", "Việt Nam", cls.generate_vietnamese_name),

            ("western", "Tây (US-UK)", cls.generate_western_name),

            ("indian", "Ấn Độ", cls.generate_indian_name),

            ("thai", "Thái Lan", cls.generate_thai_name),

            ("chinese", "Trung Quốc", cls.generate_chinese_name),

            ("korean", "Hàn Quốc", cls.generate_korean_name),

            ("japanese", "Nhật Bản", cls.generate_japanese_name),

            ("indonesian", "Indonesia", cls.generate_indonesian_name),

            ("filipino", "Philippines", cls.generate_filipino_name),

            ("brazilian", "Brazil", cls.generate_brazilian_name),

            ("russian", "Nga", cls.generate_russian_name),

            ("arabic", "Ả Rập", cls.generate_arabic_name),

        ]

        cat, label, gen_fn = random.choice(pool)

        full, first, last = gen_fn(gender_val)

        return full, first, last, f"Toàn cầu ({label})"



    @classmethod

    def generate_name(

        cls,

        name_type: str = "vietnamese",

        gender_val: Optional[int] = None,

        custom_file: Optional[str] = None,

        mix_file_names: bool = False,

    ) -> GeneratedName:

        norm_type = cls.normalize_category(name_type)

        if gender_val is None:

            gender_val = 2 if random.random() < 0.50 else 1



        gender_str = "Nam (2)" if gender_val == 2 else "Nữ (1)"



        if norm_type in ("file", "file_mix"):

            filepath = custom_file or "names.txt"

            name_list = cls.load_names_from_file(filepath)

            is_mix = mix_file_names or (norm_type == "file_mix")

            if is_mix and len(name_list) > 1:

                item_first = random.choice(name_list)

                item_last = random.choice(name_list)

                first = item_first[1] or "Huy"

                last = item_last[2] or "Nguyen"

                has_viet_mark = any(c in "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ" for c in f"{last} {first}".lower()) or last in HO_VIET

                full = f"{last} {first}" if has_viet_mark else f"{first} {last}"

                display_tag = f"File (Ghép: {os.path.basename(filepath)})"

            else:

                full, first, last = random.choice(name_list)

                display_tag = f"Từ File ({os.path.basename(filepath)})"

            actual_cat = norm_type



        elif norm_type == "western":

            full, first, last = cls.generate_western_name(gender_val)

            display_tag = "Tây (US-UK)"

            actual_cat = "western"



        elif norm_type == "indian":

            full, first, last = cls.generate_indian_name(gender_val)

            display_tag = "Ấn Độ"

            actual_cat = "indian"



        elif norm_type == "thai":

            full, first, last = cls.generate_thai_name(gender_val)

            display_tag = "Thái Lan"

            actual_cat = "thai"



        elif norm_type == "chinese":

            full, first, last = cls.generate_chinese_name(gender_val)

            display_tag = "Trung Quốc"

            actual_cat = "chinese"



        elif norm_type == "korean":

            full, first, last = cls.generate_korean_name(gender_val)

            display_tag = "Hàn Quốc"

            actual_cat = "korean"



        elif norm_type == "japanese":

            full, first, last = cls.generate_japanese_name(gender_val)

            display_tag = "Nhật Bản"

            actual_cat = "japanese"



        elif norm_type == "indonesian":

            full, first, last = cls.generate_indonesian_name(gender_val)

            display_tag = "Indonesia"

            actual_cat = "indonesian"



        elif norm_type == "filipino":

            full, first, last = cls.generate_filipino_name(gender_val)

            display_tag = "Philippines"

            actual_cat = "filipino"



        elif norm_type == "brazilian":

            full, first, last = cls.generate_brazilian_name(gender_val)

            display_tag = "Brazil"

            actual_cat = "brazilian"



        elif norm_type == "russian":

            full, first, last = cls.generate_russian_name(gender_val)

            display_tag = "Nga"

            actual_cat = "russian"



        elif norm_type == "arabic":

            full, first, last = cls.generate_arabic_name(gender_val)

            display_tag = "Ả Rập"

            actual_cat = "arabic"



        elif norm_type == "global":

            full, first, last, display_tag = cls.generate_global_name(gender_val)

            actual_cat = "global"



        else:  # vietnamese

            full, first, last = cls.generate_vietnamese_name(gender_val)

            display_tag = "Việt Nam"

            actual_cat = "vietnamese"



        # Luôn chuẩn hóa cuối cùng qua sanitize_facebook_name để đảm bảo an toàn tuyệt đối
        san_full, san_first, san_last = cls.sanitize_facebook_name(first, last)
        first, last, full = san_first, san_last, san_full



        return GeneratedName(

            full_name=full,

            first_name=first,

            last_name=last,

            gender_val=gender_val,

            gender_str=gender_str,

            category=actual_cat,

            display_tag=display_tag,

        )



    @classmethod

    def interactive_select_name_type(cls, current_default: str = "vietnamese") -> Tuple[str, str, bool]:

        """

        Hiển thị hộp chọn (Selectbox) tương tác trên Terminal để người dùng chọn bộ tên.

        Trả về tuple (name_type, custom_file_path, mix_file_names).

        """

        try:

            from colorama import Fore, Style

            cyan = Fore.CYAN

            green = Fore.GREEN

            yellow = Fore.YELLOW

            white = Fore.WHITE

            reset = Style.RESET_ALL

        except Exception:

            cyan = green = yellow = white = reset = ""



        current_norm = cls.normalize_category(current_default)

        num_map = {

            "vietnamese": "1", "western": "2", "indian": "3",

            "thai": "4", "chinese": "5", "korean": "6", "japanese": "7",

            "global": "8", "file": "9", "indonesian": "10", "filipino": "11",

            "brazilian": "12", "russian": "13", "arabic": "14"

        }

        current_num = num_map.get(current_norm, "1")



        print(f"\n{cyan}╔══════════════════════════════════════════════════════════════════════╗{reset}")

        print(f"{cyan}║{yellow}                 CHỌN BỘ TÊN ĐĂNG KÝ (NAME GENERATOR)                 {cyan}║{reset}")

        print(f"{cyan}╚══════════════════════════════════════════════════════════════════════╝{reset}")

        print(f"  {green}[1]{reset} {white}Tên Việt Nam{reset}          (Nguyễn Văn Nam, Trần Thị Mai...)")

        print(f"  {green}[2]{reset} {white}Tên Tây / US-UK{reset}       (John Smith, Emma Watson, Michael Brown...)")

        print(f"  {green}[3]{reset} {white}Tên Ấn Độ (Indian){reset}    (Aarav Sharma, Priya Patel, Rahul Kumar...)")

        print(f"  {green}[4]{reset} {white}Tên Thái Lan (Thai){reset}    (Somchai Prasert, Kanya Suksom...)")

        print(f"  {green}[5]{reset} {white}Tên Trung Quốc{reset}         (Wang Wei, Li Jing, Zhang Fang...)")

        print(f"  {green}[6]{reset} {white}Tên Hàn Quốc{reset}           (Kim Min-jun, Park Seo-yeon, Lee Do-yun...)")

        print(f"  {green}[7]{reset} {white}Tên Nhật Bản{reset}           (Sato Ren, Suzuki Hina, Tanaka Yui...)")

        print(f"  {green}[8]{reset} {white}Tên Toàn Cầu Hỗn Hợp{reset}   (Mix ngẫu nhiên: VN, US, IN, TH, CN, KR, JP, ID...)")

        print(f"  {green}[9]{reset} {white}Lấy từ File Tùy Chọn{reset}  (Đọc từ names.txt, hỗ trợ ghép ngẫu nhiên)")

        print(f"  {green}[10]{reset} {white}Tên Indonesia{reset}        (Budi Wijaya, Putri Saputra...)")

        print(f"  {green}[11]{reset} {white}Tên Philippines{reset}      (Joshua Santos, Angel Reyes...)")

        print(f"  {green}[12]{reset} {white}Tên Brazil / Latin{reset}   (Gabriel Silva, Julia Santos...)")

        print(f"  {green}[13]{reset} {white}Tên Nga / Đông Âu{reset}    (Ivan Ivanov, Anna Smirnova...)")

        print(f"  {green}[14]{reset} {white}Tên Ả Rập (Middle East){reset} (Mohammed Al-Mansoor, Fatima Al-Harbi...)")

        print(f"{cyan}----------------------------------------------------------------------{reset}")



        try:

            choice = input(f"Lựa chọn [1-14] (Mặc định: {current_num} - {cls.CATEGORY_NAMES.get(current_norm, 'Việt Nam')}): ").strip()

        except (EOFError, KeyboardInterrupt):

            choice = ""



        if not choice:

            choice = current_num



        chosen_type = cls.CATEGORIES.get(choice, cls.normalize_category(choice))

        custom_file = "names.txt"

        mix_names = False



        if chosen_type == "file":

            print(f"\n{yellow}--- CẤU HÌNH FILE HỌ TÊN RIÊNG ---{reset}")

            try:

                f_path = input("Đường dẫn file names (Mặc định: names.txt): ").strip()

                if f_path:

                    custom_file = f_path

                m_choice = input("Ghép ngẫu nhiên Họ và Tên giữa các dòng? (y/N): ").strip().lower()

                mix_names = m_choice in ("y", "yes", "1", "true")

            except (EOFError, KeyboardInterrupt):

                pass

            count = cls.get_names_count(custom_file)

            print(f"{green}✓ Đã tải {count} tên từ '{custom_file}' (Ghép ngẫu nhiên: {'Bật' if mix_names else 'Tắt'}){reset}\n")

        else:

            print(f"{green}✓ Đã chọn bộ họ tên: {cls.CATEGORY_NAMES.get(chosen_type, chosen_type)}{reset}\n")



        return chosen_type, custom_file, mix_names

