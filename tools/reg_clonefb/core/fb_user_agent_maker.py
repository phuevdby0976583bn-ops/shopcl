# -*- coding: utf-8 -*-
"""
core/fb_user_agent_maker.py
Integrated Facebook App (Katana / FB4A) User-Agent & Device Footprint Generator.
Reverse-engineered and enhanced from Mr-SxR (Masudur Rahman Sifat) FB-APP_User-Agent_Maker.

Features:
- 19 Major Smartphone Brands & 2,546 Authentic Device Model Codes
- 462 Facebook Katana Release Versions mapped by Android OS ranges (5.x to 15.x)
- 10 CPU Architectures (arm64-v8a, armeabi-v7a, x86_64, etc.)
- 22 Android Build families with authentic date-based build serials
- 25 Screen Density variants and dynamic display resolutions
- Multi-region Telephony & Carrier network profiles (VN, US, CA, DE, FR, AU, GB)
- 7 Authentic Katana FB4A User-Agent templates (uaD1 - uaD7)
- Dual format support: Dalvik Native App ({dalvik} {ua}) and SupportsFresco IAB ({iab_ua})
"""

import os
import sys
import random
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# CONSTANTS & ASSETS
# ---------------------------------------------------------
DATA_FILE = Path(__file__).resolve().parent / "fb_ua_data.json"

ARCHITECTURES = (
    "arm64-v8a:null",
    "arm64-v8a:",
    "armeabi-v7a:armeabi",
    "arm64-v8a:armeabi-v7a:armeabi",
    "x86:armeabi-v7a",
    "x86_64:armeabi-v7a",
    "x86:arm64-v8a:armeabi-v7a",
    "x86_64:arm64-v8a:armeabi-v7a",
    "x86_64:x86:armeabi-v7a",
    "x86_64:x86:arm64-v8a",
)

BUILD_PREFIXES = (
    "SP1A.", "TP2A.", "TP1A.", "RKQ1.", "RP1A.", "TQ3A.", "TD2A.", "TD4A.",
    "SP2A.", "SD2A.", "SQ3A.", "RD2A.", "RQ3A.", "QD4A.", "QQ3A.", "QP1A.",
    "PQ3B.", "PD2A.", "PPR2.", "PPR1.", "OPM8.", "OPR6."
)

DENSITIES = (
    "1.0", "1.25", "1.2506", "1.278", "1.5", "1.625", "1.75", "1.8", "1.875",
    "2.0", "2.125", "2.2", "2.25", "2.375", "2.5", "2.75", "2.8", "2.9",
    "2.29375", "3.0", "3.25", "3.5", "3.75", "3.8", "4.0"
)

VIETNAM_CARRIERS = (
    "Viettel", "VinaPhone", "MobiFone", "Vietnamobile", "Wintel", "Itelecom"
)

# Load data from json file
_DATA_CACHE = None

def _load_ua_data() -> Dict[str, Any]:
    global _DATA_CACHE
    if _DATA_CACHE is not None:
        return _DATA_CACHE
    
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                _DATA_CACHE = json.load(f)
                return _DATA_CACHE
        except Exception as e:
            logger.warning(f"Could not load fb_ua_data.json: {e}")
    
    # Fallback minimal sets if file missing
    _DATA_CACHE = {
        "brands": {
            "Samsung": ["SM-S928B", "SM-S918B", "SM-S908B", "SM-A546B", "SM-A536B", "SM-A336B", "SM-G991B"],
            "OPPO": ["CPH2371", "CPH2511", "CPH2499", "CPH1831", "CPH2015", "CPH2127"],
            "Xiaomi": ["Redmi Note 11", "Redmi Note 12", "2201117TY", "21091116UG"],
            "Google": ["Pixel 8 Pro", "Pixel 7", "Pixel 6", "G011C", "G020A"],
            "Vivo": ["V25", "V25 Pro", "X90", "X90 Pro", "Y100", "Y200"]
        },
        "tier12_15": [("485.0.0.0.51", "456005032"), ("484.0.0.0.50", "455803383"), ("482.0.0.51.80", "455415830"), ("480.0.0.55.88", "455016452")],
        "tier8_11": [("305.1.0.40.120", "272401224"), ("304.0.0.39.118", "271126404"), ("300.2.0.58.129", "265245015")],
        "tier5_7": [("128.0.0.26.68", "61451332"), ("126.0.0.23.77", "59956218"), ("125.0.0.23.80", "58971521")],
        "locales": {
            "vi_VN": list(VIETNAM_CARRIERS),
            "en_US": ["Verizon", "AT&T", "T-Mobile", "Cricket", "Google Fi", "Metro by T-Mobile"],
            "en_GB": ["EE", "O2", "Vodafone UK", "Three UK", "giffgaff", "Tesco Mobile"]
        }
    }
    return _DATA_CACHE


