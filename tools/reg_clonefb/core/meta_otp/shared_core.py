import os
import sys
import threading
import itertools
import random
import string

from core.meta_otp.user_agents import *
from core.meta_otp.file_reader import file_input, load_settings
from core.meta_otp.proxy_manager import get_proxy_list
from core.meta_otp.config import *

# Thread-safe locks
print_lock = threading.Lock()
counter_lock = threading.Lock()
file_lock = threading.Lock()

# Global counters
total_checked = 0
total_success = 0
total_failed = 0
total_error = 0

def reset_counters():
    global total_checked, total_success, total_failed, total_error
    total_checked = 0
    total_success = 0
    total_failed = 0
    total_error = 0


# UI helpers

def get_status_bar():
    return f"\r{GREEN}[{WHITE}OTP{GREEN}] {WHITE}CHECKED:-{total_checked}{CYAN}|{GREEN}SUCCESS:-{total_success}{CYAN}|{YELLOW}FAILED:-{total_failed}{CYAN}|{RED}ERROR:-{total_error}"

def safe_print(text):
    """Thread-safe print that preserves the status bar at the bottom."""
    with print_lock:
        sys.stdout.write('\r' + ' ' * 80 + '\r')
        try:
            sys.stdout.write(str(text) + '\n')
        except UnicodeEncodeError:
            sys.stdout.write(str(text).encode('utf-8', errors='ignore').decode('utf-8') + '\n')
        sys.stdout.write(get_status_bar())
        sys.stdout.flush()

def update_counter(status, number=None, message=None, color=None):
    """Update global counters and optionally print a status message."""
    global total_checked, total_success, total_failed, total_error
    with counter_lock:
        if status == "success":
            total_success += 1
        elif status == "failed":
            total_failed += 1
        elif status == "error":
            total_error += 1
        total_checked += 1

    if message and number:
        if not color: color = WHITE
        safe_print(f"{color} {message} {number}")
    elif message:
        if not color: color = WHITE
        safe_print(f"{color} {message}")
    else:
        with print_lock:
            sys.stdout.write(get_status_bar())
            sys.stdout.flush()


# Utility functions

def generate_s_val():
    """Generate a random __s parameter value."""
    return ':'.join(''.join(random.choices(string.ascii_lowercase + string.digits, k=6)) for _ in range(3))

def generate_qpl_join_id():
    """Generate a random QPL join ID."""
    return ''.join(random.choices('0123456789abcdef', k=17))

def generate_password(length=None):
    """Generate a random password for registration."""
    if length is None:
        length = random.randint(8, 12)
    pwd_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%"
    return ''.join(random.choice(pwd_chars) for _ in range(length))

def save_remaining_numbers(remaining_numbers):
    """Update Number_List.txt with remaining unprocessed numbers."""
    with file_lock:
        with open("Number_List.txt", "w") as f_out:
            for num in remaining_numbers:
                f_out.write(num + "\n")

def save_failed_number(number):
    """Append a failed number to Failed_Numbers.txt."""
    with file_lock:
        with open("Failed_Numbers.txt", "a") as f_out:
            f_out.write(str(number) + "\n")

def save_success_number(number):
    """Append a successful number to Success_Numbers.txt."""
    with file_lock:
        with open("Success_Numbers.txt", "a") as f_out:
            f_out.write(str(number) + "\n")


# Setup menus

