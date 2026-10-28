# -*- coding: utf-8 -*-

"""

core.session_builder

Bộ tạo hồ sơ thiết bị di động thật đa dạng cao cấp (Ultra-Random Authentic Device Profiler).

Bao gồm >35 mẫu smartphone phổ biến nhất của Samsung, Xiaomi, Oppo, Vivo, Realme, OnePlus, Google Pixel, iPhone.

Đảm bảo tính nhất quán tuyệt đối giữa phần cứng, màn hình, TLS JA4 và Client Hints.

"""



import base64

import os

import random

from dataclasses import dataclass

from typing import Dict, Any, Optional, Union, List, Tuple

from curl_cffi import requests



from core.models import ProxyItem





@dataclass

class DeviceProfile:

    name: str

    brand: str

    model: str

    os_name: str

    os_version: str

    chrome_major: str

    viewport_width: int

    viewport_height: int

    pixel_ratio: float

    impersonate: str

    user_agent: str

    sec_ch_ua: str

    sec_ch_ua_mobile: str = "?1"

    sec_ch_ua_platform: str = '"Android"'

    sec_ch_ua_platform_version: str = '"14.0.0"'

    sec_ch_ua_model: str = '""'

    sec_ch_dpr: str = ""

    sec_ch_viewport_width: str = ""

    sec_ch_prefers_color_scheme: str = '"light"'

    sec_ch_ua_arch: str = '"arm"'

    sec_ch_ua_bitness: str = '"64"'

    screen_width: int = 1080

    screen_height: int = 2400

    carrier: str = "Viettel"

    country_code: str = "VN"

    mcc: str = "452"

    mnc: str = "04"

    sim_country_iso: str = "vn"

    locale: str = "vi_VN"

    accept_language: str = "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"

    timezone: str = "Asia/Ho_Chi_Minh"

    timezone_offset_minutes: int = 420

    sim_state: int = 5

    network_type: int = 13

    soc_chipset: str = "Qualcomm Snapdragon 8 Gen 2"

    is_fb_app: bool = False

    supports_fresco: bool = False

    fb_version: str = "448.0.0.38.115"

    fb_build: str = "547812903"

    gl_renderer: str = "Adreno (TM) 740"
    app_user_agent: str = ""
    dalvik_user_agent: str = ""
    web_user_agent: str = ""
    raw_app_ua: str = ""





# Danh mục các dòng máy di động Android thực tế phong phú (>70 dòng máy)

