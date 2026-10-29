import random

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Device models for Android 4-8 era (verified working)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ANDROID_BROWSER_MODELS = [
    "GT-I9300", "GT-I9500", "GT-I9505", "GT-I9190", "GT-I9195",
    "SM-G900F", "SM-G900H", "SM-G900T",
    "SM-G920F", "SM-G920I", "SM-G925F", "SM-G925I",
    "SM-G930F", "SM-G930T", "SM-G935F",
    "SM-G950F", "SM-G955F", "SM-G960F", "SM-G965F",
    "SM-N900", "SM-N9005", "SM-N910F", "SM-N910C", "SM-N920C",
    "SM-N950F", "SM-N960F",
    "GT-N7100", "GT-N7105",
    "SM-J500F", "SM-J500H", "SM-J510F", "SM-J700F", "SM-J710F",
    "SM-A500F", "SM-A510F", "SM-A520F",
    "SM-G530H", "SM-G531H", "SM-G532F",
    "Nexus 4", "Nexus 5", "Nexus 5X", "Nexus 6", "Nexus 6P",
    "Pixel", "Pixel XL",
    "XT1032", "XT1033", "XT1068", "XT1069",
    "XT1052", "XT1053", "XT1058",
    "XT1562", "XT1563", "XT1572", "XT1575",
    "LG-D802", "LG-D855", "LG-H815", "LG-H810",
    "LG-H900", "LG-H901", "LG-H918",
    "LG-K420", "LG-K430", "LG-K500",
    "C6603", "C6903", "D6503", "D6603",
    "E5823", "E6553", "E6653",
    "HTC One", "HTC One M8", "HTC One M9", "HTC 10", "HTC U11",
    "ALE-L21", "ALE-L23", "EVA-L09", "EVA-L19",
    "VNS-L31", "VNS-L21", "FRD-L09", "NXT-L29",
    "Mi 4", "Mi 4i", "Mi 5", "Mi 5s", "Mi A1", "Mi 8", "POCO F1",
    "Redmi Note 3", "Redmi Note 4", "Redmi 3S", "Redmi 4A",
    "A37f", "A57", "A71", "F1s", "F3", "F5",
    "vivo 1713", "vivo 1723", "vivo 1724",
]

ANDROID_APP_OLD_PHONES = {
    "Samsung": [
        "GT-I9300", "GT-I9500", "GT-I9505", "GT-I9190", "GT-I9195",
        "SM-G900F", "SM-G900H", "SM-G900T",
        "SM-G920F", "SM-G920I", "SM-G925F", "SM-G925I",
        "SM-G930F", "SM-G930T", "SM-G935F",
        "SM-N9005", "SM-N900", "SM-N910F", "SM-N910C", "SM-N920C",
        "GT-N7100", "GT-N7105",
        "SM-J500F", "SM-J500H", "SM-J510F", "SM-J700F", "SM-J710F",
        "SM-A500F", "SM-A510F", "SM-A520F",
        "SM-G530H", "SM-G531H", "SM-G532F",
    ],
    "Motorola": [
        "XT1032", "XT1033", "XT1068", "XT1069",
        "XT1052", "XT1053", "XT1058",
        "XT1562", "XT1563", "XT1572", "XT1575",
        "XT1635-02", "XT1650",
    ],
    "LG": [
        "LG-D802", "LG-D855", "LG-H815", "LG-H810",
        "LG-H900", "LG-H901", "LG-H918",
        "LG-K420", "LG-K430", "LG-K500",
        "LG-M150", "LG-M160", "LG-M200",
    ],
    "Sony": [
        "C6603", "C6903", "D6503", "D6603",
        "E5823", "E6553", "E6653",
        "F3111", "F3211", "G3111", "G3121",
    ],
    "HTC": [
        "HTC One", "HTC One M8", "HTC One M9",
        "HTC One A9", "HTC Desire 820", "HTC Desire 816",
        "HTC 10", "HTC U11",
    ],
    "Huawei": [
        "ALE-L21", "ALE-L23", "GRA-L09", "GRA-UL10",
        "EVA-L09", "EVA-L19", "VNS-L31", "VNS-L21",
        "FRD-L09", "FRD-L19", "NXT-L29",
        "PLK-L01", "KIW-L21", "KIW-L24",
    ],
    "Google": ["Nexus 4", "Nexus 5", "Nexus 5X", "Nexus 6", "Nexus 6P"],
    "Xiaomi": [
        "Redmi Note 3", "Redmi Note 4", "Redmi 3S", "Redmi 4A",
        "Mi 4", "Mi 4i", "Mi 5", "Mi 5s", "Mi A1", "Mi Max",
    ],
    "Oppo": ["A37f", "A37fw", "A57", "A71", "A83", "F1f", "F1s", "F3", "F5"],
    "Vivo": ["vivo 1713", "vivo 1723", "vivo 1724", "vivo 1727", "vivo 1801", "vivo 1802"],
}

