import re
from ui.colors import GREEN, RED, WHITE, CYAN, EKL, LINE
from core.settings_manager import load_settings

SERVER_MAP = {
    "1": "m.facebook.com",
    "2": "mbasic.facebook.com",
    "3": "touch.facebook.com",
    "4": "free.facebook.com",
    "5": "m.alpha.facebook.com",
    "6": "m.beta.facebook.com",
    "7": "x.facebook.com",
    "8": "limited.facebook.com",
    "9": "iphone.facebook.com",
    "10": "d.facebook.com",
}


# Prompt user to select device type or use default from settings
def select_device(config_state, render_callback):
    settings = load_settings()
    device_set = settings.get("device_settings", {})
    ask_device = device_set.get("ask_for_device", True)
    def_device = str(device_set.get("default_device", "none")).strip().lower()

    device_type = "Android"

    device_map = {
        "1": "Android",
        "2": "KaiOS",
        "3": "WindowsPhone",
        "4": "BlackBerry",
        "5": "IphoneApp",
        "6": "AndroidApp",
    }

    if def_device in device_map:
        device_type = device_map[def_device]
    elif ask_device:
        if render_callback:
            render_callback()
        print(f" {GREEN}[{RED}01{GREEN}] Android Browser {WHITE}(Android 4-8, Chrome 30-70)")
        print(f" {GREEN}[{RED}02{GREEN}] KaiOS {WHITE}(Feature Phone)")
        print(f" {GREEN}[{RED}03{GREEN}] Windows Phone {WHITE}(IE Mobile)")
        print(f" {GREEN}[{RED}04{GREEN}] BlackBerry {WHITE}(BB10)")
        print(f" {GREEN}[{RED}05{GREEN}] iPhone App {WHITE}(iOS 6-9, Facebook App)")
        print(f" {GREEN}[{RED}06{GREEN}] Android App {WHITE}(Android 4-6, FB Lite/Messenger)")
        print(f"{LINE}")
        dev_choice = input(f" {GREEN}[{RED}â—{GREEN}] Select Device {EKL} ").strip()
        device_type = device_map.get(dev_choice, "Android")

    config_state["device"] = device_type
    if render_callback:
        render_callback()
    return device_type


# Select browser type (fixed for all legacy device types)
def select_browser(device_type, config_state, render_callback):
    browser_type = "Default"
    config_state["browser"] = browser_type
    if render_callback:
        render_callback()
    return browser_type


# Prompt user to select server domain or use default from settings
def select_server(config_state, render_callback):
    settings = load_settings()
    server_set = settings.get("server_settings", {})
    raw_id = server_set.get("tools_server_id", "none")
    random_cfg = bool(server_set.get("random_server", False))
    saved_pool = server_set.get("server_pool", [])
    str_id = str(raw_id).strip().lower()

    if random_cfg or str_id in ("random", "all", "rand", "0", "00"):
        config_state["server"] = "random"
        config_state["server_mode"] = "random_all"
        config_state["random_server"] = True
        if render_callback:
            render_callback()
        return "random"

    # Check if str_id specifies multiple servers, e.g. "1,2,3"
    parts = [p.strip() for p in re.split(r'[, ]+', str_id) if p.strip()]
    if len(parts) > 1:
        pool = [SERVER_MAP.get(p, p) for p in parts if (p in SERVER_MAP or p in SERVER_MAP.values())]
        if pool:
            config_state["server"] = "subset"
            config_state["server_mode"] = "subset"
            config_state["server_pool"] = pool
            config_state["random_subset"] = True
            if render_callback:
                render_callback()
            return "subset"

    server_domain = "m.facebook.com"

    if str_id == "none" or str_id == "":
        if render_callback:
            render_callback()
        print(f" {GREEN}[{RED}00{GREEN}] {CYAN}ðŸŽ² Random táº¥t cáº£ server (1-{len(SERVER_MAP)})")
        for idx, domain in SERVER_MAP.items():
            print(f" {GREEN}[{RED}{idx.zfill(2)}{GREEN}] {WHITE}{domain}")
        print(f"{LINE}")

        while True:
            choice = input(f" {GREEN}[{RED}â—{GREEN}] Select Server (0: Táº¥t cáº£, 1 sá»‘: Cá»‘ Ä‘á»‹nh, vd '1,2,3': NhÃ³m) {EKL} ").strip()
            if choice in ("0", "00", "all", "random"):
                server_domain = "random"
                config_state["server"] = "random"
                config_state["server_mode"] = "random_all"
                config_state["random_server"] = True
                break

            ch_parts = [p.strip() for p in re.split(r'[, ]+', choice) if p.strip()]
            if len(ch_parts) > 1 and all(p in SERVER_MAP for p in ch_parts):
                pool = [SERVER_MAP[p] for p in ch_parts]
                server_domain = "subset"
                config_state["server"] = "subset"
                config_state["server_mode"] = "subset"
                config_state["server_pool"] = pool
                config_state["random_subset"] = True
                break

            if choice in SERVER_MAP:
                server_domain = SERVER_MAP[choice]
                config_state["server"] = server_domain
                config_state["server_mode"] = "single"
                config_state["random_server"] = False
                break
            if not choice:
                break
            print(f" {RED}Invalid! Enter 0, 1-{len(SERVER_MAP)}, or '1,2,3'")
    else:
        server_domain = SERVER_MAP.get(str_id, "m.facebook.com")
        config_state["server"] = server_domain
        config_state["server_mode"] = "single"
        config_state["random_server"] = False

    config_state["server"] = server_domain
    if render_callback:
        render_callback()
    return server_domain



import random
from core.user_agent import ANDROID_BROWSER_MODELS, get_android_browser_ua

def get_random_android_device():
    """Tra ve thong tin mau thiet bi Android & User-Agent cho GUI Tool Mr-SxR."""
    ua_data = get_android_browser_ua()
    if isinstance(ua_data, tuple):
        ua_str = ua_data[0]
        model = ua_data[1] if len(ua_data) > 1 else "SM-G950F"
    else:
        ua_str = str(ua_data)
        model = random.choice(ANDROID_BROWSER_MODELS) if ANDROID_BROWSER_MODELS else "SM-G950F"

    brand = "Samsung"
    if "Nexus" in model or "Pixel" in model:
        brand = "Google"
    elif "Xiaomi" in model or "Redmi" in model:
        brand = "Xiaomi"
    elif "Oppo" in model or "CPH" in model:
        brand = "OPPO"
    elif "Vivo" in model or "V2" in model:
        brand = "Vivo"
    elif "LG" in model:
        brand = "LG"
    elif "HTC" in model:
        brand = "HTC"
    elif "Sony" in model or "Xperia" in model:
        brand = "Sony"
    
    katana_versions = ["462.0.0.47.108", "459.0.0.41.112", "455.0.0.44.110", "450.0.0.38.109", "445.0.0.34.118"]
    return {
        "brand": brand,
        "model": model,
        "katana_ver": random.choice(katana_versions),
        "user_agent": ua_str,
    }