RAW_ANDROID_MODELS = [

    # Samsung Flagship, Midrange & Entry

    ("Samsung", "Galaxy S24 Ultra", "SM-S928B", "14", "131", 384, 824, 3.75, "chrome131_android"),

    ("Samsung", "Galaxy S24+", "SM-S926B", "14", "131", 384, 824, 3.75, "chrome131_android"),

    ("Samsung", "Galaxy S24", "SM-S921B", "14", "131", 360, 780, 3.0, "chrome131_android"),

    ("Samsung", "Galaxy S23 Ultra", "SM-S918B", "14", "124", 384, 824, 3.75, "chrome131_android"),

    ("Samsung", "Galaxy S23+", "SM-S916B", "14", "124", 360, 780, 3.0, "chrome131_android"),

    ("Samsung", "Galaxy S23", "SM-S911B", "14", "124", 360, 780, 3.0, "chrome131_android"),

    ("Samsung", "Galaxy S23 FE", "SM-S711B", "14", "131", 360, 800, 3.0, "chrome131_android"),

    ("Samsung", "Galaxy S22 Ultra", "SM-S908B", "13", "120", 384, 824, 3.75, "chrome131_android"),

    ("Samsung", "Galaxy S22", "SM-S901B", "13", "120", 360, 780, 3.0, "chrome131_android"),

    ("Samsung", "Galaxy S21 FE", "SM-G990B", "13", "124", 360, 800, 3.0, "chrome131_android"),

    ("Samsung", "Galaxy S21 5G", "SM-G991B", "13", "120", 360, 800, 3.0, "chrome131_android"),

    ("Samsung", "Galaxy A55 5G", "SM-A556B", "14", "131", 412, 915, 2.625, "chrome131_android"),

    ("Samsung", "Galaxy A54 5G", "SM-A546B", "14", "124", 412, 915, 2.625, "chrome131_android"),

    ("Samsung", "Galaxy A35 5G", "SM-A356B", "14", "131", 412, 915, 2.625, "chrome131_android"),

    ("Samsung", "Galaxy A34 5G", "SM-A346B", "13", "120", 412, 915, 2.625, "chrome131_android"),

    ("Samsung", "Galaxy A25 5G", "SM-A256B", "14", "131", 384, 854, 2.8125, "chrome131_android"),

    ("Samsung", "Galaxy A15", "SM-A155F", "14", "131", 384, 854, 2.8125, "chrome131_android"),

    ("Samsung", "Galaxy A14 5G", "SM-A146P", "13", "120", 384, 854, 2.8125, "chrome131_android"),

    ("Samsung", "Galaxy Z Flip 5", "SM-F731B", "14", "124", 412, 1014, 2.625, "chrome131_android"),

    ("Samsung", "Galaxy Z Fold 5", "SM-F946B", "14", "131", 373, 905, 2.89, "chrome131_android"),



    # Xiaomi & Redmi & POCO

    ("Xiaomi", "Xiaomi 14 Pro", "23116PN5BC", "14", "131", 393, 852, 3.0, "chrome131_android"),

    ("Xiaomi", "Xiaomi 14", "23127PN0CG", "14", "131", 393, 852, 3.0, "chrome131_android"),

    ("Xiaomi", "Xiaomi 13T Pro", "23078PND5G", "13", "124", 393, 852, 3.0, "chrome131_android"),

    ("Xiaomi", "Xiaomi 13T", "2306EPN60G", "13", "124", 393, 852, 3.0, "chrome131_android"),

    ("Xiaomi", "Xiaomi 13 Pro", "2210132G", "13", "124", 393, 852, 3.0, "chrome131_android"),

    ("Xiaomi", "Xiaomi 13", "2211133G", "14", "124", 393, 852, 3.0, "chrome131_android"),

    ("Xiaomi", "Xiaomi 12", "2201123G", "13", "120", 360, 800, 3.0, "chrome131_android"),

    ("Xiaomi", "Redmi Note 13 Pro+", "23090RA98G", "13", "131", 393, 873, 2.75, "chrome131_android"),

    ("Xiaomi", "Redmi Note 13 Pro", "23117RA68G", "13", "124", 393, 873, 2.75, "chrome131_android"),

    ("Xiaomi", "Redmi Note 13 5G", "2312DRAABG", "13", "124", 393, 873, 2.75, "chrome131_android"),

    ("Xiaomi", "Redmi Note 13", "2312DRA50G", "13", "124", 393, 873, 2.75, "chrome131_android"),

    ("Xiaomi", "Redmi Note 12 Pro", "22101316G", "13", "124", 393, 873, 2.75, "chrome131_android"),

    ("Xiaomi", "Redmi Note 12", "23021RAAEG", "13", "120", 393, 873, 2.75, "chrome131_android"),

    ("Xiaomi", "Redmi 13C", "23100RN82L", "13", "120", 360, 800, 2.0, "chrome131_android"),

    ("Xiaomi", "Redmi 12", "23053RN02Y", "13", "120", 393, 873, 2.75, "chrome131_android"),

    ("Xiaomi", "POCO F6", "24069PC21G", "14", "131", 393, 873, 2.75, "chrome131_android"),

    ("Xiaomi", "POCO F5 Pro", "23013PC75G", "13", "124", 393, 873, 2.75, "chrome131_android"),

    ("Xiaomi", "POCO F5", "23049PCD8G", "13", "124", 393, 873, 2.75, "chrome131_android"),

    ("Xiaomi", "POCO X6 Pro", "2311DRK48G", "14", "131", 393, 873, 2.75, "chrome131_android"),

    ("Xiaomi", "POCO X6", "23122PCD1G", "14", "131", 393, 873, 2.75, "chrome131_android"),

    ("Xiaomi", "POCO X5 Pro", "22101320G", "13", "120", 393, 873, 2.75, "chrome131_android"),

    ("Xiaomi", "POCO M6 Pro", "2312FPCA6G", "13", "124", 393, 873, 2.75, "chrome131_android"),



    # Oppo

    ("Oppo", "Find X6 Pro", "PGEM10", "13", "131", 412, 915, 3.5, "chrome131_android"),

    ("Oppo", "Find X5 Pro", "CPH2305", "13", "120", 412, 915, 3.5, "chrome131_android"),

    ("Oppo", "Reno11 Pro 5G", "CPH2607", "14", "131", 360, 800, 3.0, "chrome131_android"),

    ("Oppo", "Reno11 5G", "CPH2599", "14", "131", 360, 800, 3.0, "chrome131_android"),

    ("Oppo", "Reno10 Pro 5G", "CPH2525", "13", "124", 360, 800, 3.0, "chrome131_android"),

    ("Oppo", "Reno10 5G", "CPH2531", "13", "124", 360, 800, 3.0, "chrome131_android"),

    ("Oppo", "Reno8 5G", "CPH2359", "13", "120", 360, 800, 3.0, "chrome131_android"),

    ("Oppo", "A79 5G", "CPH2557", "13", "124", 360, 800, 2.4, "chrome131_android"),

    ("Oppo", "A78 5G", "CPH2565", "13", "120", 360, 800, 2.0, "chrome131_android"),

    ("Oppo", "A58", "CPH2577", "13", "120", 360, 800, 2.0, "chrome131_android"),



    # Vivo

    ("Vivo", "Vivo X100 Pro", "V2324A", "14", "131", 393, 873, 2.75, "chrome131_android"),

    ("Vivo", "Vivo V30 5G", "V2318", "14", "131", 393, 873, 2.75, "chrome131_android"),

    ("Vivo", "Vivo V30e", "V2339", "14", "131", 393, 873, 2.75, "chrome131_android"),

    ("Vivo", "Vivo V29", "V2250", "13", "124", 393, 873, 2.75, "chrome131_android"),

    ("Vivo", "Vivo V27", "V2246", "13", "120", 393, 873, 2.75, "chrome131_android"),

    ("Vivo", "Vivo Y36", "V2247", "13", "120", 393, 873, 2.75, "chrome131_android"),

    ("Vivo", "Vivo Y27", "V2249", "13", "120", 360, 800, 2.4, "chrome131_android"),



    # Realme & OnePlus

    ("Realme", "Realme 12 Pro+ 5G", "RMX3840", "14", "131", 393, 873, 2.75, "chrome131_android"),

    ("Realme", "Realme 12+ 5G", "RMX3867", "14", "131", 393, 873, 2.75, "chrome131_android"),

    ("Realme", "Realme 11 Pro+", "RMX3740", "13", "124", 393, 873, 2.75, "chrome131_android"),

    ("Realme", "Realme 11", "RMX3780", "13", "124", 360, 800, 3.0, "chrome131_android"),

    ("Realme", "Realme 10", "RMX3630", "13", "120", 360, 800, 3.0, "chrome131_android"),

    ("Realme", "Realme C67", "RMX3890", "14", "131", 360, 800, 2.4, "chrome131_android"),

    ("Realme", "Realme C55", "RMX3710", "13", "120", 360, 800, 2.4, "chrome131_android"),

    ("OnePlus", "OnePlus 12", "CPH2581", "14", "131", 412, 915, 3.5, "chrome131_android"),

    ("OnePlus", "OnePlus 12R", "CPH2609", "14", "131", 412, 915, 3.0, "chrome131_android"),

    ("OnePlus", "OnePlus 11", "CPH2449", "13", "124", 412, 915, 3.5, "chrome131_android"),

    ("OnePlus", "OnePlus Nord 3", "CPH2493", "13", "124", 412, 915, 3.0, "chrome131_android"),

    ("OnePlus", "OnePlus Nord CE 3", "CPH2569", "13", "124", 393, 873, 2.75, "chrome131_android"),



    # Google Pixel

    ("Google", "Pixel 8 Pro", "Pixel 8 Pro", "14", "131", 412, 892, 2.625, "chrome131_android"),

    ("Google", "Pixel 8", "Pixel 8", "14", "131", 412, 892, 2.625, "chrome131_android"),

    ("Google", "Pixel 8a", "Pixel 8a", "14", "131", 412, 915, 2.625, "chrome131_android"),

    ("Google", "Pixel 7 Pro", "Pixel 7 Pro", "13", "124", 412, 892, 2.625, "chrome131_android"),

    ("Google", "Pixel 7a", "Pixel 7a", "14", "124", 412, 915, 2.625, "chrome131_android"),

    ("Google", "Pixel 7", "Pixel 7", "14", "124", 412, 915, 2.625, "chrome131_android"),

    ("Google", "Pixel 6a", "Pixel 6a", "13", "120", 412, 915, 2.625, "chrome131_android"),

    ("Google", "Pixel 6", "Pixel 6", "13", "120", 412, 915, 2.625, "chrome131_android"),



    # Sony & Asus & Motorola

    ("Sony", "Xperia 1 V", "XQ-DQ72", "14", "131", 384, 854, 3.5, "chrome131_android"),

    ("Sony", "Xperia 5 V", "XQ-DE72", "14", "131", 384, 854, 2.8125, "chrome131_android"),

    ("Asus", "ROG Phone 8", "ASUS_AI2401", "14", "131", 393, 852, 2.75, "chrome131_android"),

    ("Motorola", "Edge 50 Pro", "XT2403-2", "14", "131", 393, 873, 2.75, "chrome131_android"),

    ("Samsung", "Galaxy Z Fold 6", "SM-F956B", "14", "131", 373, 905, 2.89, "chrome131_android"),

    ("Samsung", "Galaxy Z Flip 6", "SM-F741B", "14", "131", 412, 1014, 2.625, "chrome131_android"),

    ("Samsung", "Galaxy S24 Ultra (512GB)", "SM-S928B", "14", "131", 384, 824, 3.75, "chrome131_android"),

    ("Samsung", "Galaxy S23 Ultra (12GB)", "SM-S9180", "14", "124", 384, 824, 3.75, "chrome131_android"),

    ("Google", "Pixel 9 Pro", "Pixel 9 Pro", "14", "131", 412, 892, 2.625, "chrome131_android"),

    ("Google", "Pixel 9", "Pixel 9", "14", "131", 412, 892, 2.625, "chrome131_android"),

    ("Xiaomi", "Xiaomi 14 Ultra", "24030PN60G", "14", "131", 393, 852, 3.0, "chrome131_android"),

    ("Xiaomi", "Redmi K70 Pro", "23117RK66C", "14", "131", 393, 852, 3.0, "chrome131_android"),

    ("Vivo", "Vivo X100 Ultra", "V2359A", "14", "131", 393, 873, 2.75, "chrome131_android"),

    ("Oppo", "Find X7 Ultra", "PHY110", "14", "131", 412, 915, 3.5, "chrome131_android"),

    ("OnePlus", "OnePlus Open", "CPH2551", "14", "131", 412, 915, 3.5, "chrome131_android"),

    ("Realme", "Realme GT5 Pro", "RMX3888", "14", "131", 393, 873, 2.75, "chrome131_android"),

]