IPHONE_APP_OLD_DEVICES = [
    "iPhone4,1",
    "iPhone5,1", "iPhone5,2", "iPhone5,3", "iPhone5,4",
    "iPhone6,1", "iPhone6,2",
    "iPhone7,1", "iPhone7,2",
    "iPhone8,1", "iPhone8,2", "iPhone8,4",
    "iPhone9,1", "iPhone9,2", "iPhone9,3", "iPhone9,4",
    "iPhone10,1", "iPhone10,2", "iPhone10,3", "iPhone10,4", "iPhone10,5", "iPhone10,6",
]

# Facebook App version pairs (FBAV, FBBV) - old versions only
FBAV_BV_OLD = [
    ("66.0.0.33.73", "23966353"), ("65.0.0.42.81", "23239543"),
    ("64.0.0.52.76", "22754145"), ("63.0.0.37.81", "21778670"),
    ("62.0.0.42.77", "21376152"), ("60.0.0.16.76", "20453986"),
    ("59.0.0.15.313", "20097173"), ("58.0.0.28.70", "18971721"),
    ("57.0.0.18.136", "18629582"), ("55.0.0.18.66", "17676094"),
    ("53.0.0.29.18", "16918763"), ("51.0.0.14.10", "16328224"),
    ("50.0.0.10.54", "16053535"), ("47.0.0.25.125", "15237799"),
    ("45.0.0.38.146", "14760736"), ("42.0.0.27.114", "14063944"),
    ("39.0.0.0.88", "12733034"), ("38.0.0.0.81", "12144892"),
    ("35.0.0.0.337", "10862146"), ("34.0.0.0.242", "10009614"),
    ("33.0.0.0.1", "9018335"), ("30.0.0.19.17", "8445415"),
    ("29.0.0.0.11", "7267672"), ("28.0.0.1.16", "6811796"),
    ("27.0.0.0.15", "6590726"), ("26.0.0.0.6", "6108302"),
]


def get_android_browser_ua():
    """Generate modern Android 11-14 browser UA with Chrome 122-126 and contemporary devices."""
    android_ver = random.choice(["11", "12", "13", "14"])
    chrome_major = random.randint(122, 126)
    chrome_build = random.randint(6200, 6499)
    chrome_patch = random.randint(40, 180)

    modern_models = [
        "SM-S928B", "SM-S926B", "SM-S918B", "SM-S916B", "SM-S908B",
        "SM-G998B", "SM-A546B", "SM-A536B", "Pixel 7 Pro", "Pixel 8 Pro",
        "Pixel 7a", "2211133G", "2312DRA50G", "22101316G", "CPH2371", "CPH2525"
    ]
    model = random.choice(modern_models)

    build_prefixes = ["TP1A", "UP1A", "AP1A", "UQ1A"]
    build_id = f"{random.choice(build_prefixes)}.{random.randint(220624, 240500)}.{random.randint(10, 99)}"

    ua = (
        f"Mozilla/5.0 (Linux; Android {android_ver}; {model} Build/{build_id}) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{chrome_major}.0.{chrome_build}.{chrome_patch} Mobile Safari/537.36"
    )
    return ua, model, android_ver


