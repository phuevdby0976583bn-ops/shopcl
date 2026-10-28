import os
import sys
import time
import random
import string
import uuid
import requests
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs

from core.meta_otp.phone_loader import read_numbers
from core.meta_otp.file_reader import file_input
from core.meta_otp.token_extractor import extract_tokens
from core.meta_otp.shared_core import *

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    os.system('')


def run():
    """Entry point for API automation mode."""
    clear_logo()
    numbers = file_input("api_settings")
    if not numbers:
        input(f"{WHITE} Press Enter to exit...")
        return

    ua_func = setup_user_agent("api_settings")
    if not ua_func: return

    PROXY_LIST, PROXY_ITERATOR = setup_proxies("api_settings")
    resend_count = setup_otp_resend("api_settings")
    max_workers = setup_threads("api_settings")

    clear_logo()
    reset_counters()
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

            future = executor.submit(process_number, num, user_agent, current_proxy, resend_count)
            future.add_done_callback(make_callback(num))

    display_final_summary()


def generate_random_username():
    """Generate a random username for Meta registration."""
    p1 = ''.join(random.choices(string.ascii_lowercase, k=random.randint(2, 4)))
    p1 += ''.join(random.choices(string.digits, k=random.randint(1, 3)))
    p2 = ''.join(random.choices(string.ascii_lowercase, k=random.randint(1, 2)))
    p2 += ''.join(random.choices(string.digits, k=random.randint(1, 2)))
    p2 += ''.join(random.choices(string.ascii_lowercase, k=random.randint(2, 4)))
    p3 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(3, 6)))
    p1 = ''.join(random.sample(p1, len(p1)))
    p2 = ''.join(random.sample(p2, len(p2)))
    p3 = ''.join(random.sample(p3, len(p3)))
    return f"{p1}_{p2}_{p3}"


def strip_json_prefix(text):
    """Remove Facebook's 'for (;;);' anti-hijacking prefix from JSON responses."""
    if text.startswith("for (;;);"):
        return text[len("for (;;);"):]
    return text


def build_common_params(hs, rev, s_val, hsi, dyn, csr, comet_req, lsd, jazoest, spin_b, spin_t,
                        ccg="GOOD", hsdp="", hblp="", sjsp=""):
    """Build the common Facebook API form parameters."""
    return {
        '__user': '0',
        '__a': '1',
        '__hs': hs,
        'dpr': '2',
        '__ccg': ccg,
        '__rev': rev,
        '__s': s_val,
        '__hsi': hsi,
        '__dyn': dyn,
        '__csr': csr,
        '__hsdp': hsdp,
        '__hblp': hblp,
        '__sjsp': sjsp,
        '__comet_req': comet_req,
        'lsd': lsd,
        'jazoest': jazoest,
        '__spin_r': rev,
        '__spin_b': spin_b,
        '__spin_t': spin_t,
        '__jssesw': '1',
    }