CHROME_SUBVERSIONS = {

    "131": ["6778.39", "6778.69", "6778.85", "6778.104", "6778.135", "6778.158", "6778.204", "6778.260"],

    "124": ["6367.60", "6367.78", "6367.82", "6367.113", "6367.118", "6367.159", "6367.179", "6367.201", "6367.207"],

    "120": ["6099.115", "6099.144", "6099.193", "6099.210", "6099.230", "6099.235"],

}



CARRIERS = ["Viettel", "VinaPhone", "MobiFone", "Vietnamobile"]





KATANA_RELEASES = [

    ("445.0.0.34.118", "542312984"),

    ("448.0.0.38.115", "547812903"),

    ("450.0.0.40.109", "551294812"),

    ("453.0.0.42.110", "555192834"),

    ("455.0.0.44.112", "558910403"),

    ("458.0.0.41.114", "561298451"),

    ("460.0.0.45.115", "563910294"),

    ("463.0.0.48.111", "568194012"),

    ("465.0.0.51.108", "571829410"),

    ("468.0.0.40.106", "576201943"),

    ("470.0.0.42.110", "579841295"),

    ("473.0.0.39.108", "584192055"),

    ("475.0.0.44.112", "588491024"),

    ("478.0.0.46.109", "592184910"),

    ("480.0.0.50.111", "596102948"),
]

# Tích hợp mở rộng toàn diện 462 bản phát hành Facebook Katana từ Mr-SxR FB-APP_User-Agent_Maker
try:
    from core.fb_user_agent_maker import get_all_katana_releases as _get_all_katana_releases
    _ext_releases = _get_all_katana_releases()
    if _ext_releases:
        KATANA_RELEASES = list(_ext_releases)
except Exception:
    pass



ANDROID_BUILD_TAGS = [

    "UP1A.231005.007",

    "UP1A.231105.001",

    "TP1A.220624.014",

    "TP1A.220905.001",

    "TKQ1.220829.002",

    "TKQ1.221114.001",

    "AP1A.240405.002",

    "AP2A.240805.005",

    "UKQ1.230917.001",

    "UKQ1.231003.002",

    "SKQ1.210216.001",

    "SP1A.210812.016",

]







