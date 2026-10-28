# -*- coding: utf-8 -*-
"""
core.password_manager
Bộ sinh mật khẩu ngẫu nhiên cường độ cao (Ultra-Random Multi-Architecture Password Generator).
Loại bỏ hoàn toàn mẫu hình cố định để chống Meta gom cụm Sybil (Sybil Graph Anomaly).
"""

import random
import string
from typing import Optional, Dict, Any, List

WORDS_VIET = [
    "Thanh", "Hoang", "Phuong", "Khanh", "Minh", "Tuan", "Quoc", "Thao", "Linh", "Bao",
    "Duyen", "Trang", "Kiet", "Thang", "Ngoc", "Hung", "Cuong", "Chien", "Phuc", "Hai",
    "Phong", "Nam", "Long", "Son", "Tung", "Dat", "Khoa", "Hieu", "Tai", "Vinh",
    "Quan", "Lam", "Kien", "Binh", "Triet", "Nghia", "Tu", "Khoi", "Sang", "Nguyen",
    "Huyen", "Huong", "Lan", "Nhi", "Vy", "Ha", "Tram", "Ngan", "Hoa", "Tuyet",
    "Mai", "Quynh", "Anh", "Dung", "Diep", "Chi", "Ly", "Thu", "Chau", "Han",
    "Thinh", "Phat", "Khang", "Trieu", "Bich", "Trinh", "Phu", "Duc", "Chau", "Thao"
]

WORDS_ENG = [
    "Sunny", "Breeze", "River", "Silver", "Golden", "Shadow", "Falcon", "Eagle", "Summit",
    "Cosmic", "Lunar", "Solar", "Thunder", "Ocean", "Forest", "Dragon", "Phoenix", "Spark",
    "Crystal", "Amber", "Velvet", "Marble", "Timber", "Astral", "Harbor", "Aurora", "Echo",
    "Blaze", "Horizon", "Miracle", "Venture", "Apex", "Zenith", "Pulse", "Titan", "Nova",
    "Stella", "Orion", "Sierra", "Cascade", "Glacier", "Zephyr", "Cobalt", "Sable", "Jasper",
    "Raven", "Canyon", "Summit", "Vanguard", "Mystic", "Zenith", "Radiant", "Vivid", "Lumos"
]

WORDS_GLOBAL = [
    "Luna", "Sol", "Cielo", "Mar", "Estrella", "Nube", "Flor", "Brisa", "Terra", "Fuego",
    "Sakura", "Hikari", "Yuki", "Kaze", "Sora", "Hoshi", "Mori", "Ryu", "Aoi", "Mizu",
    "Stern", "Sonne", "Mond", "Wald", "Berg", "Wolke", "Fluss", "Traum", "Licht", "Feuer",
    "Aero", "Aqua", "Ignis", "Silva", "Lux", "Vita", "Nox", "Vesper", "Pax", "Cor", "Fidelis"
]

SPECIAL_SYMBOLS = ["@", "#", "$", "!", "%", "&", "*", "_", "^", "~", "-"]