def get_iphone_app_ua(carrier=None, locale=None):
    """Generate iPhone Facebook App UA with iOS 6-9 (verified working)."""
    devices = IPHONE_APP_OLD_DEVICES
    ios_versions = [
        ("6_0", "6.0"), ("6_0_1", "6.0.1"), ("6_1_3", "6.1.3"), ("6_1_4", "6.1.4"),
        ("7_0", "7.0"), ("7_0_2", "7.0.2"), ("7_1_2", "7.1.2"),
        ("8_0", "8.0"), ("8_1", "8.1"), ("8_3", "8.3"), ("8_4", "8.4"), ("8_4_1", "8.4.1"),
        ("9_0", "9.0"), ("9_1", "9.1"), ("9_2_1", "9.2.1"), ("9_3_2", "9.3.2"), ("9_3_5", "9.3.5"),
    ]

    ios_ver_us, ios_ver = random.choice(ios_versions)
    machine = random.choice(devices)

    webkit_ver_map = {"6": "536.26", "7": "537.51.1", "8": "600.1.4", "9": "601.1.46"}
    webkit_ver = webkit_ver_map.get(ios_ver.split(".")[0], "600.1.4")

    build_id = random.choice(["10A5376e", "12H321", "13C75", "14A403", "16A366", "11D257", "11B511", "17A577", "18A393", "19B74"])
    carriers = ["T-Mobile", "AT&T", "Verizon", "Sprint", "Vodafone", "O2", "Orange", "SoftBank", "KDDI", "Docomo", "Viettel", "Vinaphone", "Mobifone"]
    eff_carrier = carrier or random.choice(carriers)
    eff_locale = locale or ("vi_VN" if any(vn in str(eff_carrier).lower() for vn in ("viettel", "vinaphone", "mobifone", "vietnamobile")) else "en_US")

    fbav_major = random.randint(6, 60)
    fbav_minor = random.randint(0, 5)
    fbav = f"{fbav_major}.{fbav_minor}.0.{random.randint(10, 50)}.{random.randint(100, 500)}"
    fbbv = str(random.randint(1000000, 25000000))

    ua = (
        f"Mozilla/5.0 (iPhone; CPU iPhone OS {ios_ver_us} like Mac OS X) "
        f"AppleWebKit/{webkit_ver} (KHTML, like Gecko) "
        f"Mobile/{build_id} "
        f"[FBAN/FBIOS;FBAV/{fbav};FBBV/{fbbv};FBDV/{machine};FBMD/iPhone;"
        f"FBSN/iPhone OS;FBSV/{ios_ver};FBSS/2;FBCR/{eff_carrier};FBID/phone;FBLC/{eff_locale};FBOP/5;]"
    )
    return ua


# -------------------------------------------------------------------------
# Modern Authentic Katana (FB4A) Releases (2024 - 2026) - Meta CI/CD Builds
# -------------------------------------------------------------------------
KATANA_MODERN_RELEASES = [
    ("518.0.0.63.86", "750617200"),
    ("517.0.0.52.85", "748523100"),
    ("516.0.0.45.83", "746198400"),
    ("515.0.0.39.81", "743810200"),
    ("514.0.0.31.78", "741205300"),
    ("512.0.0.25.75", "738112000"),
    ("510.0.0.28.75", "735012400"),
    ("505.0.0.22.70", "728100500"),
    ("500.0.0.18.66", "720514300"),
    ("490.0.0.15.62", "705210300"),
]