MODEL_HARDWARE_SPECS: Dict[str, Tuple[str, str]] = {

    # Samsung Flagships & Midranges

    "SM-S928B": ("Qualcomm Snapdragon 8 Gen 3", "Adreno (TM) 750"),

    "SM-S926B": ("Samsung Exynos 2400", "Samsung Xclipse 940"),

    "SM-S921B": ("Samsung Exynos 2400", "Samsung Xclipse 940"),

    "SM-S918B": ("Qualcomm Snapdragon 8 Gen 2", "Adreno (TM) 740"),

    "SM-S9180": ("Qualcomm Snapdragon 8 Gen 2", "Adreno (TM) 740"),

    "SM-S916B": ("Qualcomm Snapdragon 8 Gen 2", "Adreno (TM) 740"),

    "SM-S911B": ("Qualcomm Snapdragon 8 Gen 2", "Adreno (TM) 740"),

    "SM-S711B": ("Samsung Exynos 2200", "Samsung Xclipse 920"),

    "SM-S908B": ("Qualcomm Snapdragon 8 Gen 1", "Adreno (TM) 730"),

    "SM-S901B": ("Qualcomm Snapdragon 8 Gen 1", "Adreno (TM) 730"),

    "SM-G990B": ("Qualcomm Snapdragon 888", "Adreno (TM) 660"),

    "SM-G991B": ("Samsung Exynos 2100", "Mali-G78 MP14"),

    "SM-A556B": ("Samsung Exynos 1480", "Samsung Xclipse 530"),

    "SM-A546B": ("Samsung Exynos 1380", "Mali-G68 MP5"),

    "SM-A356B": ("Samsung Exynos 1380", "Mali-G68 MP5"),

    "SM-A346B": ("MediaTek Dimensity 1080", "Mali-G68 MC4"),

    "SM-A256B": ("Samsung Exynos 1280", "Mali-G68"),

    "SM-A155F": ("MediaTek Helio G99", "Mali-G57 MC2"),

    "SM-A146P": ("MediaTek Dimensity 700", "Mali-G57 MC2"),

    "SM-F731B": ("Qualcomm Snapdragon 8 Gen 2", "Adreno (TM) 740"),

    "SM-F946B": ("Qualcomm Snapdragon 8 Gen 2", "Adreno (TM) 740"),

    "SM-F956B": ("Qualcomm Snapdragon 8 Gen 3", "Adreno (TM) 750"),

    "SM-F741B": ("Qualcomm Snapdragon 8 Gen 3", "Adreno (TM) 750"),



    # Xiaomi & POCO & Redmi

    "23116PN5BC": ("Qualcomm Snapdragon 8 Gen 3", "Adreno (TM) 750"),

    "23127PN0CG": ("Qualcomm Snapdragon 8 Gen 3", "Adreno (TM) 750"),

    "24030PN60G": ("Qualcomm Snapdragon 8 Gen 3", "Adreno (TM) 750"),

    "23078PND5G": ("MediaTek Dimensity 9200+", "Immortalis-G715 MC11"),

    "2306EPN60G": ("MediaTek Dimensity 8200 Ultra", "Mali-G610 MC6"),

    "2210132G": ("Qualcomm Snapdragon 8 Gen 2", "Adreno (TM) 740"),

    "2211133G": ("Qualcomm Snapdragon 8 Gen 2", "Adreno (TM) 740"),

    "2201123G": ("Qualcomm Snapdragon 8 Gen 1", "Adreno (TM) 730"),

    "23090RA98G": ("MediaTek Dimensity 7200 Ultra", "Mali-G610 MC4"),

    "23117RA68G": ("Qualcomm Snapdragon 7s Gen 2", "Adreno (TM) 710"),

    "2312DRAABG": ("MediaTek Dimensity 6080", "Mali-G57 MC2"),

    "2312DRA50G": ("Qualcomm Snapdragon 685", "Adreno (TM) 610"),

    "22101316G": ("MediaTek Dimensity 1080", "Mali-G68 MC4"),

    "23021RAAEG": ("Qualcomm Snapdragon 685", "Adreno (TM) 610"),

    "23100RN82L": ("MediaTek Helio G85", "Mali-G52 MC2"),

    "23053RN02Y": ("MediaTek Helio G88", "Mali-G52 MC2"),

    "24069PC21G": ("Qualcomm Snapdragon 8s Gen 3", "Adreno (TM) 735"),

    "23013PC75G": ("Qualcomm Snapdragon 8+ Gen 1", "Adreno (TM) 730"),

    "23117RK66C": ("Qualcomm Snapdragon 8 Gen 3", "Adreno (TM) 750"),



    # Google Pixel

    "Pixel 9 Pro": ("Google Tensor G4", "Immortalis-G715s MC10"),

    "Pixel 9": ("Google Tensor G4", "Immortalis-G715s MC10"),

    "Pixel 8 Pro": ("Google Tensor G3", "Immortalis-G715s MC10"),

    "Pixel 8": ("Google Tensor G3", "Immortalis-G715s MC10"),

    "Pixel 8a": ("Google Tensor G3", "Immortalis-G715s MC10"),

    "Pixel 7 Pro": ("Google Tensor G2", "Mali-G710 MP7"),

    "Pixel 7a": ("Google Tensor G2", "Mali-G710 MP7"),

    "Pixel 7": ("Google Tensor G2", "Mali-G710 MP7"),

    "Pixel 6a": ("Google Tensor", "Mali-G78 MP20"),

    "Pixel 6": ("Google Tensor", "Mali-G78 MP20"),



    # OnePlus & Realme & Oppo & Vivo & Sony

    "CPH2581": ("Qualcomm Snapdragon 8 Gen 3", "Adreno (TM) 750"),

    "CPH2609": ("Qualcomm Snapdragon 8 Gen 2", "Adreno (TM) 740"),

    "CPH2449": ("Qualcomm Snapdragon 8 Gen 2", "Adreno (TM) 740"),

    "CPH2493": ("MediaTek Dimensity 9000", "Mali-G710 MC10"),

    "CPH2569": ("Qualcomm Snapdragon 782G", "Adreno (TM) 642L"),

    "CPH2551": ("Qualcomm Snapdragon 8 Gen 2", "Adreno (TM) 740"),

    "RMX3840": ("Qualcomm Snapdragon 7s Gen 2", "Adreno (TM) 710"),

    "RMX3867": ("MediaTek Dimensity 7050", "Mali-G68 MC4"),

    "RMX3740": ("MediaTek Dimensity 7050", "Mali-G68 MC4"),

    "RMX3780": ("MediaTek Dimensity 6020", "Mali-G57 MC2"),

    "RMX3630": ("MediaTek Helio G99", "Mali-G57 MC2"),

    "RMX3890": ("Qualcomm Snapdragon 685", "Adreno (TM) 610"),

    "RMX3710": ("MediaTek Helio G88", "Mali-G52 MC2"),

    "RMX3888": ("Qualcomm Snapdragon 8 Gen 3", "Adreno (TM) 750"),

    "PHY110": ("Qualcomm Snapdragon 8 Gen 3", "Adreno (TM) 750"),

    "V2359A": ("Qualcomm Snapdragon 8 Gen 3", "Adreno (TM) 750"),

    "V2318": ("Qualcomm Snapdragon 7 Gen 3", "Adreno (TM) 720"),

    "V2339": ("Qualcomm Snapdragon 6 Gen 1", "Adreno (TM) 710"),

    "V2250": ("Qualcomm Snapdragon 778G", "Adreno (TM) 642L"),

    "V2246": ("MediaTek Dimensity 7200", "Mali-G610 MC4"),

    "V2247": ("Qualcomm Snapdragon 680", "Adreno (TM) 610"),

    "V2249": ("MediaTek Helio G85", "Mali-G52 MC2"),

    "XQ-DQ72": ("Qualcomm Snapdragon 8 Gen 2", "Adreno (TM) 740"),

    "XQ-DE72": ("Qualcomm Snapdragon 8 Gen 2", "Adreno (TM) 740"),

    "ASUS_AI2401": ("Qualcomm Snapdragon 8 Gen 3", "Adreno (TM) 750"),

    "XT2403-2": ("Qualcomm Snapdragon 7 Gen 3", "Adreno (TM) 720"),

    # Additional POCO & Oppo & Vivo models

    "23049PCD8G": ("Qualcomm Snapdragon 7+ Gen 2", "Adreno (TM) 725"),

    "2311DRK48G": ("MediaTek Dimensity 8300 Ultra", "Mali-G615 MC6"),

    "23122PCD1G": ("Qualcomm Snapdragon 7s Gen 2", "Adreno (TM) 710"),

    "22101320G": ("Qualcomm Snapdragon 778G", "Adreno (TM) 642L"),

    "2312FPCA6G": ("MediaTek Helio G99-Ultra", "Mali-G57 MC2"),

    "PGEM10": ("Qualcomm Snapdragon 8 Gen 2", "Adreno (TM) 740"),

    "CPH2305": ("Qualcomm Snapdragon 8 Gen 1", "Adreno (TM) 730"),

    "CPH2607": ("MediaTek Dimensity 8200", "Mali-G610 MC6"),

    "CPH2599": ("MediaTek Dimensity 7050", "Mali-G68 MC4"),

    "CPH2525": ("Qualcomm Snapdragon 778G", "Adreno (TM) 642L"),

    "CPH2531": ("MediaTek Dimensity 7050", "Mali-G68 MC4"),

    "CPH2359": ("MediaTek Dimensity 1300", "Mali-G77 MC9"),

    "CPH2557": ("MediaTek Dimensity 6020", "Mali-G57 MC2"),

    "CPH2565": ("MediaTek Dimensity 700", "Mali-G57 MC2"),

    "CPH2577": ("MediaTek Helio G85", "Mali-G52 MC2"),

    "V2324A": ("MediaTek Dimensity 9300", "Immortalis-G720 MC12"),



}