def setup_user_agent(setting_key="api_settings"):
    """Interactive user-agent profile selection menu."""
    clear_logo()

    ua_map = {
        '1': get_android_4_6, '01': get_android_4_6,
        '2': get_android_7_11, '02': get_android_7_11,
        '3': get_android_12_15, '03': get_android_12_15,
        '4': get_ios_old, '04': get_ios_old,
        '5': get_ios_medium, '05': get_ios_medium,
        '6': get_ios_new, '06': get_ios_new,
        '7': get_ipad_old, '07': get_ipad_old,
        '8': get_ipad_new, '08': get_ipad_new,
        '9': get_kaios, '09': get_kaios,
        '10': get_windows_phone,
        '11': get_blackberry,
    }

    settings = load_settings(setting_key)
    ua_set = settings.get("user_agent_settings", {})
    ask_ua = ua_set.get("ask_for_user_agent", True)
    def_ua = str(ua_set.get("default_user_agent", "none")).strip().lower()

    if def_ua in ua_map:
        choice = def_ua
        print(f"{GREEN} [{RED}●{GREEN}] Default User-Agent Selected {EKL} {choice}")
    else:
        if ask_ua:
            print(f" {opt_labels[0]} Android 4-6 (Old)")
            print(f" {opt_labels[1]} Android 7-11 (Mid)")
            print(f" {opt_labels[2]} Android 12-15 (New)")
            print(f" {opt_labels[3]} iOS Old (10-12)")
            print(f" {opt_labels[4]} iOS Medium (13-15)")
            print(f" {opt_labels[5]} iOS New (16-18)")
            print(f" {opt_labels[6]} iPad Old (10-13)")
            print(f" {opt_labels[7]} iPad New (15-18)")
            print(f" {opt_labels[8]} KaiOS")
            print(f" {opt_labels[9]} Windows Phone")
            print(f" {opt_labels[10]} BlackBerry")
            print(f"{LINE}")
            choice = input(f"{GREEN} [{RED}●{GREEN}] Select User-Agent {EKL} ").strip()
        else:
            choice = '1'
            print(f"{GREEN} [{RED}●{GREEN}] Using Profile {choice} due to config")

    ua_func = ua_map.get(choice)
    if not ua_func:
        print(f"{RED} Invalid choice!")
        input(f"{WHITE} Press Enter to exit...")
        return None
    return ua_func

def setup_proxies(setting_key="api_settings"):
    """Load proxy list and create round-robin iterator."""
    clear_logo()
    PROXY_LIST = get_proxy_list(settings_key=setting_key)
    PROXY_ITERATOR = itertools.cycle(PROXY_LIST) if PROXY_LIST else None

    if PROXY_LIST:
        print(f"{GREEN} [{RED}●{GREEN}] Total Proxies {EKL} {len(PROXY_LIST)}")
    else:
        print(f"{YELLOW} No Proxy configured. Will continue without proxy.")

    return PROXY_LIST, PROXY_ITERATOR

def setup_browser(setting_key="selenium_settings"):
    """Interactive browser selection menu for Selenium mode."""
    clear_logo()
    settings = load_settings(setting_key)
    browser_set = settings.get("browser_settings", {})
    ask_browser = browser_set.get("ask_for_browser", True)
    def_browser = str(browser_set.get("default_browser", "chrome")).strip().lower()

    if not ask_browser:
        choice = def_browser
        print(f"{GREEN} [{RED}●{GREEN}] Default Browser Selected {EKL} {choice}")
    else:
        print(f" {opt_labels[0]} Google Chrome (Default)")
        print(f" {opt_labels[1]} Microsoft Edge")
        print(f" {opt_labels[2]} Mozilla Firefox")
        print(f" {opt_labels[3]} Brave Browser")
        print(f" {opt_labels[4]} Opera Browser\n{LINE}")

        choice = input(f"{GREEN} [{RED}●{GREEN}] Select Browser {EKL} ").strip()

    if choice in ['2', '02', 'edge']:
        return 'edge'
    elif choice in ['3', '03', 'firefox']:
        return 'firefox'
    elif choice in ['4', '04', 'brave']:
        return 'brave'
    elif choice in ['5', '05', 'opera']:
        return 'opera'
    else:
        return 'chrome'

def setup_headless_mode(setting_key="selenium_settings"):
    """Interactive headless mode selection."""
    clear_logo()
    settings = load_settings(setting_key)
    headless_set = settings.get("headless_settings", {})
    ask_headless = headless_set.get("ask_for_headless", True)
    def_headless = headless_set.get("default_headless", False)

    if not ask_headless:
        print(f"{GREEN} [{RED}●{GREEN}] Headless Mode {EKL} {def_headless} (From Config)")
        return bool(def_headless)
    else:
        print(f" {opt_labels[0]} Visible (UI Open)")
        print(f" {opt_labels[1]} Headless (Background)\n{LINE}")
        h_choice = input(f"{GREEN} [{RED}●{GREEN}] Select Mode {EKL} ").strip()
        return True if h_choice in ['2', '02'] else False

