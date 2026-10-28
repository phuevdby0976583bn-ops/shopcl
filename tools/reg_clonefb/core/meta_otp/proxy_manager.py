import json
from core.meta_otp.config import *

# Settings cache
_proxy_settings_cache = None

def load_settings(setting_key="api_settings"):
    """Load and cache proxy-related settings from Setting.json."""
    global _proxy_settings_cache
    if _proxy_settings_cache is None:
        try:
            with open("Setting.json", "r") as f:
                _proxy_settings_cache = json.load(f)
        except:
            _proxy_settings_cache = {}

        if "api_settings" not in _proxy_settings_cache and "forget_settings" in _proxy_settings_cache:
            _proxy_settings_cache["api_settings"] = _proxy_settings_cache.get("forget_settings", {})

    return _proxy_settings_cache.get(setting_key, {})

def parse_proxy(proxy_str):
    """Parse a proxy string into requests-compatible dict format.
    
    Supported formats:
      - ip:port
      - ip:port:user:pass
      - http://user:pass@ip:port
    """
    proxy_str = proxy_str.strip()
    if not proxy_str:
        return None

    if "://" not in proxy_str:
        parts = proxy_str.split(':')
        if len(parts) == 4:
            ip, port, user, pwd = parts
            proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
        elif len(parts) == 2:
            ip, port = parts
            proxy_url = f"http://{ip}:{port}"
        else:
            return None
    else:
        proxy_url = proxy_str

    return {"http": proxy_url, "https": proxy_url}

def get_proxy_list(settings_key="api_settings", prompt_label="Proxy"):
    """Load proxies from settings and/or interactive user input."""
    settings = load_settings(settings_key)
    proxy_set = settings.get("proxy_settings", {})
    ask_proxy = proxy_set.get("ask_for_proxy", True)
    def_proxy = proxy_set.get("default_proxy", "")

    ask_proxy_final = ask_proxy
    PROXY_LIST = []

    # Load default proxies from config
    if def_proxy:
        if isinstance(def_proxy, list):
            print(f"{WHITE} Loading {len(def_proxy)} Default {prompt_label}...")
            for p in def_proxy:
                parsed = parse_proxy(p)
                if parsed:
                    PROXY_LIST.append({'proxy': parsed, 'locale': 'en_US', 'country': 'Unknown'})
                    print(f"{GREEN} [{RED}●{GREEN}] {prompt_label} Added: {p}")
                else:
                    print(f"{RED} Invalid Default {prompt_label} Format: {p}")
        else:
            parsed_proxies = parse_proxy(def_proxy)
            if parsed_proxies:
                print(f"{WHITE} Loading Default {prompt_label}...")
                PROXY_LIST.append({'proxy': parsed_proxies, 'locale': 'en_US', 'country': 'Unknown'})
                print(f"{GREEN} [{RED}●{GREEN}] {prompt_label} Added: {def_proxy}")
            else:
                print(f"{RED} Invalid Default {prompt_label} Format!")

    if def_proxy and not PROXY_LIST:
        print(f"{RED} All Default {prompt_label} Failed!")
        ask_proxy_final = True

    if PROXY_LIST and not ask_proxy:
        ask_proxy_final = False

    # Interactive proxy input
    if ask_proxy_final:
        proxy_input = input(f"{GREEN} [{RED}●{GREEN}] Enter {prompt_label} (or 'y' for multiple) [Enter to Skip] {EKL} ").strip()

        if proxy_input.lower() == 'y':
            try:
                cnt_in = input(f"{GREEN} [{RED}●{GREEN}] How many {prompt_label}? {EKL} ")
                if cnt_in.strip():
                    cnt = int(cnt_in)
                    for i in range(cnt):
                        while True:
                            p_in = input(f"{WHITE} [{RED}●{WHITE}] Enter {prompt_label} [{i+1}/{cnt}] {EKL} ").strip()
                            if not p_in:
                                continue
                            parsed = parse_proxy(p_in)
                            if parsed:
                                print(f"{GREEN} [{RED}●{GREEN}] {prompt_label} Added: {p_in}")
                                PROXY_LIST.append({'proxy': parsed, 'locale': 'en_US', 'country': 'Unknown'})
                                break
                            else:
                                print(f"{RED} Invalid {prompt_label} Format!")
                else:
                    print(f"{RED} Invalid Number!")
            except:
                print(f"{RED} Invalid Input")

        elif proxy_input:
            parsed_proxies = parse_proxy(proxy_input)
            if parsed_proxies:
                print(f"{GREEN} [{RED}●{GREEN}] {prompt_label} Added: {proxy_input}")
                PROXY_LIST.append({'proxy': parsed_proxies, 'locale': 'en_US', 'country': 'Unknown'})
            else:
                print(f"{RED} Invalid {prompt_label} Format!")

    return PROXY_LIST