ACCEPT_LANGUAGE_VARIANTS = [

    "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",

    "vi-VN,vi;q=0.9,en-US;q=0.7,en;q=0.6",

    "vi-VN,vi;q=0.8,en-US;q=0.9,en;q=0.7",

    "vi,en-US;q=0.9,en;q=0.8",

    "vi-VN,vi;q=0.95,en-US;q=0.85,en;q=0.75",

]





def generate_dynamic_grease_brands(chrome_maj: str, is_webview: bool = False) -> str:

    """Sinh chuỗi Sec-CH-UA với thương hiệu GREASE biến thiên ngẫu nhiên theo chuẩn Chromium / Android."""

    grease_names = [

        "Not-A.Brand", "Not_A Brand", "Not=A?Brand", "Not/A)Brand", "Not A;Brand"

    ]

    grease_versions = ["8", "24", "99", "99.0.0.0"]

    name = random.choice(grease_names)

    ver = random.choice(grease_versions)



    if is_webview:

        items = [

            f'"{name}";v="{ver}"',

            f'"Chromium";v="{chrome_maj}"',

            f'"Android WebView";v="{chrome_maj}"'

        ]

    else:

        items = [

            f'"{name}";v="{ver}"',

            f'"Chromium";v="{chrome_maj}"',

            f'"Google Chrome";v="{chrome_maj}"'

        ]

    random.shuffle(items)

    return ", ".join(items)





def build_supports_fresco_ua(
    brand: str,
    model_code: str,
    os_ver: str,
    chrome_maj: str,
    full_chrome_ver: str,
    build_tag: str,
    dpr: float = 2.0,
    carrier: str = "",
    locale: str = "vi_VN",
    fb_ver: str = "",
    fb_bld: str = "",
) -> str:
    """Sinh User-Agent Chrome Mobile dien thoai that chuan cho m.facebook.com."""
    return (
        f"Mozilla/5.0 (Linux; Android {os_ver}; {model_code} Build/{build_tag}) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{full_chrome_ver} Mobile Safari/537.36"
    )


def build_dynamic_android_profile(raw_entry: tuple, geo_profile: Optional[Any] = None) -> DeviceProfile:

    brand, model_name, model_code, os_ver, chrome_maj, vp_w, vp_h, dpr, tls_preset = raw_entry

    # Enforce strict TLS JA4 and User-Agent version alignment to prevent Checkpoint 282
    tls_preset = "chrome131_android"
    chrome_maj = "131"

    sub = random.choice(CHROME_SUBVERSIONS.get(chrome_maj, ["6367.179"]))

    full_chrome_ver = f"{chrome_maj}.0.{sub}"

    build_tag = random.choice(ANDROID_BUILD_TAGS)

    fb_ver, fb_bld = random.choice(KATANA_RELEASES)



    # Dong bo hoa carrier & thong so vien thong theo vi tri dia ly truoc khi tao User-Agent

    if geo_profile:

        carrier = geo_profile.carrier_name

        country_code = geo_profile.country_code

        mcc = geo_profile.mcc

        mnc = geo_profile.mnc

        sim_country_iso = geo_profile.sim_country_iso

        locale = geo_profile.locale

        accept_lang = geo_profile.accept_language

        timezone = geo_profile.timezone

        tz_offset = geo_profile.timezone_offset_minutes

    else:

        carrier = random.choice(CARRIERS)

        country_code = "VN"

        mcc = "452"

        mnc = "04"

        sim_country_iso = "vn"

        locale = "vi_VN"

        accept_lang = random.choice(ACCEPT_LANGUAGE_VARIANTS)

        timezone = "Asia/Ho_Chi_Minh"

        tz_offset = 420



    # Chuan hoa User-Agent SupportsFresco / Chrome Mobile dien thoai that (ApiChromeOldMfb)

    fb_ua = build_supports_fresco_ua(

        brand=brand,

        model_code=model_code,

        os_ver=os_ver,

        chrome_maj=chrome_maj,

        full_chrome_ver=full_chrome_ver,

        build_tag=build_tag,

        dpr=dpr,

        carrier=carrier,

        locale=locale,

        fb_ver=fb_ver,

        fb_bld=fb_bld,

    )

    sec_ch = generate_dynamic_grease_brands(chrome_maj, is_webview=False)



    # Tính nhất quán phần cứng 100% giữa Dòng máy, Vi xử lý (SoC) và GPU Renderer

    hw_spec = MODEL_HARDWARE_SPECS.get(model_code)

    if hw_spec:

        soc, gl = hw_spec

    elif geo_profile and getattr(geo_profile, "soc_preference", None):

        soc = geo_profile.soc_preference

        gl = geo_profile.gl_renderer_preference

    else:

        soc = "Qualcomm Snapdragon 8 Gen 2"

        gl = "Adreno (TM) 740"



    return DeviceProfile(

        name=f"{brand} {model_name}",

        brand=brand,

        model=model_code,

        os_name="Android",

        os_version=os_ver,

        chrome_major=chrome_maj,

        viewport_width=vp_w,

        viewport_height=vp_h,

        pixel_ratio=dpr,

        impersonate=tls_preset,

        user_agent=fb_ua,

        sec_ch_ua=sec_ch,

        sec_ch_ua_mobile="?1",

        sec_ch_ua_platform='"Android"',

        sec_ch_ua_platform_version=f'"{os_ver}.0.0"',

        sec_ch_ua_model=f'"{model_code}"',

        sec_ch_dpr=str(dpr),

        sec_ch_viewport_width=str(vp_w),

        sec_ch_prefers_color_scheme=random.choice(['"light"', '"light"', '"dark"']),

        sec_ch_ua_arch='"arm"',

        sec_ch_ua_bitness='"64"',

        screen_width=int(vp_w * dpr),

        screen_height=int(vp_h * dpr),

        carrier=carrier,

        country_code=country_code,

        mcc=mcc,

        mnc=mnc,

        sim_country_iso=sim_country_iso,

        locale=locale,

        accept_language=accept_lang,

        timezone=timezone,

        timezone_offset_minutes=tz_offset,

        soc_chipset=soc,

        gl_renderer=gl,

        is_fb_app=False,

        supports_fresco=False,

        fb_version=fb_ver,

        fb_build=fb_bld,

    )





