import os
import sys
import time
import random
import string
import re
from concurrent.futures import ThreadPoolExecutor

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from webdriver_manager.opera import OperaDriverManager

from core.meta_otp.file_reader import file_input
from core.meta_otp.shared_core import *
from core.meta_otp.proxy_tunnel import create_proxy_tunnel, init_extension_dir

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    os.system('')

# Cached driver path to avoid repeated downloads
cached_driver_path = None


def run():
    """Entry point for Selenium automation mode."""
    clear_logo()

    numbers = file_input("selenium_settings")
    if not numbers:
        input(f"{WHITE} Press Enter to exit...")
        return

    selected_browser = setup_browser("selenium_settings")
    is_headless = setup_headless_mode("selenium_settings")
    start_route = setup_start_route("selenium_settings")
    work_mode = setup_work_mode("selenium_settings")

    ua_func = setup_user_agent("selenium_settings")
    if not ua_func: return

    PROXY_LIST, PROXY_ITERATOR = setup_proxies("selenium_settings")
    resend_count = setup_otp_resend("selenium_settings")
    max_workers = setup_threads("selenium_settings")

    clear_logo()
    reset_counters()
    init_extension_dir()

    print(f"{GREEN} [{RED}●{GREEN}] Total Numbers  {EKL} {len(numbers)}")
    print(f"{GREEN} [{RED}●{GREEN}] Threads         {EKL} {max_workers}")
    print(f"{GREEN} [{RED}●{GREEN}] Proxies         {EKL} {len(PROXY_LIST) if PROXY_LIST else 'None'}")
    print(f"{LINE}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        remaining_numbers = list(numbers)

        def make_callback(n):
            def callback(future):
                with file_lock:
                    if n in remaining_numbers:
                        remaining_numbers.remove(n)
                save_remaining_numbers(remaining_numbers)
            return callback

        for num in numbers:
            proxy_data = next(PROXY_ITERATOR) if PROXY_ITERATOR else None
            current_proxy = proxy_data['proxy'] if proxy_data else None
            user_agent = ua_func()

            future = executor.submit(process_number, num, user_agent, current_proxy, resend_count, is_headless, selected_browser, start_route, work_mode)
            future.add_done_callback(make_callback(num))

    display_final_summary()


def create_driver(user_agent, proxy=None, headless=False, browser='chrome'):
    """Create and configure a Selenium WebDriver instance.
    Returns (driver, proxy_tunnel) tuple.
    """
    global cached_driver_path

    proxy_tunnel = None
    driver = None

    # Resolve proxy URL
    proxy_server_url = None
    if proxy:
        proxy_url = proxy.get('http', '').replace('http://', '')
        if proxy_url:
            if '@' in proxy_url:
                proxy_tunnel, local_port = create_proxy_tunnel(proxy_url)
                if proxy_tunnel and local_port:
                    proxy_server_url = f'http://127.0.0.1:{local_port}'
                else:
                    proxy_server_url = f'http://{proxy_url}'
            else:
                proxy_server_url = f'http://{proxy_url}'

    # Determine window size based on device type
    window_size = "500,600"
    if user_agent:
        mobile_keywords = ['Android', 'iPhone', 'iPad', 'Mobile', 'Windows Phone', 'KAIOS', 'BB10', 'BlackBerry']
        if any(kw in user_agent for kw in mobile_keywords):
            window_size = "360,640"

    # Adjust user-agent string for non-Chrome browsers
    if user_agent and browser not in ['chrome', 'brave']:
        chrome_match = re.search(r'Chrome/([0-9]+)\.', user_agent)
        if chrome_match:
            c_maj = int(chrome_match.group(1))
            edge_ver = f"{c_maj}.0.{random.randint(1000, 3000)}.{random.randint(30, 200)}"
            opera_ver = f"{max(c_maj - 14, 60)}.0.{random.randint(3000, 5000)}.{random.randint(30, 150)}"
            ff_maj = str(max(c_maj, 90))
        else:
            edge_ver = f"{random.randint(100, 130)}.0.{random.randint(1000, 3000)}.{random.randint(30, 200)}"
            opera_ver = f"{random.randint(70, 100)}.0.{random.randint(3000, 5000)}.{random.randint(30, 150)}"
            ff_maj = str(random.randint(100, 130))

        if browser == 'edge':
            if 'Android' in user_agent:
                user_agent += f" EdgA/{edge_ver}"
            elif 'iPhone' in user_agent or 'iPad' in user_agent:
                user_agent += f" EdgiOS/{edge_ver}"
            else:
                user_agent += f" Edg/{edge_ver}"
        elif browser == 'opera':
            if 'Android' in user_agent:
                user_agent += f" OPR/{opera_ver}"
            elif 'iPhone' in user_agent or 'iPad' in user_agent:
                user_agent = user_agent.replace("Safari/", "OPT/")
            else:
                user_agent += f" OPR/{opera_ver}"
        elif browser == 'firefox':
            if 'Android' in user_agent:
                user_agent = re.sub(r'AppleWebKit/.*? \(KHTML, like Gecko\) Chrome/[0-9.]+ Mobile Safari/[0-9.]+', f'Gecko/{ff_maj}.0 Firefox/{ff_maj}.0', user_agent)
                user_agent = re.sub(r'AppleWebKit/.*? \(KHTML, like Gecko\) Chrome/[0-9.]+ Safari/[0-9.]+', f'Gecko/{ff_maj}.0 Firefox/{ff_maj}.0', user_agent)
            elif 'iPhone' in user_agent or 'iPad' in user_agent:
                user_agent += f" FxiOS/{ff_maj}.0"
            else:
                user_agent = re.sub(r'AppleWebKit/.*? \(KHTML, like Gecko\) Chrome/[0-9.]+ Safari/[0-9.]+', f'Gecko/20100101 Firefox/{ff_maj}.0', user_agent)

    # Common Chromium preferences
    chromium_prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "webrtc.ip_handling_policy": "disable_non_proxied_udp",
        "webrtc.multiple_routes_enabled": False,
        "webrtc.nonproxied_udp_enabled": False
    }

    os.environ['WDM_LOG'] = '7'

    # --- Chrome / Brave / Opera ---
    if browser in ['chrome', 'brave', 'opera']:
        options = ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        if user_agent:
            options.add_argument(f"user-agent={user_agent}")
        if proxy_server_url:
            options.add_argument(f'--proxy-server={proxy_server_url}')

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-features=DisableLoadExtensionCommandLineSwitch")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option("prefs", chromium_prefs)
        options.add_argument(f"--window-size={window_size}")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-infobars")
        options.add_argument("--mute-audio")

        if browser == 'chrome':
            if cached_driver_path is None:
                cached_driver_path = ChromeDriverManager().install()
            service = ChromeService(cached_driver_path)
            driver = webdriver.Chrome(service=service, options=options)

        elif browser == 'brave':
            possible_paths = [
                "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe",
                "C:/Program Files (x86)/BraveSoftware/Brave-Browser/Application/brave.exe",
                os.path.expanduser("~\\AppData\\Local\\BraveSoftware\\Brave-Browser\\Application\\brave.exe")
            ]
            brave_path = next((p for p in possible_paths if os.path.exists(p)), None)

            if not brave_path:
                safe_print(f"{RED} Brave browser not found in standard locations. Please install it or use Chrome.")
                return None, None

            options.binary_location = brave_path
            try:
                service = ChromeService(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
            except Exception as e:
                safe_print(f"{RED} Failed to launch Brave. Error: {e}")
                return None, None

        elif browser == 'opera':
            possible_paths = [
                os.path.expanduser("~\\AppData\\Local\\Programs\\Opera\\opera.exe"),
                os.path.expanduser("~\\AppData\\Local\\Programs\\Opera GX\\opera.exe"),
                "C:/Program Files/Opera/opera.exe",
                "C:/Program Files/Opera GX/opera.exe"
            ]
            opera_path = next((p for p in possible_paths if os.path.exists(p)), None)

            if not opera_path:
                safe_print(f"{RED} Opera browser not found in standard locations. Please install it or use Chrome.")
                return None, None

            options.binary_location = opera_path
            try:
                service = ChromeService(OperaDriverManager().install())
                options.add_argument('allow-elevated-browser')
                driver = webdriver.Chrome(service=service, options=options)
            except Exception as e:
                safe_print(f"{RED} Failed to launch Opera. Error: {e}")
                return None, None

        # Hide webdriver flag
        try:
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                """
            })
        except: pass

    # --- Edge ---
    elif browser == 'edge':
        options = EdgeOptions()
        if headless:
            options.add_argument("--headless=new")
        if user_agent:
            options.add_argument(f"user-agent={user_agent}")
        if proxy_server_url:
            options.add_argument(f'--proxy-server={proxy_server_url}')

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option("prefs", chromium_prefs)
        options.add_argument(f"--window-size={window_size}")
        options.add_argument("--disable-notifications")
        options.add_argument("--mute-audio")

        try:
            service = EdgeService(EdgeChromiumDriverManager().install())
            driver = webdriver.Edge(service=service, options=options)
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                """
            })
        except Exception as e:
            safe_print(f"{RED} Failed to launch Edge. Error: {e}")
            return None, None

    # --- Firefox ---
    elif browser == 'firefox':
        options = FirefoxOptions()
        if headless:
            options.add_argument("--headless")

        if user_agent:
            options.set_preference("general.useragent.override", user_agent)

        if proxy_server_url:
            proxy_url_clean = proxy_server_url.replace('http://', '').replace('https://', '')
            if ':' in proxy_url_clean:
                ip, port = proxy_url_clean.split(':', 1)
                options.set_preference("network.proxy.type", 1)
                options.set_preference("network.proxy.http", ip)
                options.set_preference("network.proxy.http_port", int(port))
                options.set_preference("network.proxy.ssl", ip)
                options.set_preference("network.proxy.ssl_port", int(port))

        options.set_preference("dom.webdriver.enabled", False)
        options.set_preference('useAutomationExtension', False)
        options.set_preference("media.volume_scale", "0.0")
        options.set_preference("dom.webnotifications.enabled", False)

        width, height = map(int, window_size.split(','))
        options.add_argument(f"--width={width}")
        options.add_argument(f"--height={height}")

        try:
            service = FirefoxService(GeckoDriverManager().install())
            driver = webdriver.Firefox(service=service, options=options)
        except Exception as e:
            safe_print(f"{RED} Failed to launch Firefox. Error: {e}")
            return None, None

    return driver, proxy_tunnel


