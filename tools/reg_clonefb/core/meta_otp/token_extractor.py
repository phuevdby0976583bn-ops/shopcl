import re
import time

# Pre-compiled regex patterns for token extraction
LSD_PATTERNS = [
    re.compile(r'"LSD",\s*\[\s*\],\s*\{\s*"token":\s*"([^"]+)"'),
    re.compile(r'"lsd":\s*"([^"]+)"'),
    re.compile(r'name="lsd"\s+value="([^"]+)"')
]
REV_PATTERN = re.compile(r'"server_revision":\s*(\d+)')
HSI_PATTERN = re.compile(r'"hsi":\s*"(\d+)"')
SPIN_B_PATTERN = re.compile(r'"__spin_b":\s*"([^"]+)"')
SPIN_T_PATTERN = re.compile(r'"__spin_t":\s*(\d+)')
HS_PATTERNS = [
    re.compile(r'"__hs":\s*"([^"]+)"'),
    re.compile(r'"haste_session":\s*"([^"]+)"')
]
COMET_REQ_PATTERN = re.compile(r'"comet_env":\s*(\d+)')
FB_DTSG_PATTERNS = [
    re.compile(r'"DTSGInitData",\s*\[\s*\],\s*\{\s*"token":\s*"([^"]+)"'),
    re.compile(r'"DTSGInitialData",\s*\[\s*\],\s*\{\s*"token":\s*"([^"]+)"'),
    re.compile(r'name="fb_dtsg"\s+value="([^"]+)"'),
    re.compile(r'"fb_dtsg":\s*"([^"]+)"'),
    re.compile(r'"dtsg":\s*\{\s*"token":\s*"([^"]+)"')
]

def extract_tokens(html, session_cookies=None, default_lsd="", default_rev="", default_hsi="",
                   default_hs="", default_spin_b="trunk", default_spin_t="", default_comet_req="72"):
    """Extract authentication tokens from Meta HTML response."""
    tokens = {}

    # LSD token
    lsd_val = default_lsd
    for p in LSD_PATTERNS:
        match = p.search(html)
        if match:
            lsd_val = match.group(1)
            break
    tokens['lsd'] = lsd_val

    # Server revision
    rev_match = REV_PATTERN.search(html)
    tokens['rev'] = rev_match.group(1) if rev_match else default_rev

    # HSI
    hsi_match = HSI_PATTERN.search(html)
    tokens['hsi'] = hsi_match.group(1) if hsi_match else default_hsi

    # Spin bundle
    spin_b_match = SPIN_B_PATTERN.search(html)
    tokens['spin_b'] = spin_b_match.group(1) if spin_b_match else default_spin_b

    # Spin timestamp
    spin_t_match = SPIN_T_PATTERN.search(html)
    tokens['spin_t'] = spin_t_match.group(1) if spin_t_match else (default_spin_t if default_spin_t else str(int(time.time())))

    # Haste session
    hs_val = default_hs
    for p in HS_PATTERNS:
        match = p.search(html)
        if match:
            hs_val = match.group(1)
            break
    tokens['hs'] = hs_val

    # Comet request ID
    comet_match = COMET_REQ_PATTERN.search(html)
    tokens['comet_req'] = comet_match.group(1) if comet_match else default_comet_req

    # DTSG token
    fb_dtsg = ""
    for p in FB_DTSG_PATTERNS:
        m = p.search(html)
        if m:
            fb_dtsg = m.group(1)
            break
    tokens['fb_dtsg'] = fb_dtsg

    # Jazoest (computed from cookies)
    if session_cookies:
        all_cookie_str = ''.join(session_cookies.get_dict().values())
        tokens['jazoest'] = "2" + str(sum(ord(c) for c in all_cookie_str))
    else:
        tokens['jazoest'] = ""

    return tokens