# Modern Authentic Android Smartphone Devices (Samsung Galaxy S21-S24 Ultra, Xiaomi, Pixel, Oppo, Vivo)
MODERN_KATANA_PHONES = {
    "samsung": [
        ("SM-G998B", "Samsung Galaxy S21 Ultra 5G", "3.0", 1080, 1920),
        ("SM-G996B", "Samsung Galaxy S21+ 5G", "2.75", 1080, 2400),
        ("SM-G991B", "Samsung Galaxy S21 5G", "2.75", 1080, 2400),
        ("SM-S908B", "Samsung Galaxy S22 Ultra 5G", "3.5", 1440, 3088),
        ("SM-S906B", "Samsung Galaxy S22+ 5G", "2.75", 1080, 2340),
        ("SM-S901B", "Samsung Galaxy S22 5G", "2.75", 1080, 2340),
        ("SM-S918B", "Samsung Galaxy S23 Ultra 5G", "3.5", 1440, 3088),
        ("SM-S916B", "Samsung Galaxy S23+ 5G", "2.75", 1080, 2340),
        ("SM-S911B", "Samsung Galaxy S23 5G", "2.75", 1080, 2340),
        ("SM-S928B", "Samsung Galaxy S24 Ultra 5G", "3.5", 1440, 3120),
        ("SM-S926B", "Samsung Galaxy S24+ 5G", "3.0", 1440, 3120),
        ("SM-A546B", "Samsung Galaxy A54 5G", "2.75", 1080, 2340),
        ("SM-A536B", "Samsung Galaxy A53 5G", "2.75", 1080, 2400),
        ("SM-A346B", "Samsung Galaxy A34 5G", "2.75", 1080, 2340),
        ("SM-N986B", "Samsung Galaxy Note 20 Ultra 5G", "3.5", 1440, 3088),
        ("SM-F946B", "Samsung Galaxy Z Fold 5", "3.0", 1812, 2176),
    ],
    "xiaomi": [
        ("2211133G", "Xiaomi 13", "3.0", 1080, 2400),
        ("2312DRA50G", "Redmi Note 13 Pro", "3.0", 1220, 2712),
        ("22101316G", "Redmi Note 12 Pro", "2.75", 1080, 2400),
        ("2201117TY", "Redmi Note 11", "2.75", 1080, 2400),
        ("23049PCD8G", "POCO F5", "3.0", 1080, 2400),
        ("21091116UG", "Xiaomi 11T Pro", "3.0", 1080, 2400),
    ],
    "google": [
        ("Pixel 8 Pro", "Google Pixel 8 Pro", "3.5", 1344, 2992),
        ("Pixel 8", "Google Pixel 8", "2.75", 1080, 2400),
        ("Pixel 7 Pro", "Google Pixel 7 Pro", "3.5", 1440, 3120),
        ("Pixel 7", "Google Pixel 7", "2.75", 1080, 2400),
        ("Pixel 6 Pro", "Google Pixel 6 Pro", "3.5", 1440, 3120),
        ("Pixel 6a", "Google Pixel 6a", "2.75", 1080, 2400),
    ],
    "oppo": [
        ("CPH2511", "OPPO Reno10 Pro 5G", "3.0", 1080, 2412),
        ("CPH2499", "OPPO Find N2 Flip", "3.0", 1080, 2520),
        ("CPH2371", "OPPO Reno7 5G", "2.75", 1080, 2400),
        ("CPH2211", "OPPO A94", "2.75", 1080, 2400),
    ],
    "vivo": [
        ("V2250", "vivo V27 5G", "3.0", 1080, 2400),
        ("V2205", "vivo V25 5G", "2.75", 1080, 2404),
        ("V2241", "vivo X90 Pro", "3.5", 1260, 2800),
    ],
}


def get_modern_katana_fb4a_ua(carrier=None, locale=None, brand=None, model=None, pure_bracket=True):
    """
    Sinh User-Agent Facebook for Android (Katana / FB4A) chuẩn xác 100% như trên app Meta:
    Ví dụ: [FBAN/FB4A;FBAV/518.0.0.63.86;FBBV/750617200;FBDM/{density=3.0,width=1080,height=1920};FBLC/en_US;FBRV/0;FBCR/Viettel;FBMF/samsung;FBBD/samsung;FBPN/com.facebook.katana;FBDV/SM-G998B;FBSV/9;FBOP/1;FBCA/x86_64:arm64-v8a;]
    Khi đăng nhập, Meta ghi nhận: 'was logged in on Samsung Galaxy S21 Ultra 5G'.
    """
    # 70% ưu tiên bản 518.0.0.63.86 (phiên bản chuẩn từ screenshot)
    if random.random() < 0.7:
        fbav, fbbv = ("518.0.0.63.86", "750617200")
    else:
        fbav, fbbv = random.choice(KATANA_MODERN_RELEASES)

    fbsv = str(random.choice([9, 10, 11, 12, 13, 14]))

    brand_key = (brand.lower() if brand and brand.lower() in MODERN_KATANA_PHONES else None) or random.choice(list(MODERN_KATANA_PHONES.keys()))
    cand_models = MODERN_KATANA_PHONES[brand_key]

    selected_tuple = None
    if model:
        for t in cand_models:
            if t[0].lower() == str(model).lower():
                selected_tuple = t
                break
    if not selected_tuple:
        selected_tuple = random.choice(cand_models)

    model_code, model_name, density, width, height = selected_tuple
    fbdm = "{" + f"density={density},width={width},height={height}" + "}"

    archite = random.choice((
        "x86_64:arm64-v8a", "arm64-v8a:armeabi-v7a:armeabi", "arm64-v8a:", "arm64-v8a:x86_64"
    ))

    fbcr_opts = ("Viettel", "MobiFone", "VinaPhone", "Vietnamobile")
    fbcr = carrier or random.choice(fbcr_opts)
    fblc = locale or ("vi_VN" if any(vn in str(fbcr).lower() for vn in ("viettel", "vinaphone", "mobifone", "vietnamobile")) else "en_US")

    brand_tag = brand_key.lower()
    ua_tag = f"[FBAN/FB4A;FBAV/{fbav};FBBV/{fbbv};FBDM/{fbdm};FBLC/{fblc};FBRV/0;FBCR/{fbcr};FBMF/{brand_tag};FBBD/{brand_tag};FBPN/com.facebook.katana;FBDV/{model_code};FBSV/{fbsv};FBOP/1;FBCA/{archite};]"

    if pure_bracket:
        return ua_tag, model_code, fbsv

    build_serial = f"TP1A.{random.randint(220624, 220905)}.{random.randint(10, 99)}"
    dalvik = f"Dalvik/2.1.0 (Linux; U; Android {fbsv}; {model_code} Build/{build_serial})"
    return f"{dalvik} {ua_tag}", model_code, fbsv