IOS_PROFILES_TEMPLATES = [

    ("iPhone 15 Pro Max", "iPhone16,2", "17.4", 430, 932, 3.0, "safari17_2_ios"),

    ("iPhone 14 Pro", "iPhone15,2", "16.6", 393, 852, 3.0, "safari17_2_ios"),

    ("iPhone 13", "iPhone14,5", "16.5", 390, 844, 3.0, "safari17_2_ios"),

    ("iPhone 12", "iPhone13,2", "16.4", 390, 844, 3.0, "safari17_2_ios"),

]





def build_dynamic_ios_profile(tmpl: tuple, geo_profile: Optional[Any] = None) -> DeviceProfile:

    name, model_code, ios_ver, vp_w, vp_h, dpr, tls = tmpl

    ver_underscore = ios_ver.replace(".", "_")

    ua = f"Mozilla/5.0 (iPhone; CPU iPhone OS {ver_underscore} like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{ios_ver} Mobile/15E148 Safari/604.1"

    

    if geo_profile:

        carrier = geo_profile.carrier_name

        country_code = geo_profile.country_code

        locale = geo_profile.locale

        accept_lang = geo_profile.accept_language

        timezone = geo_profile.timezone

        tz_offset = geo_profile.timezone_offset_minutes

    else:

        carrier = random.choice(CARRIERS)

        country_code = "VN"

        locale = "vi_VN"

        accept_lang = random.choice(ACCEPT_LANGUAGE_VARIANTS)

        timezone = "Asia/Ho_Chi_Minh"

        tz_offset = 420



    return DeviceProfile(

        name=name,

        brand="Apple",

        model=model_code,

        os_name="iOS",

        os_version=ios_ver,

        chrome_major="",

        viewport_width=vp_w,

        viewport_height=vp_h,

        pixel_ratio=dpr,

        impersonate=tls,

        user_agent=ua,

        sec_ch_ua="",

        sec_ch_ua_mobile="",

        sec_ch_ua_platform="",

        sec_ch_ua_platform_version="",

        sec_ch_ua_model="",

        screen_width=int(vp_w * dpr),

        screen_height=int(vp_h * dpr),

        carrier=carrier,

        country_code=country_code,

        locale=locale,

        accept_language=accept_lang,

        timezone=timezone,

        timezone_offset_minutes=tz_offset,

    )









KAIOS_MODELS = [

    ("Nokia", "Nokia 8110 4G", "2.5"),

    ("Nokia", "Nokia 2720 Flip", "2.5.2"),

    ("Nokia", "Nokia 800 Tough", "2.5.1"),

    ("Nokia", "Nokia 6300 4G", "2.5.4"),

    ("Nokia", "Nokia 2780 Flip", "3.0"),

    ("Alcatel", "Go Flip 3", "2.5"),

    ("Jio", "JioPhone 2", "2.5"),

    ("Energizer", "E241s", "2.5.1"),

]





def build_dynamic_kaios_profile(geo_profile=None):

    brand, model_name, kai_ver = random.choice(KAIOS_MODELS)

    rv_ver = "84.0" if kai_ver.startswith("3") else "48.0"

    ua = f"Mozilla/5.0 (Mobile; {model_name}; Android; rv:{rv_ver}) Gecko/{rv_ver} Firefox/{rv_ver} KAIOS/{kai_ver}"

    carrier = geo_profile.carrier_name if geo_profile else random.choice(CARRIERS)

    country_code = geo_profile.country_code if geo_profile else "VN"

    locale = geo_profile.locale if geo_profile else "vi_VN"

    accept_lang = geo_profile.accept_language if geo_profile else "vi-VN,vi;q=0.9,en-US;q=0.8"

    timezone = geo_profile.timezone if geo_profile else "Asia/Ho_Chi_Minh"

    return DeviceProfile(

        name=f"{brand} {model_name} (KaiOS)",

        brand=brand,

        model=model_name,

        os_name="KaiOS",

        os_version=kai_ver,

        chrome_major="",

        viewport_width=240,

        viewport_height=320,

        pixel_ratio=1.0,

        impersonate="firefox133",

        user_agent=ua,

        sec_ch_ua="",

        sec_ch_ua_mobile="",

        sec_ch_ua_platform="",

        sec_ch_ua_platform_version="",

        sec_ch_ua_model="",

        screen_width=240,

        screen_height=320,

        carrier=carrier,

        country_code=country_code,

        locale=locale,

        accept_language=accept_lang,

        timezone=timezone,

    )