def get_all_brands() -> List[str]:
    data = _load_ua_data()
    return list(data.get("brands", {}).keys())


def get_models_by_brand(brand: str) -> List[str]:
    data = _load_ua_data()
    return data.get("brands", {}).get(brand, [])


def get_all_katana_releases() -> List[Tuple[str, str]]:
    data = _load_ua_data()
    return (
        data.get("tier12_15", []) +
        data.get("tier8_11", []) +
        data.get("tier5_7", [])
    )


# ---------------------------------------------------------
# GENERATOR ENGINE
# ---------------------------------------------------------
def generate_fb_user_agent(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    os_version: Optional[str] = None,
    locale: Optional[str] = None,
    carrier: Optional[str] = None,
    geo_profile: Optional[Any] = None,
    template_idx: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Generates a realistic Facebook Katana (FB4A) User-Agent structure.
    Returns full Dalvik Native UA, pure FBAN/FB4A tag, SupportsFresco Webview UA,
    matching Chrome Mobile browser UA, and complete device hardware specs.
    """
    data = _load_ua_data()
    brands_dict = data.get("brands", {})
    
    # 1. Select Brand & Model
    if not brand or brand not in brands_dict:
        brand = random.choice(list(brands_dict.keys()))
    
    available_models = brands_dict.get(brand, ["Generic"])
    if not model or model not in available_models:
        model = random.choice(available_models)
        
    # 2. Android OS Version
    if not os_version:
        major = random.randint(10, 14) if random.random() < 0.85 else random.randint(6, 15)
        minor = random.randint(0, 4)
        patch = random.randint(0, 3)
        os_version = f"{major}.{minor}.{patch}"
    else:
        major = int(str(os_version).split(".")[0])

    # 3. Katana Releases mapped strictly by Android major version (Mr-SxR accurate logic)
    if major >= 12:
        rel_list = data.get("tier12_15", [])
    elif major >= 8:
        rel_list = data.get("tier8_11", [])
    else:
        rel_list = data.get("tier5_7", [])
        
    if not rel_list:
        rel_list = [("485.0.0.0.51", "456005032")]
        
    fbav, fbbv = random.choice(rel_list)
    rvplus = random.randint(1, 99)
    try:
        fbrv = (int(fbav.split(".")[0]) * 1000) + int(fbbv) + rvplus
    except Exception:
        fbrv = 456005032
        
    fbop = random.choice(("1", "19", "20"))
    archite = random.choice(ARCHITECTURES)
    
    # 4. Build Serial Number
    build_prefix = random.choice(BUILD_PREFIXES)
    date_code = f"{random.randint(7, 24):02d}{random.randint(1, 12):02d}{random.randint(1, 28):02d}.{random.randint(1, 70):03d}"
    full_build_tag = f"{build_prefix}{date_code}"

    # 5. Screen Resolution & Density
    density = random.choice(DENSITIES)
    width = random.randint(720, 1440) if random.random() < 0.8 else random.randint(480, 1080)
    height = random.randint(1600, 2560) if random.random() < 0.8 else random.randint(800, 2400)
    fbdm = f"{{density={density},width={width},height={height}}}"

    # 6. Locale & Carrier
    locales_dict = data.get("locales", {})
    if geo_profile:
        carrier = getattr(geo_profile, "carrier_name", None) or carrier
        locale = getattr(geo_profile, "locale", None) or locale
        
    if not locale:
        locale = random.choice(list(locales_dict.keys()) + ["vi_VN"])
        
    if not carrier:
        if "vi" in locale.lower():
            carrier = random.choice(VIETNAM_CARRIERS)
        elif locale in locales_dict:
            carrier = random.choice(locales_dict[locale])
        else:
            carrier = "Viettel"

    # 7. Dalvik Prefix
    dalvik = f"Dalvik/2.1.0 (Linux; U; Android {os_version}; {model} Build/{full_build_tag})"
    dblifb = f"[FBAN/FB4A;FBAV/{fbav};FBBV/{fbbv};"

    # 8. Seven authentic FB4A User-Agent templates from Mr-SxR
    uaD1 = f"[FBAN/FB4A;FBAV/{fbav};FBPN/com.facebook.katana;FBLC/{locale};FBBV/{fbbv};FBCR/{carrier};FBMF/{brand};FBBD/{brand.lower()};FBDV/{model};FBSV/{os_version};FBCA/{archite};FBDM/{fbdm};]"
    uaD2 = f"[FBAN/FB4A;FBAV/{fbav};FBPN/com.facebook.katana;FBLC/{locale};FBBV/{fbbv};FBCR/{carrier};FBMF/{brand};FBBD/{brand.lower()};FBDV/{model};FBSV/{os_version};FBCA/{archite};FBDM/{fbdm};FB_FW/1;]"
    uaD3 = f"[FBAN/FB4A;FBAV/{fbav};FBPN/com.facebook.katana;FBLC/{locale};FBBV/{fbbv};FBCR/{carrier};FBMF/{brand};FBBD/{brand.lower()};FBDV/{model};FBSV/{os_version};FBCA/{archite};FBDM/{fbdm};FB_FW/1;] FBBK/1"
    uaD4 = f"[FBAN/FB4A;FBAV/{fbav};FBPN/com.facebook.katana;FBLC/{locale};FBBV/{fbbv};FBCR/{carrier};FBMF/{brand};FBBD/{brand.lower()};FBDV/{model};FBSV/{os_version};FBCA/{archite};FBDM/{fbdm};FB_FW/1;FBRV/{fbrv};]"
    uaD5 = f"[FBAN/FB4A;FBAV/{fbav};FBPN/com.facebook.katana;FBLC/{locale};FBBV/{fbbv};FBCR/{carrier};FBMF/{brand};FBBD/{brand.lower()};FBDV/{model};FBSV/{os_version};FBCA/{archite};FBDM/{fbdm};FB_FW/1;FBRV/{fbrv};] FBBK/1"
    uaD6 = f"[FBAN/FB4A;FBAV/{fbav};FBBV/{fbbv};FBDM/{fbdm};FBLC/{locale};FBRV/{fbrv};FB_FW/2;FBCR/{carrier};FBMF/{brand};FBBD/{brand.lower()};FBPN/com.facebook.katana;FBDV/{model};FBSV/{os_version};FBOP/{fbop};FBCA/{archite};]"
    uaD7 = f"[FBAN/FB4A;FBAV/{fbav};FBBV/{fbbv};FBDM/{fbdm};FBLC/{locale};FBCR/{carrier};FBMF/{brand};FBBD/{brand.lower()};FBPN/com.facebook.katana;FBDV/{model};FBSV/{os_version};FBCA/{archite};]"
    
    templates = [uaD1, uaD2, uaD3, uaD4, uaD5, uaD6, uaD7]
    if template_idx is not None and 0 <= template_idx < len(templates):
        chosen_app_ua = templates[template_idx]
        chosen_tname = f"uaD{template_idx+1}"
    else:
        rnd_idx = random.randint(0, len(templates) - 1)
        chosen_app_ua = templates[rnd_idx]
        chosen_tname = f"uaD{rnd_idx+1}"

    full_dalvik_app_ua = f"{dalvik} {chosen_app_ua}"
    double_fban_ua = f"{dblifb}{chosen_app_ua}"

    # 9. Matching Webview & SupportsFresco In-App Browser UA
    chrome_major = "131"
    chrome_build = f"131.0.{random.randint(6700, 6834)}.{random.randint(50, 220)}"
    
    iab_ua = (
        f"Mozilla/5.0 (Linux; Android {os_version}; {model} Build/{full_build_tag}; wv) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/{chrome_build} Mobile Safari/537.36 "
        f"[FB_IAB/FB4A;FBAV/{fbav};FBBV/{fbbv};FBDV/{model};FBMD/{brand};FBSN/Android;"
        f"FBSV/{os_version};FBSS/{density};FBCR/{carrier};FBID/phone;FBLC/{locale};FBOP/{fbop};FBRV/{fbrv};SupportsFresco/1;]"
    )
    
    chrome_web_ua = (
        f"Mozilla/5.0 (Linux; Android {os_version}; {model} Build/{full_build_tag}) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_build} Mobile Safari/537.36"
    )

    return {
        "user_agent": full_dalvik_app_ua,
        "dalvik_app_ua": full_dalvik_app_ua,
        "app_ua": chosen_app_ua,
        "dalvik_ua": dalvik,
        "dblifb_ua": double_fban_ua,
        "iab_ua": iab_ua,
        "web_ua": chrome_web_ua,
        "brand": brand,
        "model": model,
        "os_version": os_version,
        "os_major": str(major),
        "katana_version": fbav,
        "katana_build": fbbv,
        "fbrv": str(fbrv),
        "fbop": fbop,
        "build_tag": full_build_tag,
        "density": density,
        "screen_width": width,
        "screen_height": height,
        "architecture": archite,
        "carrier": carrier,
        "locale": locale,
        "chrome_major": chrome_major,
        "chrome_build": chrome_build,
        "template": chosen_tname,
    }


def make_fb_app_user_agent(brand: Optional[str] = None, os_version: Optional[str] = None) -> str:
    """Quick helper returning standard Dalvik + Katana User-Agent string."""
    return generate_fb_user_agent(brand=brand, os_version=os_version)["user_agent"]


def make_fb_iab_user_agent(brand: Optional[str] = None, os_version: Optional[str] = None) -> str:
    """Quick helper returning In-App Browser SupportsFresco User-Agent string."""
    return generate_fb_user_agent(brand=brand, os_version=os_version)["iab_ua"]


def make_device_profile(
    is_fb_app: bool = False,
    geo_profile: Optional[Any] = None,
    brand: Optional[str] = None,
    model: Optional[str] = None
) -> Any:
    """
    Generates a DeviceProfile instance compatible with core.session_builder.
    Pre-wired with Mr-SxR Katana parameters and genuine hardware fingerprints.
    """
    from core.session_builder import DeviceProfile, generate_dynamic_grease_brands

    ua_meta = generate_fb_user_agent(
        brand=brand,
        model=model,
        geo_profile=geo_profile
    )
    
    sec_ch = generate_dynamic_grease_brands(ua_meta["chrome_major"], is_webview=is_fb_app)
    dpr_val = float(ua_meta["density"]) if ua_meta["density"].replace(".", "").isdigit() else 2.5
    
    # Telephony and Geo synchronization
    mcc = "452"
    mnc = "04"
    sim_iso = "vn"
    carrier = ua_meta["carrier"]
    country_code = "VN"
    locale = ua_meta["locale"]
    timezone = "Asia/Ho_Chi_Minh"
    tz_offset = 420
    accept_lang = f"{ua_meta['locale'].replace('_', '-')},{ua_meta['locale'][:2]};q=0.9,en-US;q=0.8,en;q=0.7"

    if geo_profile:
        mcc = getattr(geo_profile, "mcc", mcc)
        mnc = getattr(geo_profile, "mnc", mnc)
        sim_iso = getattr(geo_profile, "sim_country_iso", sim_iso)
        carrier = getattr(geo_profile, "carrier_name", carrier)
        country_code = getattr(geo_profile, "country_code", country_code)
        locale = getattr(geo_profile, "locale", locale)
        timezone = getattr(geo_profile, "timezone", timezone)
        tz_offset = getattr(geo_profile, "timezone_offset_minutes", tz_offset)
        accept_lang = getattr(geo_profile, "accept_language", accept_lang)
    elif ua_meta["locale"] == "en_US":
        mcc = "310"
        mnc = "410"
        sim_iso = "us"
        carrier = "Verizon"
        country_code = "US"
        timezone = "America/New_York"
        tz_offset = -300
    elif ua_meta["locale"] == "en_GB":
        mcc = "234"
        mnc = "30"
        sim_iso = "gb"
        carrier = "Vodafone UK"
        country_code = "GB"
        timezone = "Europe/London"
        tz_offset = 0

    # Web/IAB UA is used as default user_agent for HTTP navigations, with native UA stored
    primary_ua = ua_meta["iab_ua"] if is_fb_app else ua_meta["web_ua"]

    return DeviceProfile(
        name=f"{ua_meta['brand']} {ua_meta['model']} (Mobile Browser)",
        brand=ua_meta["brand"],
        model=ua_meta["model"],
        os_name="Android",
        os_version=ua_meta["os_version"],
        chrome_major=ua_meta["chrome_major"],
        viewport_width=int(ua_meta["screen_width"] / max(1.0, dpr_val)),
        viewport_height=int(ua_meta["screen_height"] / max(1.0, dpr_val)),
        pixel_ratio=dpr_val,
        impersonate="chrome131_android",
        user_agent=primary_ua,
        sec_ch_ua=sec_ch,
        sec_ch_ua_mobile="?1",
        sec_ch_ua_platform='"Android"',
        sec_ch_ua_platform_version=f'"{ua_meta["os_major"]}.0.0"',
        sec_ch_ua_model=f'"{ua_meta["model"]}"',
        sec_ch_dpr=str(dpr_val),
        sec_ch_viewport_width=str(int(ua_meta["screen_width"] / max(1.0, dpr_val))),
        sec_ch_prefers_color_scheme=random.choice(['"light"', '"dark"']),
        sec_ch_ua_arch='"arm"' if "arm" in ua_meta["architecture"] else '"x86"',
        sec_ch_ua_bitness='"64"' if "64" in ua_meta["architecture"] else '"32"',
        screen_width=ua_meta["screen_width"],
        screen_height=ua_meta["screen_height"],
        carrier=carrier,
        country_code=country_code,
        mcc=mcc,
        mnc=mnc,
        sim_country_iso=sim_iso,
        locale=locale,
        accept_language=accept_lang,
        timezone=timezone,
        timezone_offset_minutes=tz_offset,
        soc_chipset=f"{ua_meta['brand']} Octa-Core Processor",
        is_fb_app=is_fb_app,
        supports_fresco=False,
        fb_version=ua_meta["katana_version"],
        fb_build=ua_meta["katana_build"],
        gl_renderer="Adreno (TM) 740" if "Samsung" in ua_meta["brand"] or "Qualcomm" in ua_meta["brand"] else "Mali-G78 MC14",
        app_user_agent=ua_meta["app_ua"],
        dalvik_user_agent=ua_meta["dalvik_ua"],
        web_user_agent=ua_meta["web_ua"],
        raw_app_ua=ua_meta["dalvik_app_ua"],
    )


# ---------------------------------------------------------
# INTERACTIVE CLI (Mr-SxR Compatible)
# ---------------------------------------------------------
def run_cli():
    """Runs the terminal interactive UI honoring Mr-SxR tool style."""
    clr_code = lambda c: f"\033[{c}m" if sys.platform != "win32" or "WT_SESSION" in os.environ or "ANSICON" in os.environ else ""
    w = clr_code("1;97")
    g = clr_code("1;92")
    r = clr_code("1;91")
    c = clr_code("1;96")
    y = clr_code("1;93")
    reset = clr_code("0")

    line = f"{c}────────────────────────────────────────────────────────────{reset}"

    def banner():
        os.system("cls" if os.name == "nt" else "clear")
        print(f"""{g}
      .d8888.  db    db  d8888b. 
      88'  YP  8b  d8'  88  8D 
      8bo.     8bd8'   88oobY' 
        Y8b.   .dPYb.   888b   
      db   8D  .8P  Y8.  88 88. 
      8888Y'  YP    YP  88   YD   
{line}
 {g}[{r}●{g}] TOOL        {c}:{w} Facebook App User-Agent Maker (Mr-SxR Core)
 {g}[{r}●{g}] STATUS      {c}:{g} Integrated & Production Ready
 {g}[{r}●{g}] BRANDS      {c}:{y} 19 Brands | 2,546 Models | 462 Katana Releases
{line}""")

    while True:
        banner()
        print(f" {g}[{r}01{g}]{w} Generate Single User-Agent")
        print(f" {g}[{r}02{g}]{w} Batch Generate User-Agents (10x)")
        print(f" {g}[{r}03{g}]{w} Export User-Agents to File (ua_output.txt)")
        print(f" {g}[{r}00{g}]{w} Exit")
        print(line)
        
        choice = input(f" {g}CHOOSE OPTION {c}:{w} ").strip().lower()
        if choice in ("1", "01", "a"):
            banner()
            res = generate_fb_user_agent()
            print(f"{y}[Device]{w} {res['brand']} {res['model']} (Android {res['os_version']})")
            print(f"{y}[Katana Release]{w} v{res['katana_version']} (Build {res['katana_build']}) | {res['carrier']} ({res['locale']})")
            print(line)
            print(f"{c}• Dalvik + Katana App UA:{reset}")
            print(f"{w}{res['dalvik_app_ua']}{reset}")
            print(line)
            print(f"{c}• SupportsFresco In-App Browser UA:{reset}")
            print(f"{w}{res['iab_ua']}{reset}")
            print(line)
            input(f"\n{g}Press Enter to generate another...{reset}")
        elif choice in ("2", "02", "b"):
            banner()
            print(f"{y}Generating 10 random Facebook Katana User-Agents:{reset}\n")
            for i in range(1, 11):
                item = generate_fb_user_agent()
                print(f"{g}[{i:02d}]{w} {item['brand']} {item['model']} (Katana {item['katana_version']})")
                print(f"{c}{item['dalvik_app_ua']}\n{reset}")
            print(line)
            input(f"\n{g}Press Enter to return to menu...{reset}")
        elif choice in ("3", "03", "c"):
            banner()
            cnt_str = input(f" {g}Number of User-Agents to export (default: 50){c}:{w} ").strip()
            count = int(cnt_str) if cnt_str.isdigit() else 50
            out_file = Path("ua_output.txt")
            with open(out_file, "w", encoding="utf-8") as f:
                for _ in range(count):
                    ua = generate_fb_user_agent()["dalvik_app_ua"]
                    f.write(ua + "\n")
            print(f"\n{g}✓ Successfully exported {count} User-Agents to {out_file.resolve()}{reset}")
            print(line)
            input(f"\n{g}Press Enter to return to menu...{reset}")
        elif choice in ("0", "00", "exit", "q"):
            print(f"\n{g}Goodbye!{reset}")
            break


if __name__ == "__main__":
    try:
        run_cli()
    except (KeyboardInterrupt, EOFError):
        print("\n\nExiting...")
        sys.exit(0)