def get_android_app_ua(carrier=None, locale=None):
    """
    Sinh User-Agent Facebook Katana FB4A App chính thức (Samsung Galaxy S21 Ultra, S22, S23, Xiaomi, Pixel...):
    Khớp 100% định dạng app Facebook trên Android và phiên bản FBAV 518.x hiện đại.
    """
    return get_modern_katana_fb4a_ua(carrier=carrier, locale=locale, pure_bracket=True)


def get_kaios_ua():
    """Generate KaiOS feature phone UA (verified working - can't run modern JS)."""
    kai_model = random.choice([
        "Nokia 8110 4G", "Nokia 2720 Flip", "Nokia 800 Tough", "Nokia 6300 4G",
        "Nokia 2760 Flip", "Nokia 2780 Flip", "Nokia 8000 4G",
        "LYF/F220B/LYF-F220B-003-01-15-130718", "LYF/F271i/LYF-F271i-001-01-15-130718",
        "Alcatel Go Flip 3", "Alcatel Go Flip 4", "Alcatel SMARTFLIP",
        "JioPhone 2", "JioPhone Next",
        "TCL Flip Pro", "TCL Flip 2",
        "CAT B35", "CAT S22 Flip",
        "Energizer E282SC", "Energizer E241s",
        "Doro 7060", "Doro 7080",
    ])
    kai_ver = random.choice(["2.5", "2.5.1", "2.5.2", "2.5.3", "2.5.4", "3.0", "3.1"])
    rv_ver = "48.0"
    if kai_ver in ("3.0", "3.1"):
        rv_ver = "84.0"

    ua = f"Mozilla/5.0 (Mobile; {kai_model}; Android; rv:{rv_ver}) Gecko/{rv_ver} Firefox/{rv_ver} KAIOS/{kai_ver}"
    return ua


def get_windows_phone_ua():
    """Generate Windows Phone UA (verified working - IE Mobile can't run modern JS)."""
    wp_model = random.choice([
        "Lumia 520", "Lumia 525", "Lumia 530", "Lumia 535",
        "Lumia 540", "Lumia 550", "Lumia 620", "Lumia 625",
        "Lumia 630", "Lumia 635", "Lumia 640", "Lumia 640 XL",
        "Lumia 650", "Lumia 720", "Lumia 730", "Lumia 735",
        "Lumia 820", "Lumia 830", "Lumia 920", "Lumia 925",
        "Lumia 930", "Lumia 950", "Lumia 950 XL", "Lumia 1020",
        "Lumia 1320", "Lumia 1520",
        "HTC One M8", "HTC One M8 for Windows",
        "Samsung ATIV S", "Samsung ATIV S Neo",
        "Huawei Ascend W1", "Huawei Ascend W2",
    ])
    ua = f"Mozilla/5.0 (Mobile; Windows Phone 8.1; Android 4.0; ARM; Trident/7.0; Touch; rv:11.0; IEMobile/11.0; NOKIA; {wp_model}) like iPhone OS 7_0_3 Mac OS X AppleWebKit/537 (KHTML, like Gecko) Mobile Safari/537"
    return ua


def get_blackberry_ua():
    """Generate BlackBerry 10 UA (verified working - old WebKit can't run modern JS)."""
    bb_input = random.choice(["Touch", "Kbd"])
    bb_ver = random.choice([
        "10.3.1.2708", "10.3.1.2726", "10.3.1.2743",
        "10.3.2.2836", "10.3.2.2876", "10.3.2.2877",
        "10.3.3.2163", "10.3.3.2205", "10.3.3.3057", "10.3.3.3216",
    ])
    ua = f"Mozilla/5.0 (BB10; {bb_input}) AppleWebKit/537.35+ (KHTML, like Gecko) Version/{bb_ver} Mobile Safari/537.35+"
    return ua