WINDOWS_PHONE_MODELS = [

    "Lumia 520", "Lumia 525", "Lumia 530", "Lumia 535", "Lumia 630",

    "Lumia 635", "Lumia 640", "Lumia 720", "Lumia 730", "Lumia 820",

    "Lumia 830", "Lumia 920", "Lumia 925", "Lumia 930", "Lumia 950"

]





def build_dynamic_windows_phone_profile(geo_profile=None):

    model_name = random.choice(WINDOWS_PHONE_MODELS)

    ua = f"Mozilla/5.0 (Mobile; Windows Phone 8.1; Android 4.0; ARM; Trident/7.0; Touch; rv:11.0; IEMobile/11.0; NOKIA; {model_name}) like iPhone OS 7_0_3 Mac OS X AppleWebKit/537 (KHTML, like Gecko) Mobile Safari/537"

    carrier = geo_profile.carrier_name if geo_profile else random.choice(CARRIERS)

    country_code = geo_profile.country_code if geo_profile else "VN"

    locale = geo_profile.locale if geo_profile else "vi_VN"

    accept_lang = geo_profile.accept_language if geo_profile else "vi-VN,vi;q=0.9,en-US;q=0.8"

    timezone = geo_profile.timezone if geo_profile else "Asia/Ho_Chi_Minh"

    return DeviceProfile(

        name=f"Nokia {model_name} (Windows Phone)",

        brand="Nokia",

        model=model_name,

        os_name="Windows Phone",

        os_version="8.1",

        chrome_major="",

        viewport_width=360,

        viewport_height=640,

        pixel_ratio=1.5,

        impersonate="edge101",

        user_agent=ua,

        sec_ch_ua="",

        sec_ch_ua_mobile="",

        sec_ch_ua_platform="",

        sec_ch_ua_platform_version="",

        sec_ch_ua_model="",

        screen_width=360,

        screen_height=640,

        carrier=carrier,

        country_code=country_code,

        locale=locale,

        accept_language=accept_lang,

        timezone=timezone,

    )





BLACKBERRY_VERSIONS = ["10.3.1.2708", "10.3.2.2836", "10.3.2.2876", "10.3.3.2205", "10.3.3.3216"]





def build_dynamic_blackberry_profile(geo_profile=None):

    bb_ver = random.choice(BLACKBERRY_VERSIONS)

    ua = f"Mozilla/5.0 (BB10; Touch) AppleWebKit/537.35+ (KHTML, like Gecko) Version/{bb_ver} Mobile Safari/537.35+"

    carrier = geo_profile.carrier_name if geo_profile else random.choice(CARRIERS)

    country_code = geo_profile.country_code if geo_profile else "VN"

    locale = geo_profile.locale if geo_profile else "vi_VN"

    accept_lang = geo_profile.accept_language if geo_profile else "vi-VN,vi;q=0.9,en-US;q=0.8"

    timezone = geo_profile.timezone if geo_profile else "Asia/Ho_Chi_Minh"

    return DeviceProfile(

        name="BlackBerry Z10 (BB10)",

        brand="BlackBerry",

        model="Z10",

        os_name="BB10",

        os_version=bb_ver,

        chrome_major="",

        viewport_width=360,

        viewport_height=640,

        pixel_ratio=1.5,

        impersonate="safari17_0",

        user_agent=ua,

        sec_ch_ua="",

        sec_ch_ua_mobile="",

        sec_ch_ua_platform="",

        sec_ch_ua_platform_version="",

        sec_ch_ua_model="",

        screen_width=360,

        screen_height=640,

        carrier=carrier,

        country_code=country_code,

        locale=locale,

        accept_language=accept_lang,

        timezone=timezone,

    )





def get_random_device_profile(device_type: str = "Android", geo_profile: Optional[Any] = None) -> DeviceProfile:

    """Sinh ngẫu nhiên một hồ sơ thiết bị di động thật chuẩn xác với độ biến thiên cao."""

    dtype = (device_type or "Android").lower()

    if dtype in ("desktop", "chrome", "pc"):

        sub = random.choice(CHROME_SUBVERSIONS["124"])

        ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.{sub} Safari/537.36"

        sec_ch = generate_dynamic_grease_brands("124", is_webview=False)

        carrier = geo_profile.carrier_name if geo_profile else "VNPT"

        country_code = geo_profile.country_code if geo_profile else "VN"

        locale = geo_profile.locale if geo_profile else "vi_VN"

        accept_lang = geo_profile.accept_language if geo_profile else "vi-VN,vi;q=0.9,en-US;q=0.8"

        timezone = geo_profile.timezone if geo_profile else "Asia/Ho_Chi_Minh"

        return DeviceProfile(

            name="Windows Desktop",

            brand="PC",

            model="Windows",

            os_name="Windows",

            os_version="10.0",

            chrome_major="124",

            viewport_width=1920,

            viewport_height=1080,

            pixel_ratio=1.0,

            impersonate="chrome124",

            user_agent=ua,

            sec_ch_ua=sec_ch,

            sec_ch_ua_mobile="?0",

            sec_ch_ua_platform='"Windows"',

            sec_ch_ua_platform_version='"15.0.0"',

            sec_ch_ua_model='""',

            screen_width=1920,

            screen_height=1080,

            carrier=carrier,

            country_code=country_code,

            locale=locale,

            accept_language=accept_lang,

            timezone=timezone,

        )

    elif dtype in ("iphone", "ios", "iphoneapp", "safari"):

        return build_dynamic_ios_profile(random.choice(IOS_PROFILES_TEMPLATES), geo_profile=geo_profile)

    elif dtype in ("legacy", "classic", "kaios", "featurephone", "nokia", "windowsphone", "wp", "lumia", "blackberry", "bb", "bb10"):
        # Bảo vệ chống Checkpoint 282: Tuyệt đối không sinh thiết bị lỗi thời (BlackBerry 2013, Windows Phone, KaiOS)
        # Tự động đồng bộ sang hồ sơ smartphone Android / iOS hiện đại đạt chuẩn Meta Trust
        return build_dynamic_android_profile(random.choice(RAW_ANDROID_MODELS), geo_profile=geo_profile)

    elif any(k in dtype for k in ("mr_sxr", "mr.sxr", "sxr", "katana", "fb4a", "fb_app", "facebook_app", "android_katana")):

        from core.fb_user_agent_maker import make_device_profile

        return make_device_profile(is_fb_app=False, geo_profile=geo_profile)

    elif dtype in ("random", "all"):

        choice_fn = random.choice(["android", "ios"])

        return get_random_device_profile(choice_fn, geo_profile=geo_profile)

    else:

        return build_dynamic_android_profile(random.choice(RAW_ANDROID_MODELS), geo_profile=geo_profile)