def process_number(number, user_agent, proxy=None, resend_count=1):
    """Core API logic: navigate Meta AI registration flow to trigger OTP."""
    try:
        session = requests.Session()
        if proxy:
            session.proxies.update(proxy)

        # Detect platform from user-agent
        is_mobile = '?0'
        platform = '"Windows"'
        if 'Android' in user_agent:
            is_mobile, platform = '?1', '"Android"'
        elif 'iPhone' in user_agent or 'iPad' in user_agent:
            is_mobile, platform = '?1', '"iOS"'
        elif 'Windows Phone' in user_agent:
            is_mobile, platform = '?1', '"Windows"'
        elif 'KAIOS' in user_agent or 'Mobile' in user_agent:
            is_mobile = '?1'

        base_headers = {
            'accept-language': 'en-US,en;q=0.8',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Brave";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': is_mobile,
            'sec-ch-ua-platform': platform,
            'sec-gpc': '1',
            'user-agent': user_agent,
        }

        api_headers = {
            **base_headers,
            'accept': '*/*',
            'content-type': 'application/x-www-form-urlencoded',
            'priority': 'u=1, i',
            'sec-ch-ua-full-version-list': '"Not:A-Brand";v="99.0.0.0", "Brave";v="145.0.0.0", "Chromium";v="145.0.0.0"',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform-version': '"19.0.0"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'x-asbd-id': '359341',
        }

        page_headers = {
            **base_headers,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'priority': 'u=0, i',
            'referer': 'https://www.google.com/',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'cross-site',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
        }

        # Step 1: Visit meta.ai (with retry)
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                response = session.get("https://www.meta.ai/", headers=page_headers, allow_redirects=True, timeout=15)
            except requests.exceptions.RequestException as req_err:
                if attempt == max_retries:
                    update_counter("error", number, f"meta.ai request failed: {req_err}", RED)
                    save_failed_number(number)
                    return
                time.sleep(2)
                continue

            if response.status_code == 403:
                # Handle Cloudflare-style challenge
                challenge_match = re.search(r"fetch\('(/__rd_verify_[^']+)'\s*,", response.text)
                if challenge_match:
                    challenge_url = f"https://www.meta.ai{challenge_match.group(1)}"
                    challenge_headers = {
                        **base_headers,
                        'accept': '*/*',
                        'origin': 'https://www.meta.ai',
                        'priority': 'u=1, i',
                        'referer': 'https://www.meta.ai/',
                        'sec-fetch-dest': 'empty',
                        'sec-fetch-mode': 'cors',
                        'sec-fetch-site': 'same-origin',
                    }
                    session.post(challenge_url, headers=challenge_headers, timeout=15)
                else:
                    safe_print(f"{YELLOW} Challenge URL Not Found! [{number}]")
                    return

                page_headers_retry = {
                    **base_headers,
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'cache-control': 'max-age=0',
                    'priority': 'u=0, i',
                    'referer': 'https://www.meta.ai/',
                    'sec-fetch-dest': 'document',
                    'sec-fetch-mode': 'navigate',
                    'sec-fetch-site': 'same-origin',
                    'upgrade-insecure-requests': '1',
                }
                try:
                    response = session.get("https://www.meta.ai/", headers=page_headers_retry, allow_redirects=True, timeout=15)
                except:
                    pass

                if response.status_code == 200:
                    break
            elif response.status_code == 403:
                safe_print(f"{YELLOW} [RATE LIMIT] IP Blocked (403)! [{number}]")
                continue
            elif response.status_code == 200:
                break
            else:
                break

        if response.status_code != 200:
            update_counter("error", number, "meta.ai visit failed!", RED)
            save_failed_number(number)
            return

        safe_print(f"{GREEN} ✅ meta.ai visit Success! [{number}]")

        # Extract tokens from homepage
        html = response.text
        tokens = extract_tokens(html, session_cookies=session.cookies)
        lsd = tokens['lsd']
        rev = tokens['rev']
        hsi = tokens['hsi']
        spin_b = tokens['spin_b']
        spin_t = tokens['spin_t']
        hs = tokens['hs']
        comet_req = tokens['comet_req']
        jazoest = tokens['jazoest']

        waterfall_id = str(uuid.uuid4())
        s_val = generate_s_val()
        qpl_id = "947263943"
        dyn = "7xeUjG1mxu1syUqxemh0no6u5U4e2C1vzEdE98K360CEbo1nEhw2nVEtwMw6ywaq221FwpUO0n24oaEnxO0Bo7O2l0Fwqo31w9O1lwlE-U2zxe2GewbS361qw82dUlwhE5m1pwg8fU1ck9zo2NwkQ0Lo6-m362WE3Gwxyo6O2G3W1nwOwbWEb8uwm83Ywgo6218wkE3PwiE6S"
        csr = ""

        # Step 2: Fetch OIDC redirect URI
        step2_headers = {
            **api_headers,
            'origin': 'https://www.meta.ai',
            'referer': 'https://www.meta.ai/',
            'x-fb-lsd': lsd,
            'x-fb-qpl-active-flows': qpl_id,
        }

        step2_data = {
            'entrypoint': 'floating_login_button',
            'next_url': '/',
            'oidc_provider': 'frl',
            'waterfall_id': waterfall_id,
            **build_common_params(hs, rev, s_val, hsi, dyn, csr, comet_req, lsd, jazoest, spin_b, spin_t),
            '__req': 'b',
            '__crn': 'comet.kadabra.KadabraAssistantRoute',
            'qpl_active_flow_ids': qpl_id,
        }

        response = session.post('https://www.meta.ai/fetch_frl_oidc/', headers=step2_headers, data=step2_data, allow_redirects=False, timeout=15)

        step2_text = strip_json_prefix(response.text)

        try:
            step2_json = json.loads(step2_text)
            oidc_uri = step2_json.get("payload", {}).get("oidc_uri", "")
        except json.JSONDecodeError:
            oidc_uri = ""

        if not oidc_uri:
            oidc_match = re.search(r'"oidc_uri"\s*:\s*"([^"]+)"', response.text)
            if oidc_match:
                oidc_uri = oidc_match.group(1).replace("\\/", "/")

        if not oidc_uri:
            update_counter("error", number, "oidc_uri not found!", RED)
            save_failed_number(number)
            return

        # Step 3: Follow auth redirect
        step3_headers = {
            **base_headers,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.7',
            'priority': 'u=0, i',
            'referer': 'https://www.meta.ai/',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'cross-site',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
        }

        response = session.get(oidc_uri, headers=step3_headers, allow_redirects=True, timeout=15)

        if response.status_code != 200:
            update_counter("error", number, "auth redirect failed!", RED)
            save_failed_number(number)
            return

        auth_referer = response.url
        parsed_auth_url = urlparse(auth_referer)
        auth_params = parse_qs(parsed_auth_url.query)
        csi = auth_params.get('csi', [''])[0]
        auth_redirect_uri = auth_params.get('redirect_uri', [''])[0]

        # Extract auth page tokens
        auth_tokens = extract_tokens(response.text, session_cookies=session.cookies, default_comet_req="33")
        auth_lsd = auth_tokens['lsd']
        auth_rev = auth_tokens['rev']
        auth_hsi = auth_tokens['hsi']
        auth_spin_b = auth_tokens['spin_b']
        auth_spin_t = auth_tokens['spin_t']
        auth_hs = auth_tokens['hs']
        auth_comet_req = auth_tokens['comet_req']
        auth_jazoest = auth_tokens['jazoest']

        auth_dyn = "7xeUmwlEnwn8K2Wmh0no6u5U4e0yoW3q32360CEbo1nEhw2nVE4W099w8G1Dz81s8hwnU2lwv89k2C1Fwc60D82IzXwae4UaEW0Loco5G0zK1swa-0raazo7u0zE2ZwrU6C2q0XU6O1FwlU4a5Ue82dwtU1fE"
        auth_csr = ""
        auth_ccg = "GOOD"

        # Step 4: Check contact point availability
        s_val = generate_s_val()

        step4_headers = {
            **api_headers,
            'accept-language': 'en-US,en;q=0.7',
            'origin': 'https://auth.meta.com',
            'referer': auth_referer,
            'x-fb-lsd': auth_lsd,
        }

        step4_data = {
            'account_reg_info[birthday]': time.strftime('%Y-%m-%d'),
            'account_reg_info[device_id]': '',
            'account_reg_info[first_name]': '',
            'account_reg_info[has_youth_consent]': 'false',
            'account_reg_info[is_bootstrap_flow]': 'false',
            'account_reg_info[last_name]': '',
            'account_reg_info[pc_rendering_data]': '',
            'account_reg_info[phone_number]': number,
            'account_reg_info[registration_flow_id]': '',
            'allow_unconfirmed_email': 'false',
            'check_for_pre_registration_restrictions': 'true',
            'check_mma_account': 'false',
            'contact_point': number,
            'contact_point_type': 'PHONE_NUMBER',
            'reg_integrity': '',
            'skip_xapp_checks': 'false',
            'source_app_id': '391894423991568',
            **build_common_params(auth_hs, auth_rev, s_val, auth_hsi, auth_dyn, auth_csr,
                                  auth_comet_req, auth_lsd, auth_jazoest, auth_spin_b, auth_spin_t, auth_ccg),
            '__req': '1j',
        }

        response = session.post('https://auth.meta.com/api/check-contact-point-availability/', headers=step4_headers, data=step4_data, timeout=15)

        step4_text = strip_json_prefix(response.text)

        reg_integrity = ""
        try:
            step4_json = json.loads(step4_text)
            reg_integrity = step4_json.get("payload", {}).get("regIntegrity", "")
        except json.JSONDecodeError:
            pass

        if not reg_integrity:
            ri_match = re.search(r'"regIntegrity"\s*:\s*"([^"]+)"', response.text)
            if ri_match:
                reg_integrity = ri_match.group(1)

        # Extract contact point from response
        contact_point = ""
        try:
            contact_point = step4_json.get("payload", {}).get("contactPoint", "")
        except:
            pass
        if not contact_point:
            cp_match = re.search(r'"contactPoint"\s*:\s*"([^"]+)"', response.text)
            if cp_match:
                contact_point = cp_match.group(1)
        if not contact_point:
            contact_point = number if number.startswith('+') else '+' + number

        # Step 5: Submit date of birth
        current_year = time.localtime().tm_year
        dob_year = random.randint(current_year - 35, current_year - 18)
        dob_month = random.randint(1, 12)
        dob_day = random.randint(1, 28)
        dob = f"{dob_year}-{dob_month:02d}-{dob_day:02d}"

        s_val = generate_s_val()
        qpl_join_id = generate_qpl_join_id()

        step5_headers = {
            **api_headers,
            'origin': 'https://auth.meta.com',
            'referer': auth_referer,
            'x-fb-lsd': auth_lsd,
        }

        step5_data = {
            'caa_event_flow': 'ntf',
            'date_of_birth': dob,
            'first_name': '',
            'has_youth_consent': 'false',
            'isf': 'false',
            'last_name': '',
            'phone_number': contact_point,
            'qpl_join_id': qpl_join_id,
            'reg_integrity': reg_integrity,
            'source_app_id': '391894423991568',
            **build_common_params(auth_hs, auth_rev, s_val, auth_hsi, auth_dyn, auth_csr,
                                  auth_comet_req, auth_lsd, auth_jazoest, auth_spin_b, auth_spin_t, auth_ccg),
            '__req': '1c',
        }

        response = session.post('https://auth.meta.com/api/check-date-of-birth/', headers=step5_headers, data=step5_data, timeout=15)

        step5_text = strip_json_prefix(response.text)
        try:
            step5_json = json.loads(step5_text)
            if step5_json.get("error"):
                error_msg = step5_json.get("errorDescription", "Unknown error")
                update_counter("failed", number, f"Account already exists! {error_msg}", YELLOW)
                save_failed_number(number)
                return
            payload = step5_json.get("payload")
            if payload:
                new_ri = payload.get("regIntegrity", "")
                if new_ri:
                    reg_integrity = new_ri
        except json.JSONDecodeError:
            pass

        # Step 6: Submit password
        password = generate_password()
        formatted_password = f"#PWD_BROWSER:0:{int(time.time())}:{password}"

        s_val = generate_s_val()
        qpl_join_id = generate_qpl_join_id()

        step6_headers = {
            **api_headers,
            'origin': 'https://auth.meta.com',
            'referer': auth_referer,
            'x-fb-lsd': auth_lsd,
        }

        step6_data = {
            'contact_point': contact_point,
            'date_of_birth': dob,
            'name': '',
            'password': formatted_password,
            'qpl_join_id': qpl_join_id,
            **build_common_params(auth_hs, auth_rev, s_val, auth_hsi, auth_dyn, auth_csr,
                                  auth_comet_req, auth_lsd, auth_jazoest, auth_spin_b, auth_spin_t, auth_ccg),
            '__req': '1r',
        }

        response = session.post('https://auth.meta.com/api/check-password/', headers=step6_headers, data=step6_data, timeout=15)

        step6_text = strip_json_prefix(response.text)
        try:
            step6_json = json.loads(step6_text)
            if step6_json.get("error"):
                error_msg = step6_json.get("errorDescription", "Unknown error")
                update_counter("failed", number, f"Password step failed! {error_msg}", RED)
                save_failed_number(number)
                return
            payload = step6_json.get("payload")
            if payload:
                new_ri = payload.get("regIntegrity", "")
                if new_ri:
                    reg_integrity = new_ri
        except json.JSONDecodeError:
            pass

        # Step 7: Submit registration (triggers OTP)
        username = generate_random_username()
        s_val = generate_s_val()
        qpl_join_id = generate_qpl_join_id()

        step7_headers = {
            **api_headers,
            'origin': 'https://auth.meta.com',
            'referer': auth_referer,
            'x-fb-lsd': auth_lsd,
        }

        step7_data = {
            'client_consent_timestamp': str(int(time.time())),
            'display_name': '',
            'foa_import_source_name': '',
            'foa_import_source_obid': '',
            'nta_disclosures_summary_cms_id': '',
            'picture_source': '',
            'tos_cms_id': '957798449862312',
            'username': username,
            'consent_version': '',
            'contact_point': contact_point,
            'contact_point_type': 'PHONE_NUMBER',
            'csi': csi,
            'date_of_birth': dob,
            'device_id': '',
            'fb_encrypted_access_token': '',
            'fb_oidc_access_token': '',
            'first_name': '',
            'has_youth_consent': 'false',
            'ig_encrypted_access_token': '',
            'ig_encrypted_auth_header': '',
            'ig_oidc_access_token': '',
            'last_name': '',
            'opt_into_marketing': 'false',
            'password': formatted_password,
            'redirect_uri': auth_redirect_uri,
            'reg_integrity': reg_integrity,
            'should_save_credentials': 'true',
            'source_app_id': '391894423991568',
            'third_party_age_verification_id': '',
            'waterfall_id': waterfall_id,
            'caa_event_flow': 'ntf',
            'entry_point': 'login_home',
            'event_client_time': f'{time.time():.3f}',
            'is_kadabra_zero': 'false',
            'reg_navigation_flow_name': 'new_to_family_c50_r1',
            'regulation_jurisdiction': '["BD"]',
            'qpl_join_id': qpl_join_id,
            **build_common_params(auth_hs, auth_rev, s_val, auth_hsi, auth_dyn, auth_csr,
                                  auth_comet_req, auth_lsd, auth_jazoest, auth_spin_b, auth_spin_t, auth_ccg),
            '__req': '1k',
        }

        response = session.post('https://auth.meta.com/login/device-based/kadabra-register-save-credentials/', headers=step7_headers, data=step7_data, timeout=15)

        step7_text = strip_json_prefix(response.text)

        try:
            step7_json = json.loads(step7_text)
            if step7_json.get("error"):
                error_msg = step7_json.get("errorDescription", "Unknown error")
                update_counter("failed", number, f"Registration failed! {error_msg}", RED)
                save_failed_number(number)
                return

            payload = step7_json.get("payload")
            if payload:
                account_id = payload.get("account_id", "")

                if account_id:
                    update_counter("success", number, f"Registration Successful! OTP Sent! ID:{account_id}", GREEN)
                    save_success_number(number)

                    # Step 8: Resend OTP loop
                    if resend_count > 0:
                        for r_idx in range(resend_count):
                            reload_headers = {
                                **base_headers,
                                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                                'accept-language': 'en-US,en;q=0.7',
                                'priority': 'u=0, i',
                                'referer': 'https://auth.meta.com/',
                                'sec-fetch-dest': 'document',
                                'sec-fetch-mode': 'navigate',
                                'sec-fetch-site': 'same-origin',
                                'upgrade-insecure-requests': '1',
                            }
                            reload_response = session.get(auth_referer, headers=reload_headers, allow_redirects=True, timeout=15)

                            resend_tokens = extract_tokens(reload_response.text, session_cookies=session.cookies,
                                                           default_lsd=auth_lsd, default_rev=auth_rev,
                                                           default_hsi=auth_hsi, default_hs=auth_hs,
                                                           default_spin_b=auth_spin_b, default_spin_t=auth_spin_t,
                                                           default_comet_req=auth_comet_req)
                            fb_dtsg = resend_tokens['fb_dtsg']
                            if not fb_dtsg:
                                safe_print(f"{YELLOW}  fb_dtsg not found! Resend OTP skip. [{number}]")
                                return

                            s_val = generate_s_val()

                            resend_headers = {
                                **api_headers,
                                'origin': 'https://auth.meta.com',
                                'referer': auth_referer,
                                'x-fb-friendly-name': 'FRLResendOTPMutation',
                                'x-fb-lsd': resend_tokens['lsd'],
                            }

                            resend_variables = json.dumps({
                                "input": {
                                    "contact_point": {"sensitive_string_value": contact_point},
                                    "contact_point_type": "PHONE_NUMBER",
                                    "source_app_id": 391894423991568,
                                    "actor_id": "0",
                                    "client_mutation_id": "1"
                                }
                            })

                            resend_data = {
                                'av': '0',
                                **build_common_params(resend_tokens['hs'], resend_tokens['rev'], s_val,
                                                      resend_tokens['hsi'], auth_dyn, auth_csr,
                                                      resend_tokens['comet_req'], resend_tokens['lsd'],
                                                      resend_tokens['jazoest'], resend_tokens['spin_b'],
                                                      resend_tokens['spin_t'], "EXCELLENT"),
                                '__req': '1w',
                                'fb_dtsg': fb_dtsg,
                                'fb_api_caller_class': 'RelayModern',
                                'fb_api_req_friendly_name': 'FRLResendOTPMutation',
                                'server_timestamps': 'true',
                                'variables': resend_variables,
                                'doc_id': '9505972379478338',
                            }

                            response = session.post('https://auth.meta.com/api/graphql/', headers=resend_headers, data=resend_data, timeout=15)

                            resend_text = strip_json_prefix(response.text)

                            try:
                                resend_json = json.loads(resend_text)
                                resend_success = resend_json.get("data", {}).get("resend_otp", {}).get("success", False)

                                errors = resend_json.get("errors", [])
                                if errors:
                                    error_code = errors[0].get("api_error_code")
                                    error_desc = errors[0].get("description", "Unknown Error")
                                    if error_code == 613:
                                        safe_print(f"{YELLOW} [RATE LIMIT] {error_desc} [{number}]")
                                        break
                                    else:
                                        safe_print(f"{YELLOW} OTP Resend {r_idx+1}/{resend_count} Failed (Code: {error_code}) [{number}]")
                                elif resend_success:
                                    safe_print(f"{GREEN} OTP Resend {r_idx+1}/{resend_count} Successful! [{number}]")
                                else:
                                    safe_print(f"{YELLOW} OTP Resend {r_idx+1}/{resend_count} Failed (Unknown) [{number}]")

                            except Exception as e:
                                safe_print(f"{YELLOW} Resend OTP {r_idx+1} Error: {e} [{number}]")

                            if r_idx < resend_count - 1:
                                delay = round(random.uniform(0.5, 1.2), 2)
                                time.sleep(delay)
                else:
                    errors = payload.get("validation_errors", [])
                    update_counter("failed", number, f"Registration failed! {errors}", RED)
                    save_failed_number(number)
            else:
                update_counter("failed", number, "Registration failed! (payload null)", RED)
                save_failed_number(number)
        except json.JSONDecodeError:
            update_counter("error", number, "Response parse failed!", RED)
            save_failed_number(number)

    except requests.exceptions.ConnectionError as e:
        update_counter("error", number, f"Network error: {str(e)[:30]}...", RED)
        save_failed_number(number)
        time.sleep(5)
    except requests.exceptions.Timeout:
        update_counter("error", number, "Request timeout!", RED)
        save_failed_number(number)
        time.sleep(5)
    except requests.exceptions.RequestException as e:
        update_counter("error", number, f"Request error: {str(e)[:30]}...", RED)
        save_failed_number(number)
        time.sleep(3)
    except Exception as e:
        update_counter("error", number, f"Unexpected error: {str(e)[:30]}...", RED)
        save_failed_number(number)

from core.meta_otp.service import normalize_proxy_to_dict as normalize_proxy