def setup_start_route(setting_key="selenium_settings"):
    """Choose between starting from Meta AI homepage or auth page directly."""
    clear_logo()
    settings = load_settings(setting_key)
    route_set = settings.get("route_settings", {})
    ask_route = route_set.get("ask_for_route", True)
    try:
        def_route = int(route_set.get("default_route", 0))
    except:
        def_route = 0

    if not ask_route:
        print(f"{GREEN} [{RED}●{GREEN}] Start Route {EKL} {def_route} (From Config)")
        return def_route
    else:
        print(f" {opt_labels[0]} Start from Home (Default)")
        print(f" {opt_labels[1]} Start from Auth Page\n{LINE}")
        route_choice = input(f"{GREEN} [{RED}●{GREEN}] Select Starting Route {EKL} ").strip()
        return 1 if route_choice in ['2', '02'] else 0

def setup_work_mode(setting_key="selenium_settings"):
    """Choose between Both / Resend-Only / Create-Only work modes."""
    clear_logo()
    settings = load_settings(setting_key)
    work_set = settings.get("work_mode", {})
    ask_mode = work_set.get("ask_for_mode", True)
    try:
        def_mode = int(work_set.get("default_mode", 0))
    except:
        def_mode = 0

    work_mode = def_mode
    if not ask_mode:
        print(f"{GREEN} [{RED}●{GREEN}] Work Mode {EKL} {def_mode} (From Config)")
    else:
        print(f" {opt_labels[0]} Both (Resend + Create)")
        print(f" {opt_labels[1]} Resend Only (Ignore Create New Account)")
        print(f" {opt_labels[2]} Create Only (Ignore Existing Accounts)\n{LINE}")
        wm = input(f"{GREEN} [{RED}●{GREEN}] Select Work Mode [Enter for Default] {EKL} ").strip()
        if wm in ['0', '1', '01']:
            work_mode = 0
        elif wm in ['2', '02']:
            work_mode = 1
        elif wm in ['3', '03']:
            work_mode = 2
    return work_mode

def setup_otp_resend(setting_key="api_settings"):
    """Configure OTP resend count."""
    clear_logo()
    settings = load_settings(setting_key)
    otp_set = settings.get("otp_settings", {})
    ask_resend = otp_set.get("ask_for_resend_count", True)
    try:
        def_resend = int(otp_set.get("default_resend_count", 1))
    except:
        def_resend = 1

    if not ask_resend:
        resend_count = def_resend
        print(f"{GREEN} [{RED}●{GREEN}] Resend OTP Count {EKL} {resend_count} (From Config)")
    else:
        print(f"{WHITE} How many times to Resend OTP? (0 to disable Resend)")
        r_inp = input(f"{GREEN} [{RED}●{GREEN}] Resend Count [Default: {def_resend}] {EKL} ").strip()
        try:
            resend_count = int(r_inp) if r_inp else def_resend
        except:
            resend_count = def_resend
            print(f"{RED} Invalid input. Using Default {EKL} {resend_count}")
        print(f"{GREEN} [{RED}●{GREEN}] Resend OTP Set to {EKL} {resend_count}")

    return resend_count

def setup_threads(setting_key="api_settings"):
    """Configure the number of worker threads."""
    settings = load_settings(setting_key)
    thread_set = settings.get("thread_settings", {})
    ask_threads = thread_set.get("ask_for_threads", True)
    try:
        def_threads = int(thread_set.get("default_threads", 20))
    except:
        def_threads = 20

    if not ask_threads:
        print(f"{GREEN} [{RED}●{GREEN}] Threads {EKL} {def_threads} (From Config)")
        return def_threads

    try:
        w_inp = input(f"{LINE}\n{GREEN} [{RED}●{GREEN}] Enter number of Threads/Workers [{def_threads}] {EKL} ").strip()
        if w_inp:
            return int(w_inp)
        else:
            return def_threads
    except:
        return def_threads

def display_final_summary():
    """Print the final processing summary after all numbers are done."""
    with print_lock:
        sys.stdout.write('\r' + ' ' * 80 + '\r')
        sys.stdout.flush()
    print(f"\n{LINE}")
    print(f"{GREEN} [{RED}●{GREEN}] {WHITE}Completed Processing {total_checked} Numbers.")
    print(f"{GREEN} [{RED}●{GREEN}] {GREEN}Total Success {EKL} {total_success}")
    print(f"{GREEN} [{RED}●{GREEN}] {YELLOW}Total Failed  {EKL} {total_failed}")
    print(f"{GREEN} [{RED}●{GREEN}] {RED}Total Error   {EKL} {total_error}")
    print(f"{LINE}")
    input(f"{WHITE} Press Enter to exit...")