def setup_session_cookies(
    session: Any,
    device_type: str = "Android",
    profile: Optional[DeviceProfile] = None
) -> None:
    """
    Pre-seed cookies màn hình khớp 100% Mr-SxR gốc (setup_session_cookies).
    Chỉ thiết lập cho Android/AndroidApp: m_pixel_ratio=1 và wd (screen resolution).
    Tuyệt đối không pre-seed ps_l, ps_n, dpr trước khi Meta phản hồi để tránh bị WAF nhận diện bot.
    """
    base_type = device_type.split("_")[0] if "_" in str(device_type) else str(device_type)
    if base_type not in ("Android", "AndroidApp"):
        return

    import random
    prof = profile or get_random_device_profile(device_type)
    if hasattr(prof, 'impersonate'):
        prof.impersonate = sanitize_impersonate(prof.impersonate)

    screen_res = f"{prof.viewport_width}x{prof.viewport_height}" if prof else random.choice(["320x480", "480x800", "540x960", "800x480", "854x480", "960x540", "720x1280", "1280x720", "1080x1920"])

    from core.http_client import HttpClient
    if isinstance(session, HttpClient):
        for dom in (".facebook.com", "m.facebook.com"):
            session.set_cookie("wd", screen_res, domain=dom)
            session.set_cookie("m_pixel_ratio", "1", domain=dom)
    elif hasattr(session, "cookies"):
        if hasattr(session.cookies, "set"):
            for dom in (".facebook.com", "m.facebook.com"):
                session.cookies.set("wd", screen_res, domain=dom)
                session.cookies.set("m_pixel_ratio", "1", domain=dom)
        elif hasattr(session.cookies, "update"):
            session.cookies.update({"wd": screen_res, "m_pixel_ratio": "1"})

def build_request_context(

    device_type: str = "Android",

    browser_type: str = "Default",

    locale: str = "vi_VN",

    profile: Optional[DeviceProfile] = None,

    geo_profile: Optional[Any] = None,

) -> Dict[str, Any]:

    """Xây dựng ngữ cảnh header đầy đủ, biến thiên ngẫu nhiên tự nhiên và khớp vị trí địa lý."""

    prof = profile or get_random_device_profile(device_type, geo_profile=geo_profile)

    ua = prof.user_agent



    # Uu tien Accept-Language dong bo theo quoc gia cua profile

    if prof.accept_language:

        accept_lang = prof.accept_language

    elif "vi" in (locale or "").lower():

        accept_lang = random.choice(ACCEPT_LANGUAGE_VARIANTS)

    else:

        accept_lang = f"{locale},en-US;q=0.9,en;q=0.8"



    headers: Dict[str, str] = {

        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",

        "accept-language": accept_lang,

        "sec-fetch-dest": "document",

        "sec-fetch-mode": "navigate",

        "sec-fetch-site": "none",

        "sec-fetch-user": "?1",

        "upgrade-insecure-requests": "1",

        "user-agent": ua,

        "priority": "u=0, i",

    }



    # Headers chuan Web Browser (khong chen fake Katana/HNI de tranh Checkpoint 282)
    # Chuan W3C Chromium Low-Entropy Client Hints: chi gui sec-ch-ua, mobile, platform
    if prof.sec_ch_ua:
        headers["sec-ch-ua"] = prof.sec_ch_ua
        headers["sec-ch-ua-mobile"] = prof.sec_ch_ua_mobile
        headers["sec-ch-ua-platform"] = prof.sec_ch_ua_platform



    from core.email_service import is_chromium_ua, clean_client_hints
    if not is_chromium_ua(ua) or getattr(prof, "os_name", "") in ("iOS", "KaiOS", "BB10", "Windows Phone"):
        clean_client_hints(headers, ua)

    return {

        "ua": ua,

        "base_headers": headers,

        "device_type": device_type,

        "locale": prof.locale or locale,

        "profile": prof,

    }





VALID_IMPERSONATE_PRESETS = {
    'chrome99', 'chrome100', 'chrome101', 'chrome104', 'chrome107', 'chrome110',
    'chrome116', 'chrome119', 'chrome120', 'chrome123', 'chrome124', 'chrome131',
    'chrome133a', 'chrome136', 'chrome142', 'chrome99_android', 'chrome131_android',
    'edge99', 'edge101', 'safari15_3', 'safari15_5', 'safari17_0', 'safari17_2_ios',
    'safari18_0', 'safari18_0_ios', 'firefox133', 'firefox135', 'firefox144',
}

def sanitize_impersonate(imp: Optional[str]) -> str:
    if not imp:
        return "chrome131_android"
    s = str(imp).strip().lower()
    if s in VALID_IMPERSONATE_PRESETS:
        return s
    if "android" in s:
        return "chrome131_android"
    if "ios" in s or "iphone" in s:
        return "safari17_2_ios"
    if "safari" in s:
        return "safari17_0"
    if "firefox" in s:
        return "firefox133"
    if "edge" in s:
        return "edge101"
    return "chrome131_android"

def create_http_session(

    device_type: str = "Android",

    proxy_dict: Optional[Union[Dict[str, str], str, ProxyItem]] = None,

    profile: Optional[DeviceProfile] = None,

    verify: bool = False,

) -> requests.Session:

    """Tạo session curl_cffi với TLS impersonation khớp hồ sơ thiết bị và tự động bypass SSL verification."""

    prof = profile or get_random_device_profile(device_type)

    impersonate = getattr(prof, "impersonate", None)
    if impersonate == "safari16_0":
        impersonate = "safari17_0"

    try:

        if impersonate:

            session = requests.Session(impersonate=impersonate, verify=verify)

        else:

            session = requests.Session(verify=verify)

    except Exception:

        try:

            if impersonate:

                session = requests.Session(impersonate=impersonate)

            else:

                session = requests.Session()

            session.verify = verify

        except Exception:

            session = requests.Session()

            session.verify = verify



    if proxy_dict:

        if isinstance(proxy_dict, ProxyItem):

            url = proxy_dict.as_url()

            session.proxies = {"http": url, "https": url}

        elif isinstance(proxy_dict, dict):

            session.proxies.update(proxy_dict)

        elif isinstance(proxy_dict, str):

            session.proxies = {"http": proxy_dict, "https": proxy_dict}



    return session