def generate_random_password(length: int = 12) -> str:
    """
    Sinh mật khẩu ngẫu nhiên với 16 cấu trúc biến thiên đa dạng (10 - 18 ký tự).
    Triệt tiêu hoàn toàn khả năng nhận diện mẫu mật khẩu tự động hóa của Meta Sybil Graph.
    """
    arch = random.randint(1, 16)
    sym = random.choice(SPECIAL_SYMBOLS)
    sym2 = random.choice(SPECIAL_SYMBOLS)
    w_vi = random.choice(WORDS_VIET)
    w_en = random.choice(WORDS_ENG + WORDS_GLOBAL)
    digits = str(random.randint(100, 9999))
    digits_short = str(random.randint(10, 99))
    birth_year = str(random.randint(1992, 2005))
    tail_chars = "".join(random.choices(string.ascii_lowercase, k=random.randint(2, 4)))

    if arch == 1:
        w2 = random.choice(WORDS_VIET)
        pwd = f"{w_vi}{w2}{sym}{digits}"
    elif arch == 2:
        pwd = f"{w_vi}{sym}{digits}{tail_chars}"
    elif arch == 3:
        pwd = f"{w_en}{w_vi}{sym}{digits_short}"
    elif arch == 4:
        pwd = f"{sym}{w_vi}{digits}{tail_chars}"
    elif arch == 5:
        w2 = random.choice(WORDS_VIET)
        pwd = f"{w_vi}{digits}{w2}{sym}"
    elif arch == 6:
        pwd = f"{w_en}{sym}{sym2}{digits}"
    elif arch == 7:
        w2 = random.choice(WORDS_VIET)
        pwd = f"{w_vi}{sym}{w2}{sym2}{digits_short}"
    elif arch == 8:
        part1 = "".join(random.choices(string.ascii_uppercase, k=random.randint(2, 3)))
        part2 = "".join(random.choices(string.ascii_lowercase, k=random.randint(3, 4)))
        part3 = "".join(random.choices(string.digits, k=random.randint(3, 4)))
        pwd = f"{part1}{part2}{sym}{part3}"
    elif arch == 9:
        pwd = f"{w_vi}{birth_year}{sym}{tail_chars}"
    elif arch == 10:
        pwd = f"{w_en}{digits}{sym}{tail_chars}"
    elif arch == 11:
        pwd = f"{w_vi.lower()}_{w_en.lower()}{digits_short}{sym}"
    elif arch == 12:
        tag = "".join(random.choices(string.ascii_uppercase, k=random.randint(2, 3)))
        pwd = f"{tag}{w_vi}{digits}{sym}"
    elif arch == 13:
        pwd = f"{w_en}{sym}{digits_short}{sym2}{w_vi}"
    elif arch == 14:
        pwd = f"{w_vi}{sym}{birth_year}{tail_chars}"
    elif arch == 15:
        w2 = random.choice(WORDS_VIET)
        pwd = f"{w_en.lower()}{sym}{w2}{digits}"
    else:
        chars = random.choices(string.ascii_letters, k=8)
        nums = random.choices(string.digits, k=4)
        combined = chars + nums + [sym]
        random.shuffle(combined)
        pwd = "".join(combined)

    if len(pwd) < 10:
        pwd = f"{pwd}{random.randint(10, 99)}"
    return pwd


def get_password(password_config: Optional[Dict[str, Any]] = None) -> str:
    if password_config and password_config.get("type") == "fixed" and password_config.get("value"):
        return password_config["value"]
    return generate_random_password()



from ui.colors import GREEN, RED, WHITE, YELLOW, CYAN, EKL, LINE
from core.settings_manager import load_settings


# Prompt user for password preference or use settings configuration
def select_password_config(config_state=None, render_callback=None):
    settings = load_settings()
    pwd_cfg = settings.get("password_settings", {})
    ask_pwd = pwd_cfg.get("ask_for_password", True)
    def_pwd = str(pwd_cfg.get("default_password", "")).strip()
    use_random = pwd_cfg.get("use_random_password", True)

    # Check if configured to skip interactive prompt
    if not ask_pwd:
        if def_pwd:
            if config_state is not None:
                config_state["password"] = f"Fixed ({def_pwd}) [Settings]"
            if render_callback:
                render_callback()
            return {"type": "fixed", "value": def_pwd}
        elif use_random:
            if config_state is not None:
                config_state["password"] = "Random Password [Settings]"
            if render_callback:
                render_callback()
            return {"type": "random", "value": None}

    if render_callback:
        render_callback()

    print(f" {GREEN}[{RED}01{GREEN}] Random Password {WHITE}(Auto-generated strong password)")
    print(f" {GREEN}[{RED}02{GREEN}] Custom / Fixed Password {WHITE}(Use a specific password for all accounts)")
    if def_pwd:
        print(f" {GREEN}[{RED}03{GREEN}] Use Saved Password {WHITE}({def_pwd})")
    print(f"{LINE}")

    while True:
        try:
            choice = input(f" {GREEN}[{RED}?{GREEN}] Select Password Type (1/2) {EKL} ").strip()
            if choice == "1" or not choice:
                if config_state is not None:
                    config_state["password"] = "Random Password"
                if render_callback:
                    render_callback()
                return {"type": "random", "value": None}
            elif choice == "2":
                while True:
                    custom_pwd = input(f" {GREEN}[{RED}?{GREEN}] Enter Custom Password {EKL} ").strip()
                    if len(custom_pwd) >= 6:
                        if config_state is not None:
                            config_state["password"] = f"Custom ({custom_pwd})"
                        if render_callback:
                            render_callback()
                        return {"type": "fixed", "value": custom_pwd}
                    print(f"{RED} Password must be at least 6 characters!")
            elif choice == "3" and def_pwd:
                if config_state is not None:
                    config_state["password"] = f"Saved ({def_pwd})"
                if render_callback:
                    render_callback()
                return {"type": "fixed", "value": def_pwd}
            else:
                print(f"{RED} Invalid choice! Enter 1 or 2.")
        except KeyboardInterrupt:
            raise
        except Exception:
            pass