def wait_and_click(driver, by, value, timeout):
    """Wait for an element to be clickable and click it."""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
        try:
            element.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", element)
        return True
    except TimeoutException:
        return False

def wait_and_type(driver, by, value, text, timeout):
    """Wait for an input element and type text character by character."""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        element.clear()
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.0001, 0.0005))
        return True
    except TimeoutException:
        return False

def select_custom_dropdown(driver, label, value_str, number):
    """Select a value from Meta's custom combobox dropdown."""
    combo_xpath = f"//div[@role='combobox' and @aria-label='{label}']"
    try:
        combo_el = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, combo_xpath)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", combo_el)
        time.sleep(0.2)
        driver.execute_script("arguments[0].click();", combo_el)
        time.sleep(random.uniform(0.2, 0.5))

        option_xpath = f"//div[@role='listbox']//div[@role='option']//*[text()='{value_str}' or .='{value_str}']"
        opt_el = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, option_xpath)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", opt_el)
        time.sleep(0.2)
        driver.execute_script("arguments[0].click();", opt_el)
        time.sleep(random.uniform(0.2, 0.5))
    except Exception as e:
        safe_print(f"{YELLOW}  Failed to select {label}: {str(e)[:30]} [{number}]")


def process_number(number, user_agent, proxy=None, resend_count=1, headless=False, browser='chrome', start_route=0, work_mode=0):
    """Core Selenium logic: automate Meta AI registration flow to trigger OTP."""
    driver = None
    proxy_tunnel = None
    try:
        driver, proxy_tunnel = create_driver(user_agent, proxy, headless, browser)
        if not driver:
            update_counter("error", number, f"Driver Error!", RED)
            save_failed_number(number)
            return

        driver.set_page_load_timeout(30)

        # Debug: verify proxy IP
        if proxy:
            try:
                driver.set_page_load_timeout(15)
                driver.get("http://httpbin.org/ip")
                ip_text = driver.find_element(By.TAG_NAME, "body").text
                safe_print(f"{GREEN} Proxy IP Log: {ip_text} [{number}]")
            except Exception:
                pass
            finally:
                driver.set_page_load_timeout(30)

        # Step 1: Navigate to starting URL
        if start_route == 1:
            start_url = "https://auth.meta.com/?csi=56f2abe3-3f4f-49e7-a199-6e874d5640ff&redirect_uri=https%3A%2F%2Fauth.meta.com%2Foidc%2F%3Fapp_id%3D391894423991568&source_app_id=391894423991568&rcs=ATksTWCb8M27sFcW13DVJlba-Qz7ih5eZ-3TO3fajnNCSoqSSsNmQchnWdMYlad0IJ8y5bZgCQNvgzOUr2kbzwpllFMzq22yS_-EJPDLjJ86-5WFLQMQjq2aim3_Go1jBZajuq-kZ2bujti-DsnQzPrHdvHWl-riU4SKQkiXNVzy00n3V6SKjwYvcDE"
        else:
            start_url = "https://www.meta.ai/"

        try:
            driver.get(start_url)
        except Exception:
            update_counter("error", number, f"Site load timeout!", RED)
            save_failed_number(number)
            return

        time.sleep(random.uniform(1.5, 2.5))

        # Wait for page to fully load
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH,
                    "//input[@autocomplete='username' or @inputmode='email' or @name='contact_point'] | //div[@id='mount_0_0_2K'] | //div[contains(@class, 'x9f619')] | //a[contains(@href, '/login') or contains(@href, '/signup')] | //span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sign')]"
                ))
            )
            safe_print(f"{GREEN} Site visit Success! [{number}]")
        except TimeoutException:
            update_counter("error", number, f"Site did not load correctly!", RED)
            save_failed_number(number)
            return

        time.sleep(random.uniform(0.5, 1.5))

        # Step 2: Click Sign Up (only from Meta AI homepage)
        if start_route == 0:
            signup_selectors = [
                "//span[translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='sign up']",
                "//a[contains(@href, '/signup')]",
                "//span[contains(text(), 'Sign') and contains(text(), 'up')]",
                "//span[contains(text(), 'Sign') and contains(text(), 'Up')]",
                "//div[@role='button' and .//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sign')]]",
            ]
            clicked_signup = False
            for sel in signup_selectors:
                if wait_and_click(driver, By.XPATH, sel, timeout=5):
                    clicked_signup = True
                    break
            if not clicked_signup:
                safe_print(f"{YELLOW} Sign Up button not found, trying to continue... [{number}]")

            time.sleep(random.uniform(0.5, 1.5))

        # Step 3: Click "Use mobile number or email address"
        use_mobile_btn = "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'mobile number') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'email address') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sign up with email')]"
        wait_and_click(driver, By.XPATH, use_mobile_btn, timeout=12)
        time.sleep(random.uniform(0.5, 1))

        # Step 4: Enter phone number
        phone_input_xpath = "//input[@autocomplete='username' or @inputmode='email' or @name='contact_point' or @type='text' or @type='email']"
        if not wait_and_type(driver, By.XPATH, phone_input_xpath, number, timeout=15):
            update_counter("error", number, "Phone input not found!", RED)
            save_failed_number(number)
            return

        next_btn_xpath = "//div[@role='button' and @tabindex='0' and not(@aria-disabled='true') and .//span[text()='Next' or .='Next']]"
        if not wait_and_click(driver, By.XPATH, next_btn_xpath, timeout=5):
            safe_print(f"{YELLOW} Failed to click Next button [{number}]")

        time.sleep(random.uniform(0.5, 1.5))

        # Detect which page we landed on
        forgot_xpath = "//div[@role='button' and @tabindex='0' and not(@aria-disabled='true') and .//span[normalize-space(text())='Forgotten password?' or normalize-space(text())='Forgot password?']]"
        resend_xpath = "//div[@role='button' and @tabindex='0' and (contains(., 'Resend code') or contains(., 'Send code again'))]"
        alt_resend_xpath = "//div[@role='button' and @tabindex='0' and not(@aria-disabled='true') and .//span[normalize-space(text())='Enter password instead']]"
        create_xpath = "//span[normalize-space(text())='Create new account']"

        page_detected = None
        end_time = time.time() + 10
        while time.time() < end_time:
            if driver.find_elements(By.XPATH, forgot_xpath):
                page_detected = 'forgot'
                break
            if driver.find_elements(By.XPATH, f"{resend_xpath} | {alt_resend_xpath}"):
                page_detected = 'resend'
                break
            if driver.find_elements(By.XPATH, create_xpath):
                page_detected = 'create'
                break
            time.sleep(0.5)

        # Handle existing account flow
        if page_detected == 'forgot':
            if work_mode == 2:
                update_counter("failed", number, "Ignored: Existing account found (Create Only Mode)", YELLOW)
                save_failed_number(number)
                return
            if wait_and_click(driver, By.XPATH, forgot_xpath, timeout=5):
                safe_print(f"{GREEN} Successfully clicked 'Forgotten password?' [{number}]")
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, f"{resend_xpath} | {alt_resend_xpath}"))
                    )
                    page_detected = 'resend'
                except TimeoutException:
                    update_counter("error", number, "Resend page not found after forgot pass", RED)
                    save_failed_number(number)
                    return
            else:
                update_counter("error", number, "Failed to click Forgotten password", RED)
                save_failed_number(number)
                return

        if page_detected == 'resend':
            if work_mode == 2:
                update_counter("failed", number, "Ignored: Existing account found (Create Only Mode)", YELLOW)
                save_failed_number(number)
                return
            time.sleep(random.uniform(1.5, 2))
            for r_idx in range(resend_count):
                if wait_and_click(driver, By.XPATH, resend_xpath, timeout=5):
                    safe_print(f"{GREEN} Successfully clicked Resend code ({r_idx+1}/{resend_count}) [{number}]")
                else:
                    safe_print(f"{YELLOW} Failed to click Resend code [{number}]")

                if r_idx < resend_count - 1:
                    time.sleep(random.uniform(2, 3))

            time.sleep(random.uniform(2.5, 3.5))
            update_counter("success", number, "Sent OTP for existing account", GREEN)
            save_success_number(number)
            return

        if work_mode == 1:
            update_counter("failed", number, "Ignored: Create new account required (Resend Only Mode)", YELLOW)
            save_failed_number(number)
            return

        # Step 5: Click "Create new account"
        create_account_xpath = "//span[text()='Create new account']"
        if not wait_and_click(driver, By.XPATH, create_account_xpath, timeout=10):
            update_counter("error", number, "Create new account button not found", RED)
            save_failed_number(number)
            return

        time.sleep(random.uniform(0.5, 1.5))

        # Step 6: Fill date of birth
        current_year = time.localtime().tm_year
        dob_year = random.randint(current_year - 35, current_year - 18)
        dob_month = random.randint(1, 12)
        dob_day = random.randint(1, 28)

        month_names = ["January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]

        select_custom_dropdown(driver, "Select day", str(dob_day), number)
        select_custom_dropdown(driver, "Select month", month_names[dob_month - 1], number)
        select_custom_dropdown(driver, "Select year", str(dob_year), number)

        wait_and_click(driver, By.XPATH, next_btn_xpath, timeout=5)
        time.sleep(random.uniform(2, 3))

        # Step 7: Enter password
        password = generate_password()

        pwd_input_xpath = "//input[@type='password' or @name='password']"
        if not wait_and_type(driver, By.XPATH, pwd_input_xpath, password, timeout=10):
            update_counter("error", number, "Password input not found!", RED)
            save_failed_number(number)
            return

        wait_and_click(driver, By.XPATH, next_btn_xpath, timeout=5)
        time.sleep(random.uniform(0.5, 1.5))

        # Click Confirm button
        confirm_btn_xpaths = [
            "//div[@role='button' and @tabindex='0' and not(@aria-disabled='true') and .//span[text()='Confirm' or .='Confirm']]",
            "//div[@role='button' and @tabindex='0' and normalize-space(.)='Confirm']",
            "//span[text()='Confirm']/ancestor::div[@role='button' and @tabindex='0']"
        ]

        for xpath in confirm_btn_xpaths:
            if wait_and_click(driver, By.XPATH, xpath, timeout=5):
                break

        time.sleep(random.uniform(0.5, 1.5))

        # Check if we reached OTP verification page
        otp_xpath = "//input[@autocomplete='one-time-code']"
        is_otp_page = False
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, otp_xpath)))
            is_otp_page = True
        except TimeoutException:
            pass

        if is_otp_page:
            update_counter("success", number, f"Registration Successful! OTP Sent!", GREEN)
            save_success_number(number)

            # Step 8: OTP resend loop
            if resend_count > 0:
                for r_idx in range(resend_count):
                    resend_btns = [
                        "//div[@role='button' and @tabindex='0' and not(@aria-disabled='true') and .//span[text()='Send code again']]",
                        "//div[@role='button' and @tabindex='0' and .//span[text()='Send code again']]",
                        "//span[text()='Send code again']/ancestor::div[@role='button' and @tabindex='0']"
                    ]

                    clicked_resend = False
                    for rb in resend_btns:
                        if wait_and_click(driver, By.XPATH, rb, timeout=3):
                            clicked_resend = True
                            break

                    if clicked_resend:
                        safe_print(f"{GREEN} OTP Resend {r_idx+1}/{resend_count} Clicked! [{number}]")

                        # Check for rate limit popup
                        try:
                            error_xpath = "//*[contains(text(), \"You've requested too many codes\") or contains(text(), 'Try again later')]"
                            popup = WebDriverWait(driver, 3).until(
                                EC.presence_of_element_located((By.XPATH, error_xpath))
                            )
                            if popup.is_displayed():
                                safe_print(f"{YELLOW} Rate limit error popup detected! Skipping further resends. [{number}]")
                                break
                        except TimeoutException:
                            pass

                        time.sleep(random.uniform(2, 3))
                    else:
                        safe_print(f"{YELLOW} OTP Resend button not found! Skipping further resends. [{number}]")
                        break

                    if r_idx < resend_count - 1:
                        time.sleep(random.uniform(1, 2))
            else:
                time.sleep(random.uniform(2, 3))

        else:
            update_counter("failed", number, "Did not reach OTP verification page!", RED)
            save_failed_number(number)

    except Exception as e:
        update_counter("error", number, f"Unexpected Selenium error: {str(e)[:30]}...", RED)
        save_failed_number(number)
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        if proxy_tunnel:
            try:
                proxy_tunnel.stop()
            except:
                pass
