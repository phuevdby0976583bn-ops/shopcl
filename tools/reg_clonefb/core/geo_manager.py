# -*- coding: utf-8 -*-
"""
core.geo_manager
Hệ thống đồng bộ Định danh Địa lý & Viễn thông Nhà mạng (GeoIP & Telephony Synchronization Engine).
Đảm bảo tính nhất quán tuyệt đối giữa:
1. Địa chỉ IP Proxy (Quốc gia, Thành phố, Timezone, ISP).
2. Nhà mạng viễn thông thực (MNO Carrier: Viettel, T-Mobile, AIS, Telkomsel...).
3. Thông số SIM vật lý: MCC (Mobile Country Code), MNC (Mobile Network Code), SIM Country ISO.
4. Đầu số điện thoại di động chính hãng & mã vùng quốc tế (+84, +1, +66, +62...).
5. Mã vùng hiển thị (Locale: vi_VN, en_US, th_TH...), Accept-Language và Timezone.
"""

import os
import re
import json
import time
import random
import logging
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)


def generate_phone_suffix_from_ip(ip=None, length=7):
    """
    Sinh duoi so dien thoai (suffix) tu nhien voi entropy cao, ngau nhien 100%
    de xoa bo hoan toan dau vet pattern co dinh theo IP (chong Checkpoint 282 cua Facebook).
    """
    for _ in range(25):
        digits = [str(random.randint(2, 9))] + [str(random.randint(0, 9)) for _ in range(length - 1)]
        suffix = ''.join(digits)
        if len(set(suffix)) >= 4 and suffix not in ('1234567', '7654321', '0123456', '9876543'):
            return suffix
    return f"{random.randint(2, 9)}{''.join(str(random.randint(0, 9)) for _ in range(length - 1))}"


@dataclass
class GeoTelephonyProfile:
    """Hồ sơ viễn thông và địa lý đồng nhất cho thiết bị di động."""
    ip: str = "127.0.0.1"
    country_code: str = "VN"
    country_name: str = "Vietnam"
    city: str = "Hanoi"
    region: str = "Hanoi"
    timezone: str = "Asia/Ho_Chi_Minh"
    timezone_offset_minutes: int = 420
    locale: str = "vi_VN"
    accept_language: str = "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
    carrier_name: str = "Viettel"
    mcc: str = "452"
    mnc: str = "04"
    operator_numeric: str = "45204"
    sim_country_iso: str = "vn"
    phone_calling_code: str = "+84"
    phone_prefixes: List[str] = field(default_factory=lambda: ["032", "033", "034", "035", "036", "037", "038", "039", "086", "096", "097", "098"])
    phone_number_length: int = 10
    sim_state: int = 5  # TelephonyManager.SIM_STATE_READY
    network_type: int = 13  # TelephonyManager.NETWORK_TYPE_LTE
    phone_type: int = 1  # TelephonyManager.PHONE_TYPE_GSM
    soc_preference: str = "Qualcomm Snapdragon 8 Gen 2"
    gl_renderer_preference: str = "Adreno (TM) 740"

    def generate_phone(self, ip: Optional[str] = None, e164: bool = False) -> str:
        """Sinh so dien thoai di dong chinh xac theo nha mang, ma vung quoc gia va duoi IP neu co."""
        prefix = random.choice(self.phone_prefixes) if self.phone_prefixes else "098"
        remaining_digits = max(1, self.phone_number_length - len(prefix))
        target_ip = ip if ip is not None else getattr(self, "ip", None)
        local_num = f"{prefix}{generate_phone_suffix_from_ip(target_ip, remaining_digits)}"
        if not e164 or getattr(self, "country_code", "VN") == "VN":
            return local_num
        calling_code = (self.phone_calling_code or "+84").strip()
        if not calling_code.startswith("+"):
            calling_code = f"+{calling_code}"
        national_num = local_num.lstrip("0") or local_num
        return f"{calling_code}{national_num}"

    def to_telephony_dict(self) -> Dict[str, Any]:
        """Xuất thông số TelephonyManager phản chiếu cấu hình phần cứng thật."""
        return {
            "sim_operator": self.operator_numeric,
            "sim_operator_name": self.carrier_name,
            "sim_country_iso": self.sim_country_iso,
            "network_operator": self.operator_numeric,
            "network_operator_name": self.carrier_name,
            "network_country_iso": self.sim_country_iso,
            "sim_state": self.sim_state,
            "network_type": self.network_type,
            "phone_type": self.phone_type,
            "locale": self.locale,
            "timezone": self.timezone,
            "timezone_offset": self.timezone_offset_minutes,
        }


COUNTRY_TELEPHONY_DATABASE: Dict[str, Dict[str, Any]] = {
    "VN": {
        "country_name": "Vietnam",
        "locale": "vi_VN",
        "accept_language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "timezones": ["Asia/Ho_Chi_Minh"],
        "timezone_offset": 420,
        "phone_calling_code": "+84",
        "phone_length": 10,
        "carriers": [
            {
                "name": "Viettel", "mcc": "452", "mnc": "04",
                "prefixes": ["098", "097", "096", "086", "039", "038", "037", "036", "035", "034", "033", "032"]
            },
            {
                "name": "Vinaphone", "mcc": "452", "mnc": "02",
                "prefixes": ["091", "094", "088", "081", "082", "083", "084", "085"]
            },
            {
                "name": "Mobifone", "mcc": "452", "mnc": "01",
                "prefixes": ["090", "093", "089", "070", "076", "077", "078", "079"]
            },
            {
                "name": "Vietnamobile", "mcc": "452", "mnc": "05",
                "prefixes": ["092", "056", "058"]
            },
        ]
    },
    "US": {
        "country_name": "United States",
        "locale": "en_US",
        "accept_language": "en-US,en;q=0.9",
        "timezones": ["America/New_York", "America/Chicago", "America/Los_Angeles", "America/Denver"],
        "timezone_offset": -300,
        "phone_calling_code": "+1",
        "phone_length": 10,
        "carriers": [
            {
                "name": "T-Mobile", "mcc": "310", "mnc": "260",
                "prefixes": ["201", "202", "206", "212", "213", "214", "310", "312", "415", "646", "718", "832", "917"]
            },
            {
                "name": "Verizon", "mcc": "311", "mnc": "480",
                "prefixes": ["305", "312", "323", "347", "404", "408", "415", "512", "619", "650", "702", "773", "929"]
            },
            {
                "name": "AT&T", "mcc": "310", "mnc": "410",
                "prefixes": ["210", "214", "281", "404", "415", "469", "512", "617", "703", "713", "832", "972"]
            },
        ]
    },
    "TH": {
        "country_name": "Thailand",
        "locale": "th_TH",
        "accept_language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
        "timezones": ["Asia/Bangkok"],
        "timezone_offset": 420,
        "phone_calling_code": "+66",
        "phone_length": 10,
        "carriers": [
            {
                "name": "AIS", "mcc": "520", "mnc": "01",
                "prefixes": ["081", "082", "087", "092", "093", "097", "098"]
            },
            {
                "name": "TrueMove H", "mcc": "520", "mnc": "00",
                "prefixes": ["086", "089", "090", "095", "096"]
            },
            {
                "name": "DTAC", "mcc": "520", "mnc": "05",
                "prefixes": ["081", "084", "085", "088", "094"]
            },
        ]
    },
    "ID": {
        "country_name": "Indonesia",
        "locale": "id_ID",
        "accept_language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        "timezones": ["Asia/Jakarta", "Asia/Makassar"],
        "timezone_offset": 420,
        "phone_calling_code": "+62",
        "phone_length": 11,
        "carriers": [
            {
                "name": "Telkomsel", "mcc": "510", "mnc": "10",
                "prefixes": ["0811", "0812", "0813", "0821", "0822", "0852"]
            },
            {
                "name": "Indosat Ooredoo", "mcc": "510", "mnc": "01",
                "prefixes": ["0814", "0815", "0816", "0855", "0856", "0857"]
            },
            {
                "name": "XL Axiata", "mcc": "510", "mnc": "11",
                "prefixes": ["0817", "0818", "0819", "0859", "0877", "0878"]
            },
        ]
    },
    "PH": {
        "country_name": "Philippines",
        "locale": "fil_PH",
        "accept_language": "en-PH,fil-PH;q=0.9,en;q=0.8",
        "timezones": ["Asia/Manila"],
        "timezone_offset": 480,
        "phone_calling_code": "+63",
        "phone_length": 11,
        "carriers": [
            {
                "name": "Smart", "mcc": "515", "mnc": "03",
                "prefixes": ["0918", "0919", "0920", "0921", "0928", "0929", "0998"]
            },
            {
                "name": "Globe", "mcc": "515", "mnc": "02",
                "prefixes": ["0917", "0927", "0935", "0945", "0956", "0965", "0977"]
            },
            {
                "name": "DITO", "mcc": "515", "mnc": "66",
                "prefixes": ["0991", "0992", "0993", "0994"]
            },
        ]
    },
    "IN": {
        "country_name": "India",
        "locale": "en_IN",
        "accept_language": "en-IN,en-GB;q=0.9,en;q=0.8,hi;q=0.7",
        "timezones": ["Asia/Kolkata"],
        "timezone_offset": 330,
        "phone_calling_code": "+91",
        "phone_length": 10,
        "carriers": [
            {
                "name": "Jio", "mcc": "405", "mnc": "86",
                "prefixes": ["900", "901", "902", "903", "904", "905", "906", "907", "908", "909"]
            },
            {
                "name": "Airtel", "mcc": "404", "mnc": "45",
                "prefixes": ["981", "982", "983", "984", "985", "986", "987", "988", "989"]
            },
            {
                "name": "Vi", "mcc": "404", "mnc": "20",
                "prefixes": ["970", "971", "972", "973", "974", "975", "976", "977"]
            },
        ]
    },
    "DE": {
        "country_name": "Germany",
        "locale": "de_DE",
        "accept_language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "timezones": ["Europe/Berlin"],
        "timezone_offset": 60,
        "phone_calling_code": "+49",
        "phone_length": 11,
        "carriers": [
            {
                "name": "Telekom", "mcc": "262", "mnc": "01",
                "prefixes": ["0151", "0160", "0170", "0171", "0175"]
            },
            {
                "name": "Vodafone", "mcc": "262", "mnc": "02",
                "prefixes": ["0152", "0162", "0172", "0173", "0174"]
            },
            {
                "name": "O2", "mcc": "262", "mnc": "03",
                "prefixes": ["0159", "0176", "0179"]
            },
        ]
    },
    "FR": {
        "country_name": "France",
        "locale": "fr_FR",
        "accept_language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "timezones": ["Europe/Paris"],
        "timezone_offset": 60,
        "phone_calling_code": "+33",
        "phone_length": 10,
        "carriers": [
            {
                "name": "Orange", "mcc": "208", "mnc": "01",
                "prefixes": ["060", "063", "067", "068", "075", "076"]
            },
            {
                "name": "SFR", "mcc": "208", "mnc": "10",
                "prefixes": ["061", "062", "069", "077", "078"]
            },
            {
                "name": "Bouygues", "mcc": "208", "mnc": "20",
                "prefixes": ["065", "066", "074", "079"]
            },
        ]
    },
    "GB": {
        "country_name": "United Kingdom",
        "locale": "en_GB",
        "accept_language": "en-GB,en;q=0.9,en-US;q=0.8",
        "timezones": ["Europe/London"],
        "timezone_offset": 0,
        "phone_calling_code": "+44",
        "phone_length": 11,
        "carriers": [
            {
                "name": "EE", "mcc": "234", "mnc": "30",
                "prefixes": ["074", "075", "077", "079"]
            },
            {
                "name": "Vodafone UK", "mcc": "234", "mnc": "15",
                "prefixes": ["073", "077", "078"]
            },
            {
                "name": "O2 UK", "mcc": "234", "mnc": "10",
                "prefixes": ["074", "075", "077"]
            },
        ]
    },
    "BR": {
        "country_name": "Brazil",
        "locale": "pt_BR",
        "accept_language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "timezones": ["America/Sao_Paulo"],
        "timezone_offset": -180,
        "phone_calling_code": "+55",
        "phone_length": 11,
        "carriers": [
            {
                "name": "Vivo", "mcc": "724", "mnc": "06",
                "prefixes": ["0119", "0219", "0319", "0419"]
            },
            {
                "name": "Claro", "mcc": "724", "mnc": "05",
                "prefixes": ["0119", "0219", "0519", "0719"]
            },
            {
                "name": "TIM", "mcc": "724", "mnc": "02",
                "prefixes": ["0119", "0219", "0819", "0919"]
            },
        ]
    },
    "JP": {
        "country_name": "Japan",
        "locale": "ja_JP",
        "accept_language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        "timezones": ["Asia/Tokyo"],
        "timezone_offset": 540,
        "phone_calling_code": "+81",
        "phone_length": 11,
        "carriers": [
            {
                "name": "NTT Docomo", "mcc": "440", "mnc": "10",
                "prefixes": ["080", "090", "070"]
            },
            {
                "name": "SoftBank", "mcc": "440", "mnc": "20",
                "prefixes": ["080", "090", "070"]
            },
            {
                "name": "au KDDI", "mcc": "440", "mnc": "50",
                "prefixes": ["080", "090", "070"]
            },
        ]
    },
    "KR": {
        "country_name": "South Korea",
        "locale": "ko_KR",
        "accept_language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "timezones": ["Asia/Seoul"],
        "timezone_offset": 540,
        "phone_calling_code": "+82",
        "phone_length": 11,
        "carriers": [
            {
                "name": "SK Telecom", "mcc": "450", "mnc": "05",
                "prefixes": ["010"]
            },
            {
                "name": "KT", "mcc": "450", "mnc": "08",
                "prefixes": ["010"]
            },
            {
                "name": "LG Uplus", "mcc": "450", "mnc": "06",
                "prefixes": ["010"]
            },
        ]
    },
    "TW": {
        "country_name": "Taiwan",
        "locale": "zh_TW",
        "accept_language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "timezones": ["Asia/Taipei"],
        "timezone_offset": 480,
        "phone_calling_code": "+886",
        "phone_length": 10,
        "carriers": [
            {
                "name": "Chunghwa Telecom", "mcc": "466", "mnc": "92",
                "prefixes": ["091", "092", "093", "097", "098"]
            },
            {
                "name": "Taiwan Mobile", "mcc": "466", "mnc": "97",
                "prefixes": ["090", "091", "092", "093"]
            },
        ]
    },
    "SG": {
        "country_name": "Singapore",
        "locale": "en_SG",
        "accept_language": "en-SG,en;q=0.9,zh-SG;q=0.8",
        "timezones": ["Asia/Singapore"],
        "timezone_offset": 480,
        "phone_calling_code": "+65",
        "phone_length": 8,
        "carriers": [
            {
                "name": "Singtel", "mcc": "525", "mnc": "01",
                "prefixes": ["81", "82", "83", "84", "90", "91", "92", "93"]
            },
            {
                "name": "StarHub", "mcc": "525", "mnc": "05",
                "prefixes": ["88", "98", "95"]
            },
        ]
    },
    "MY": {
        "country_name": "Malaysia",
        "locale": "ms_MY",
        "accept_language": "ms-MY,ms;q=0.9,en-US;q=0.8,en;q=0.7",
        "timezones": ["Asia/Kuala_Lumpur"],
        "timezone_offset": 480,
        "phone_calling_code": "+60",
        "phone_length": 10,
        "carriers": [
            {
                "name": "Celcom", "mcc": "502", "mnc": "19",
                "prefixes": ["013", "019"]
            },
            {
                "name": "Maxis", "mcc": "502", "mnc": "12",
                "prefixes": ["012", "017"]
            },
        ]
    },
    "CA": {
        "country_name": "Canada",
        "locale": "en_CA",
        "accept_language": "en-CA,en;q=0.9,fr-CA;q=0.8",
        "timezones": ["America/Toronto", "America/Vancouver"],
        "timezone_offset": -300,
        "phone_calling_code": "+1",
        "phone_length": 10,
        "carriers": [
            {
                "name": "Rogers", "mcc": "302", "mnc": "720",
                "prefixes": ["416", "647", "437"]
            },
            {
                "name": "Bell", "mcc": "302", "mnc": "610",
                "prefixes": ["514", "438"]
            },
        ]
    },
    "AU": {
        "country_name": "Australia",
        "locale": "en_AU",
        "accept_language": "en-AU,en;q=0.9,en-GB;q=0.8",
        "timezones": ["Australia/Sydney"],
        "timezone_offset": 600,
        "phone_calling_code": "+61",
        "phone_length": 10,
        "carriers": [
            {
                "name": "Telstra", "mcc": "505", "mnc": "01",
                "prefixes": ["040", "041", "042"]
            },
            {
                "name": "Optus", "mcc": "505", "mnc": "02",
                "prefixes": ["043", "044", "045"]
            },
        ]
    },
    "RU": {
        "country_name": "Russia",
        "locale": "ru_RU",
        "accept_language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "timezones": ["Europe/Moscow"],
        "timezone_offset": 180,
        "phone_calling_code": "+7",
        "phone_length": 10,
        "carriers": [
            {
                "name": "MTS", "mcc": "250", "mnc": "01",
                "prefixes": ["910", "911", "912", "913", "914", "915", "916"]
            },
            {
                "name": "MegaFon", "mcc": "250", "mnc": "02",
                "prefixes": ["920", "921", "922", "923", "924", "925", "926"]
            },
        ]
    },
}


COUNTRY_NAME_TO_CODE = {
    "VIETNAM": "VN", "VIET NAM": "VN", "VIỆT NAM": "VN", "VNM": "VN",
    "CHINA": "CN", "CHN": "CN", "TRUNG QUỐC": "CN", "TRUNG QUOC": "CN",
    "UNITED STATES": "US", "UNITED STATES OF AMERICA": "US", "USA": "US", "AMERICA": "US",
    "THAILAND": "TH", "THAI LAN": "TH", "THÁI LAN": "TH", "THA": "TH",
    "SINGAPORE": "SG", "SGP": "SG",
    "INDONESIA": "ID", "IDN": "ID",
    "PHILIPPINES": "PH", "PHL": "PH",
    "INDIA": "IN", "IND": "IN", "ẤN ĐỘ": "IN",
    "GERMANY": "DE", "DEU": "DE", "ĐỨC": "DE",
    "FRANCE": "FR", "FRA": "FR", "PHÁP": "FR",
    "UNITED KINGDOM": "GB", "UK": "GB", "GBR": "GB", "GREAT BRITAIN": "GB", "ANH": "GB",
    "BRAZIL": "BR", "BRA": "BR",
    "JAPAN": "JP", "JPN": "JP", "NHẬT BẢN": "JP", "NHẬT": "JP",
    "SOUTH KOREA": "KR", "KOREA": "KR", "KOR": "KR", "HÀN QUỐC": "KR",
    "TAIWAN": "TW", "TWN": "TW", "ĐÀI LOAN": "TW",
    "MALAYSIA": "MY", "MYS": "MY",
    "CANADA": "CA", "CAN": "CA",
    "AUSTRALIA": "AU", "AUS": "AU", "ÚC": "AU",
    "RUSSIA": "RU", "RUS": "RU", "NGA": "RU",
    "CAMBODIA": "KH", "KHM": "KH", "CAMPUCHIA": "KH",
    "LAOS": "LA", "LAO": "LA", "LÀO": "LA",
    "MYANMAR": "MM", "MMR": "MM",
    "HONG KONG": "HK", "HKG": "HK",
    "NETHERLANDS": "NL", "NLD": "NL", "HÀ LAN": "NL",
    "SPAIN": "ES", "ESP": "ES", "TÂY BAN NHA": "ES",
    "ITALY": "IT", "ITA": "IT", "Ý": "IT",
    "POLAND": "PL", "POL": "PL", "BA LAN": "PL",
    "TURKEY": "TR", "TUR": "TR", "THỔ NHĨ KỲ": "TR",
    "MEXICO": "MX", "MEX": "MX",
    "ARGENTINA": "AR", "ARG": "AR",
    "COLOMBIA": "CO", "COL": "CO",
    "CHILE": "CL", "CHL": "CL",
    "UNITED ARAB EMIRATES": "AE", "UAE": "AE",
    "SAUDI ARABIA": "SA", "SAU": "SA",
    "EGYPT": "EG", "EGY": "EG",
    "NIGERIA": "NG", "NGA": "NG",
    "SOUTH AFRICA": "ZA", "ZAF": "ZA",
    "UKRAINE": "UA", "UKR": "UA",
    "BANGLADESH": "BD", "BGD": "BD",
    "PAKISTAN": "PK", "PAK": "PK",
    "SWEDEN": "SE", "SWE": "SE",
    "NORWAY": "NO", "NOR": "NO",
    "DENMARK": "DK", "DNK": "DK",
    "FINLAND": "FI", "FIN": "FI",
    "SWITZERLAND": "CH", "CHE": "CH",
    "AUSTRIA": "AT", "AUT": "AT",
    "BELGIUM": "BE", "BEL": "BE",
    "PORTUGAL": "PT", "PRT": "PT",
    "GREECE": "GR", "GRC": "GR",
    "CZECH REPUBLIC": "CZ", "CZECHIA": "CZ", "CZE": "CZ",
    "ROMANIA": "RO", "ROU": "RO",
    "HUNGARY": "HU", "HUN": "HU",
    "NEW ZEALAND": "NZ", "NZL": "NZ",
    "ISRAEL": "IL", "ISR": "IL",
    "PERU": "PE", "PE": "PE",
    "ECUADOR": "EC", "EC": "EC",
    "BOLIVIA": "BO", "BO": "BO",
    "PARAGUAY": "PY", "PY": "PY",
    "URUGUAY": "UY", "UY": "UY",
    "VENEZUELA": "VE", "VE": "VE",
    "COSTA RICA": "CR", "CR": "CR",
    "PANAMA": "PA", "PA": "PA",
    "GUATEMALA": "GT", "GT": "GT",
    "HONDURAS": "HN", "HN": "HN",
    "EL SALVADOR": "SV", "SV": "SV",
    "NICARAGUA": "NI", "NI": "NI",
    "DOMINICAN REPUBLIC": "DO", "DO": "DO",
    "JAMAICA": "JM", "JM": "JM",
    "TRINIDAD AND TOBAGO": "TT", "TT": "TT",
    "IRELAND": "IE", "IE": "IE",
    "ICELAND": "IS", "IS": "IS",
    "BULGARIA": "BG", "BG": "BG",
    "CROATIA": "HR", "HR": "HR",
    "SERBIA": "RS", "RS": "RS",
    "SLOVAKIA": "SK", "SK": "SK",
    "SLOVENIA": "SI", "SI": "SI",
    "LITHUANIA": "LT", "LT": "LT",
    "LATVIA": "LV", "LV": "LV",
    "ESTONIA": "EE", "EE": "EE",
    "CYPRUS": "CY", "CY": "CY",
    "LUXEMBOURG": "LU", "LU": "LU",
    "MALTA": "MT", "MT": "MT",
    "ALBANIA": "AL", "AL": "AL",
    "NORTH MACEDONIA": "MK", "MK": "MK",
    "BOSNIA AND HERZEGOVINA": "BA", "BA": "BA",
    "MONTENEGRO": "ME", "ME": "ME",
    "MOLDOVA": "MD", "MD": "MD",
    "BELARUS": "BY", "BY": "BY",
    "KAZAKHSTAN": "KZ", "KZ": "KZ",
    "UZBEKISTAN": "UZ", "UZ": "UZ",
    "GEORGIA": "GE", "GE": "GE",
    "ARMENIA": "AM", "AM": "AM",
    "AZERBAIJAN": "AZ", "AZ": "AZ",
    "KYRGYZSTAN": "KG", "KG": "KG",
    "TAJIKISTAN": "TJ", "TJ": "TJ",
    "MONGOLIA": "MN", "MN": "MN",
    "MOROCCO": "MA", "MA": "MA",
    "MA-RỐC": "MA", "MAROC": "MA",
    "BỈ": "BE", "HÀ LAN": "NL", "THỤY SĨ": "CH", "THỤY ĐIỂN": "SE", "NA UY": "NO",
    "ĐAN MẠCH": "DK", "HY LẠP": "GR", "BỒ ĐÀO NHA": "PT", "ÁO": "AT",
    "CỘNG HÒA SÉC": "CZ", "UKRAINA": "UA",

    "ALGERIA": "DZ", "DZ": "DZ",
    "TUNISIA": "TN", "TN": "TN",
    "KUWAIT": "KW", "KW": "KW",
    "QATAR": "QA", "QA": "QA",
    "BAHRAIN": "BH", "BH": "BH",
    "OMAN": "OM", "OM": "OM",
    "JORDAN": "JO", "JO": "JO",
    "LEBANON": "LB", "LB": "LB",
    "IRAQ": "IQ", "IQ": "IQ",
    "IRAN": "IR", "IR": "IR",
    "KENYA": "KE", "KE": "KE",
    "GHANA": "GH", "GH": "GH",
    "IVORY COAST": "CI", "CI": "CI",
    "SENEGAL": "SN", "SN": "SN",
    "CAMEROON": "CM", "CM": "CM",
    "UGANDA": "UG", "UG": "UG",
    "ETHIOPIA": "ET", "ET": "ET",
    "TANZANIA": "TZ", "TZ": "TZ",
    "SRI LANKA": "LK", "LK": "LK",
    "NEPAL": "NP", "NP": "NP",
    "BRUNEI": "BN", "BN": "BN",
    "MACAU": "MO", "MO": "MO",
    "FIJI": "FJ", "FJ": "FJ",
    "PAPUA NEW GUINEA": "PG", "PG": "PG",
    "MALDIVES": "MV", "MV": "MV",
}


def normalize_country_code(val) -> str:
    """Chuẩn hóa tên quốc gia hoặc chuỗi bất kỳ thành mã ISO 2 chữ cái in hoa (VD: 'Vietnam' -> 'VN', 'USA' -> 'US')."""
    if not val:
        return ""
    s = str(val).strip().upper()
    if s in COUNTRY_NAME_TO_CODE:
        return COUNTRY_NAME_TO_CODE[s]
    m_par = re.search(r"[\(\[]([A-Za-z]{2})[\)\]]", s)
    if m_par:
        cand = m_par.group(1).upper()
        if cand in COUNTRY_NAME_TO_CODE:
            return COUNTRY_NAME_TO_CODE[cand]
        if len(cand) == 2 and cand.isalpha():
            return cand
    if len(s) == 2 and s.isalpha() and s in WORLD_CALLING_CODES:
        return s
    for name, code in COUNTRY_NAME_TO_CODE.items():
        if len(name) > 2 and name in s:
            return code
    try:
        import pycountry
        match = pycountry.countries.get(name=val) or pycountry.countries.get(alpha_2=s) or pycountry.countries.get(alpha_3=s)
        if match:
            return match.alpha_2
        fuzzy = pycountry.countries.search_fuzzy(val)
        if fuzzy:
            return fuzzy[0].alpha_2
    except Exception:
        pass
    if len(s) == 2 and s.isalpha():
        return s
    return ""

GLOBAL_COUNTRY_CALLING_CODES = {
    "CN": {"name": "China", "calling_code": "+86", "length": 11, "locale": "zh_CN", "tz": "Asia/Shanghai", "carriers": [{"name": "China Mobile", "mcc": "460", "mnc": "00", "prefixes": ["138", "139", "150", "158", "188"]}, {"name": "China Unicom", "mcc": "460", "mnc": "01", "prefixes": ["130", "131", "155", "186"]}, {"name": "China Telecom", "mcc": "460", "mnc": "03", "prefixes": ["133", "153", "180", "189"]}]},
    "KH": {"name": "Cambodia", "calling_code": "+855", "length": 9, "locale": "km_KH", "tz": "Asia/Phnom_Penh", "carriers": [{"name": "Smart", "mcc": "456", "mnc": "06", "prefixes": ["010", "015", "016", "086", "087", "093", "098"]}, {"name": "Cellcard", "mcc": "456", "mnc": "01", "prefixes": ["012", "014", "017", "076", "077", "078", "085", "089", "092", "095"]}]},
    "LA": {"name": "Laos", "calling_code": "+856", "length": 10, "locale": "lo_LA", "tz": "Asia/Vientiane", "carriers": [{"name": "Unitel", "mcc": "457", "mnc": "01", "prefixes": ["0209", "0205"]}, {"name": "Lao Telecom", "mcc": "457", "mnc": "02", "prefixes": ["0202", "0207"]}]},
    "MM": {"name": "Myanmar", "calling_code": "+95", "length": 10, "locale": "my_MM", "tz": "Asia/Yangon", "carriers": [{"name": "MPT", "mcc": "414", "mnc": "01", "prefixes": ["092", "094", "095"]}, {"name": "ATOM", "mcc": "414", "mnc": "06", "prefixes": ["097", "098", "099"]}]},
    "HK": {"name": "Hong Kong", "calling_code": "+852", "length": 8, "locale": "zh_HK", "tz": "Asia/Hong_Kong", "carriers": [{"name": "CSL", "mcc": "454", "mnc": "00", "prefixes": ["5", "6", "9"]}, {"name": "SmarTone", "mcc": "454", "mnc": "06", "prefixes": ["5", "6", "9"]}]},
    "NL": {"name": "Netherlands", "calling_code": "+31", "length": 9, "locale": "nl_NL", "tz": "Europe/Amsterdam", "carriers": [{"name": "KPN", "mcc": "204", "mnc": "08", "prefixes": ["06"]}, {"name": "Vodafone NL", "mcc": "204", "mnc": "04", "prefixes": ["06"]}]},
    "ES": {"name": "Spain", "calling_code": "+34", "length": 9, "locale": "es_ES", "tz": "Europe/Madrid", "carriers": [{"name": "Movistar", "mcc": "214", "mnc": "07", "prefixes": ["6", "7"]}, {"name": "Orange ES", "mcc": "214", "mnc": "03", "prefixes": ["6", "7"]}]},
    "IT": {"name": "Italy", "calling_code": "+39", "length": 10, "locale": "it_IT", "tz": "Europe/Rome", "carriers": [{"name": "TIM", "mcc": "222", "mnc": "01", "prefixes": ["33", "36"]}, {"name": "Vodafone IT", "mcc": "222", "mnc": "10", "prefixes": ["34", "37"]}]},
    "PL": {"name": "Poland", "calling_code": "+48", "length": 9, "locale": "pl_PL", "tz": "Europe/Warsaw", "carriers": [{"name": "Orange PL", "mcc": "260", "mnc": "03", "prefixes": ["50", "51", "53"]}, {"name": "Play", "mcc": "260", "mnc": "06", "prefixes": ["79", "78", "73"]}]},
    "TR": {"name": "Turkey", "calling_code": "+90", "length": 10, "locale": "tr_TR", "tz": "Europe/Istanbul", "carriers": [{"name": "Turkcell", "mcc": "286", "mnc": "01", "prefixes": ["530", "531", "532", "533"]}, {"name": "Vodafone TR", "mcc": "286", "mnc": "02", "prefixes": ["540", "541", "542"]}]},
    "MX": {"name": "Mexico", "calling_code": "+52", "length": 10, "locale": "es_MX", "tz": "America/Mexico_City", "carriers": [{"name": "Telcel", "mcc": "334", "mnc": "020", "prefixes": ["55", "81", "33"]}, {"name": "AT&T MX", "mcc": "334", "mnc": "050", "prefixes": ["55", "81", "33"]}]},
    "AR": {"name": "Argentina", "calling_code": "+54", "length": 10, "locale": "es_AR", "tz": "America/Argentina/Buenos_Aires", "carriers": [{"name": "Claro AR", "mcc": "722", "mnc": "310", "prefixes": ["11", "351"]}, {"name": "Personal", "mcc": "722", "mnc": "341", "prefixes": ["11", "341"]}]},
    "CO": {"name": "Colombia", "calling_code": "+57", "length": 10, "locale": "es_CO", "tz": "America/Bogota", "carriers": [{"name": "Claro CO", "mcc": "732", "mnc": "101", "prefixes": ["310", "311", "312", "313", "314", "320", "321"]}, {"name": "Tigo", "mcc": "732", "mnc": "103", "prefixes": ["300", "301", "302"]}]},
    "CL": {"name": "Chile", "calling_code": "+56", "length": 9, "locale": "es_CL", "tz": "America/Santiago", "carriers": [{"name": "Entel", "mcc": "730", "mnc": "01", "prefixes": ["9"]}, {"name": "Movistar CL", "mcc": "730", "mnc": "02", "prefixes": ["9"]}]},
    "AE": {"name": "UAE", "calling_code": "+971", "length": 9, "locale": "ar_AE", "tz": "Asia/Dubai", "carriers": [{"name": "Etisalat", "mcc": "424", "mnc": "02", "prefixes": ["050", "054", "056"]}, {"name": "du", "mcc": "424", "mnc": "03", "prefixes": ["052", "055", "058"]}]},
    "SA": {"name": "Saudi Arabia", "calling_code": "+966", "length": 9, "locale": "ar_SA", "tz": "Asia/Riyadh", "carriers": [{"name": "STC", "mcc": "420", "mnc": "01", "prefixes": ["050", "053", "055"]}, {"name": "Mobily", "mcc": "420", "mnc": "03", "prefixes": ["054", "056"]}]},
    "EG": {"name": "Egypt", "calling_code": "+20", "length": 10, "locale": "ar_EG", "tz": "Africa/Cairo", "carriers": [{"name": "Vodafone EG", "mcc": "602", "mnc": "02", "prefixes": ["010"]}, {"name": "Orange EG", "mcc": "602", "mnc": "01", "prefixes": ["012"]}]},
    "NG": {"name": "Nigeria", "calling_code": "+234", "length": 10, "locale": "en_NG", "tz": "Africa/Lagos", "carriers": [{"name": "MTN NG", "mcc": "621", "mnc": "30", "prefixes": ["0803", "0806", "0703", "0706", "0813", "0816"]}, {"name": "Airtel NG", "mcc": "621", "mnc": "20", "prefixes": ["0802", "0808", "0708", "0812"]}]},
    "ZA": {"name": "South Africa", "calling_code": "+27", "length": 9, "locale": "en_ZA", "tz": "Africa/Johannesburg", "carriers": [{"name": "Vodacom", "mcc": "655", "mnc": "01", "prefixes": ["082", "072", "076", "079"]}, {"name": "MTN ZA", "mcc": "655", "mnc": "10", "prefixes": ["083", "073", "078", "081"]}]},
    "UA": {"name": "Ukraine", "calling_code": "+380", "length": 9, "locale": "uk_UA", "tz": "Europe/Kyiv", "carriers": [{"name": "Kyivstar", "mcc": "255", "mnc": "03", "prefixes": ["67", "68", "96", "97", "98"]}, {"name": "Vodafone UA", "mcc": "255", "mnc": "01", "prefixes": ["50", "66", "95", "99"]}]},
    "BD": {"name": "Bangladesh", "calling_code": "+880", "length": 10, "locale": "bn_BD", "tz": "Asia/Dhaka", "carriers": [{"name": "Grameenphone", "mcc": "470", "mnc": "01", "prefixes": ["017", "013"]}, {"name": "Robi", "mcc": "470", "mnc": "02", "prefixes": ["018", "016"]}]},
    "PK": {"name": "Pakistan", "calling_code": "+92", "length": 10, "locale": "ur_PK", "tz": "Asia/Karachi", "carriers": [{"name": "Jazz", "mcc": "410", "mnc": "01", "prefixes": ["030", "032"]}, {"name": "Telenor PK", "mcc": "410", "mnc": "06", "prefixes": ["034", "035"]}]},
    "SE": {"name": "Sweden", "calling_code": "+46", "length": 9, "locale": "sv_SE", "tz": "Europe/Stockholm", "carriers": [{"name": "Telia", "mcc": "240", "mnc": "01", "prefixes": ["070", "072"]}, {"name": "Tele2", "mcc": "240", "mnc": "07", "prefixes": ["073", "076"]}]},
    "NO": {"name": "Norway", "calling_code": "+47", "length": 8, "locale": "nb_NO", "tz": "Europe/Oslo", "carriers": [{"name": "Telenor NO", "mcc": "242", "mnc": "01", "prefixes": ["4", "9"]}, {"name": "Telia NO", "mcc": "242", "mnc": "02", "prefixes": ["4", "9"]}]},
    "DK": {"name": "Denmark", "calling_code": "+45", "length": 8, "locale": "da_DK", "tz": "Europe/Copenhagen", "carriers": [{"name": "TDC", "mcc": "238", "mnc": "01", "prefixes": ["2", "3", "4", "5", "6", "7", "8", "9"]}, {"name": "Telenor DK", "mcc": "238", "mnc": "02", "prefixes": ["2", "3", "4", "5", "6", "7", "8", "9"]}]},
    "FI": {"name": "Finland", "calling_code": "+358", "length": 9, "locale": "fi_FI", "tz": "Europe/Helsinki", "carriers": [{"name": "Elisa", "mcc": "244", "mnc": "05", "prefixes": ["040", "050"]}, {"name": "Telia FI", "mcc": "244", "mnc": "91", "prefixes": ["040", "042"]}]},
    "CH": {"name": "Switzerland", "calling_code": "+41", "length": 9, "locale": "de_CH", "tz": "Europe/Zurich", "carriers": [{"name": "Swisscom", "mcc": "228", "mnc": "01", "prefixes": ["079", "078"]}, {"name": "Sunrise", "mcc": "228", "mnc": "02", "prefixes": ["076", "077"]}]},
    "AT": {"name": "Austria", "calling_code": "+43", "length": 10, "locale": "de_AT", "tz": "Europe/Vienna", "carriers": [{"name": "A1 Telekom", "mcc": "232", "mnc": "01", "prefixes": ["0664", "0680"]}, {"name": "Magenta Telekom", "mcc": "232", "mnc": "03", "prefixes": ["0676", "0650"]}]},
    "BE": {"name": "Belgium", "calling_code": "+32", "length": 9, "locale": "nl_BE", "tz": "Europe/Brussels", "carriers": [{"name": "Proximus", "mcc": "206", "mnc": "01", "prefixes": ["047"]}, {"name": "Orange BE", "mcc": "206", "mnc": "10", "prefixes": ["049"]}]},
    "PT": {"name": "Portugal", "calling_code": "+351", "length": 9, "locale": "pt_PT", "tz": "Europe/Lisbon", "carriers": [{"name": "MEO", "mcc": "268", "mnc": "06", "prefixes": ["96", "92"]}, {"name": "Vodafone PT", "mcc": "268", "mnc": "01", "prefixes": ["91", "93"]}]},
    "GR": {"name": "Greece", "calling_code": "+30", "length": 10, "locale": "el_GR", "tz": "Europe/Athens", "carriers": [{"name": "Cosmote", "mcc": "202", "mnc": "01", "prefixes": ["697", "698"]}, {"name": "Vodafone GR", "mcc": "202", "mnc": "05", "prefixes": ["694", "695"]}]},
    "CZ": {"name": "Czech Republic", "calling_code": "+420", "length": 9, "locale": "cs_CZ", "tz": "Europe/Prague", "carriers": [{"name": "T-Mobile CZ", "mcc": "230", "mnc": "01", "prefixes": ["60", "73"]}, {"name": "O2 CZ", "mcc": "230", "mnc": "02", "prefixes": ["72", "77"]}]},
    "RO": {"name": "Romania", "calling_code": "+40", "length": 9, "locale": "ro_RO", "tz": "Europe/Bucharest", "carriers": [{"name": "Orange RO", "mcc": "226", "mnc": "10", "prefixes": ["074", "075"]}, {"name": "Vodafone RO", "mcc": "226", "mnc": "01", "prefixes": ["072", "073"]}]},
    "HU": {"name": "Hungary", "calling_code": "+36", "length": 9, "locale": "hu_HU", "tz": "Europe/Budapest", "carriers": [{"name": "Telekom HU", "mcc": "216", "mnc": "30", "prefixes": ["30"]}, {"name": "Yettel", "mcc": "216", "mnc": "01", "prefixes": ["20"]}]},
    "NZ": {"name": "New Zealand", "calling_code": "+64", "length": 9, "locale": "en_NZ", "tz": "Pacific/Auckland", "carriers": [{"name": "Spark", "mcc": "530", "mnc": "05", "prefixes": ["027"]}, {"name": "One NZ", "mcc": "530", "mnc": "01", "prefixes": ["021"]}]},
    "IL": {"name": "Israel", "calling_code": "+972", "length": 9, "locale": "he_IL", "tz": "Asia/Jerusalem", "carriers": [{"name": "Cellcom", "mcc": "425", "mnc": "02", "prefixes": ["052"]}, {"name": "Partner", "mcc": "425", "mnc": "01", "prefixes": ["054"]}]},
    "PE": {"name": "Peru", "calling_code": "+51", "length": 9, "locale": "es_PE", "tz": "America/Lima", "carriers": [{"name": "Claro PE", "mcc": "716", "mnc": "10", "prefixes": ["9"]}, {"name": "Movistar PE", "mcc": "716", "mnc": "06", "prefixes": ["9"]}, {"name": "Entel PE", "mcc": "716", "mnc": "17", "prefixes": ["9"]}]},
    "EC": {"name": "Ecuador", "calling_code": "+593", "length": 9, "locale": "es_EC", "tz": "America/Guayaquil", "carriers": [{"name": "Claro EC", "mcc": "740", "mnc": "01", "prefixes": ["98", "99"]}, {"name": "Movistar EC", "mcc": "740", "mnc": "00", "prefixes": ["95", "96", "97"]}, {"name": "CNT Mobile", "mcc": "740", "mnc": "02", "prefixes": ["93", "94"]}]},
    "BO": {"name": "Bolivia", "calling_code": "+591", "length": 8, "locale": "es_BO", "tz": "America/La_Paz", "carriers": [{"name": "Entel BO", "mcc": "736", "mnc": "02", "prefixes": ["71", "72", "73", "74"]}, {"name": "Tigo BO", "mcc": "736", "mnc": "03", "prefixes": ["77", "78", "75", "76"]}]},
    "PY": {"name": "Paraguay", "calling_code": "+595", "length": 9, "locale": "es_PY", "tz": "America/Asuncion", "carriers": [{"name": "Tigo PY", "mcc": "744", "mnc": "01", "prefixes": ["981", "982", "983"]}, {"name": "Personal PY", "mcc": "744", "mnc": "05", "prefixes": ["971", "972"]}, {"name": "Claro PY", "mcc": "744", "mnc": "02", "prefixes": ["991", "992"]}]},
    "UY": {"name": "Uruguay", "calling_code": "+598", "length": 8, "locale": "es_UY", "tz": "America/Montevideo", "carriers": [{"name": "Antel", "mcc": "748", "mnc": "00", "prefixes": ["99", "98", "92"]}, {"name": "Movistar UY", "mcc": "748", "mnc": "07", "prefixes": ["94", "95"]}, {"name": "Claro UY", "mcc": "748", "mnc": "10", "prefixes": ["96", "97"]}]},
    "VE": {"name": "Venezuela", "calling_code": "+58", "length": 10, "locale": "es_VE", "tz": "America/Caracas", "carriers": [{"name": "Movistar VE", "mcc": "734", "mnc": "04", "prefixes": ["414", "424"]}, {"name": "Movilnet", "mcc": "734", "mnc": "06", "prefixes": ["416", "426"]}, {"name": "Digitel", "mcc": "734", "mnc": "02", "prefixes": ["412"]}]},
    "CR": {"name": "Costa Rica", "calling_code": "+506", "length": 8, "locale": "es_CR", "tz": "America/Costa_Rica", "carriers": [{"name": "Kolbi ICE", "mcc": "712", "mnc": "01", "prefixes": ["83", "84", "85", "86", "87", "88"]}, {"name": "Claro CR", "mcc": "712", "mnc": "03", "prefixes": ["70", "71", "72"]}, {"name": "Liberty CR", "mcc": "712", "mnc": "04", "prefixes": ["60", "61", "62"]}]},
    "PA": {"name": "Panama", "calling_code": "+507", "length": 8, "locale": "es_PA", "tz": "America/Panama", "carriers": [{"name": "+Movil", "mcc": "714", "mnc": "01", "prefixes": ["64", "65", "66", "67", "68"]}, {"name": "Tigo PA", "mcc": "714", "mnc": "020", "prefixes": ["60", "61", "62", "63"]}]},
    "GT": {"name": "Guatemala", "calling_code": "+502", "length": 8, "locale": "es_GT", "tz": "America/Guatemala", "carriers": [{"name": "Tigo GT", "mcc": "704", "mnc": "02", "prefixes": ["30", "31", "40", "41"]}, {"name": "Claro GT", "mcc": "704", "mnc": "01", "prefixes": ["50", "51", "52", "55"]}]},
    "HN": {"name": "Honduras", "calling_code": "+504", "length": 8, "locale": "es_HN", "tz": "America/Tegucigalpa", "carriers": [{"name": "Tigo HN", "mcc": "708", "mnc": "02", "prefixes": ["94", "95", "96", "97", "98"]}, {"name": "Claro HN", "mcc": "708", "mnc": "01", "prefixes": ["31", "32", "87", "88"]}]},
    "SV": {"name": "El Salvador", "calling_code": "+503", "length": 8, "locale": "es_SV", "tz": "America/El_Salvador", "carriers": [{"name": "Tigo SV", "mcc": "706", "mnc": "03", "prefixes": ["70", "71", "72"]}, {"name": "Claro SV", "mcc": "706", "mnc": "01", "prefixes": ["76", "77", "78"]}, {"name": "Movistar SV", "mcc": "706", "mnc": "02", "prefixes": ["60", "61"]}]},
    "NI": {"name": "Nicaragua", "calling_code": "+505", "length": 8, "locale": "es_NI", "tz": "America/Managua", "carriers": [{"name": "Claro NI", "mcc": "710", "mnc": "21", "prefixes": ["81", "82", "83", "84"]}, {"name": "Tigo NI", "mcc": "710", "mnc": "30", "prefixes": ["55", "57", "76", "77"]}]},
    "DO": {"name": "Dominican Republic", "calling_code": "+1809", "length": 10, "locale": "es_DO", "tz": "America/Santo_Domingo", "carriers": [{"name": "Claro DO", "mcc": "370", "mnc": "02", "prefixes": ["809", "829", "849"]}, {"name": "Altice DO", "mcc": "370", "mnc": "01", "prefixes": ["809", "829", "849"]}]},
    "JM": {"name": "Jamaica", "calling_code": "+1876", "length": 10, "locale": "en_JM", "tz": "America/Jamaica", "carriers": [{"name": "Digicel JM", "mcc": "338", "mnc": "05", "prefixes": ["876"]}, {"name": "Flow JM", "mcc": "338", "mnc": "180", "prefixes": ["876"]}]},
    "TT": {"name": "Trinidad and Tobago", "calling_code": "+1868", "length": 10, "locale": "en_TT", "tz": "America/Port_of_Spain", "carriers": [{"name": "bmobile", "mcc": "374", "mnc": "12", "prefixes": ["868"]}, {"name": "Digicel TT", "mcc": "374", "mnc": "130", "prefixes": ["868"]}]},
    "IE": {"name": "Ireland", "calling_code": "+353", "length": 9, "locale": "en_IE", "tz": "Europe/Dublin", "carriers": [{"name": "Vodafone IE", "mcc": "272", "mnc": "01", "prefixes": ["87"]}, {"name": "Three IE", "mcc": "272", "mnc": "02", "prefixes": ["83", "86"]}, {"name": "Eir", "mcc": "272", "mnc": "03", "prefixes": ["85"]}]},
    "IS": {"name": "Iceland", "calling_code": "+354", "length": 7, "locale": "is_IS", "tz": "Atlantic/Reykjavik", "carriers": [{"name": "Siminn", "mcc": "274", "mnc": "01", "prefixes": ["6", "7", "8"]}, {"name": "Vodafone IS", "mcc": "274", "mnc": "02", "prefixes": ["6", "7", "8"]}]},
    "BG": {"name": "Bulgaria", "calling_code": "+359", "length": 9, "locale": "bg_BG", "tz": "Europe/Sofia", "carriers": [{"name": "A1 Bulgaria", "mcc": "284", "mnc": "01", "prefixes": ["88"]}, {"name": "Yettel BG", "mcc": "284", "mnc": "05", "prefixes": ["89"]}, {"name": "Vivacom", "mcc": "284", "mnc": "03", "prefixes": ["87"]}]},
    "HR": {"name": "Croatia", "calling_code": "+385", "length": 9, "locale": "hr_HR", "tz": "Europe/Zagreb", "carriers": [{"name": "Hrvatski Telekom", "mcc": "219", "mnc": "01", "prefixes": ["98", "99"]}, {"name": "A1 Hrvatska", "mcc": "219", "mnc": "10", "prefixes": ["91", "92"]}, {"name": "Telemach HR", "mcc": "219", "mnc": "02", "prefixes": ["95"]}]},
    "RS": {"name": "Serbia", "calling_code": "+381", "length": 9, "locale": "sr_RS", "tz": "Europe/Belgrade", "carriers": [{"name": "MTS", "mcc": "220", "mnc": "03", "prefixes": ["64", "65", "66"]}, {"name": "Yettel RS", "mcc": "220", "mnc": "01", "prefixes": ["62", "63"]}, {"name": "A1 Srbija", "mcc": "220", "mnc": "05", "prefixes": ["60", "61"]}]},
    "SK": {"name": "Slovakia", "calling_code": "+421", "length": 9, "locale": "sk_SK", "tz": "Europe/Bratislava", "carriers": [{"name": "Orange SK", "mcc": "231", "mnc": "01", "prefixes": ["905", "907", "915"]}, {"name": "Telekom SK", "mcc": "231", "mnc": "02", "prefixes": ["903", "911"]}, {"name": "O2 SK", "mcc": "231", "mnc": "06", "prefixes": ["948", "949"]}]},
    "SI": {"name": "Slovenia", "calling_code": "+386", "length": 8, "locale": "sl_SI", "tz": "Europe/Ljubljana", "carriers": [{"name": "Telekom Slovenije", "mcc": "293", "mnc": "41", "prefixes": ["31", "41", "51"]}, {"name": "A1 Slovenija", "mcc": "293", "mnc": "40", "prefixes": ["40"]}, {"name": "Telemach SI", "mcc": "293", "mnc": "70", "prefixes": ["70"]}]},
    "LT": {"name": "Lithuania", "calling_code": "+370", "length": 8, "locale": "lt_LT", "tz": "Europe/Vilnius", "carriers": [{"name": "Tele2 LT", "mcc": "246", "mnc": "03", "prefixes": ["6"]}, {"name": "Telia LT", "mcc": "246", "mnc": "01", "prefixes": ["6"]}, {"name": "Bite LT", "mcc": "246", "mnc": "02", "prefixes": ["6"]}]},
    "LV": {"name": "Latvia", "calling_code": "+371", "length": 8, "locale": "lv_LV", "tz": "Europe/Riga", "carriers": [{"name": "LMT", "mcc": "247", "mnc": "01", "prefixes": ["2"]}, {"name": "Tele2 LV", "mcc": "247", "mnc": "02", "prefixes": ["2"]}, {"name": "Bite LV", "mcc": "247", "mnc": "05", "prefixes": ["2"]}]},
    "EE": {"name": "Estonia", "calling_code": "+372", "length": 8, "locale": "et_EE", "tz": "Europe/Tallinn", "carriers": [{"name": "Telia EE", "mcc": "248", "mnc": "01", "prefixes": ["50", "51", "52"]}, {"name": "Elisa EE", "mcc": "248", "mnc": "02", "prefixes": ["56", "57"]}, {"name": "Tele2 EE", "mcc": "248", "mnc": "03", "prefixes": ["55", "58"]}]},
    "CY": {"name": "Cyprus", "calling_code": "+357", "length": 8, "locale": "el_CY", "tz": "Asia/Nicosia", "carriers": [{"name": "Cyta", "mcc": "280", "mnc": "01", "prefixes": ["99", "97"]}, {"name": "Epic CY", "mcc": "280", "mnc": "10", "prefixes": ["96"]}]},
    "LU": {"name": "Luxembourg", "calling_code": "+352", "length": 9, "locale": "fr_LU", "tz": "Europe/Luxembourg", "carriers": [{"name": "POST Luxembourg", "mcc": "270", "mnc": "01", "prefixes": ["621"]}, {"name": "Orange LU", "mcc": "270", "mnc": "99", "prefixes": ["661"]}]},
    "MT": {"name": "Malta", "calling_code": "+356", "length": 8, "locale": "mt_MT", "tz": "Europe/Malta", "carriers": [{"name": "Epic MT", "mcc": "278", "mnc": "01", "prefixes": ["99"]}, {"name": "GO Mobile", "mcc": "278", "mnc": "21", "prefixes": ["79"]}]},
    "AL": {"name": "Albania", "calling_code": "+355", "length": 9, "locale": "sq_AL", "tz": "Europe/Tirane", "carriers": [{"name": "Vodafone AL", "mcc": "276", "mnc": "01", "prefixes": ["69"]}, {"name": "ONE AL", "mcc": "276", "mnc": "03", "prefixes": ["68"]}]},
    "MK": {"name": "North Macedonia", "calling_code": "+389", "length": 8, "locale": "mk_MK", "tz": "Europe/Skopje", "carriers": [{"name": "Makedonski Telekom", "mcc": "294", "mnc": "01", "prefixes": ["70", "71", "72"]}, {"name": "A1 Macedonia", "mcc": "294", "mnc": "03", "prefixes": ["75", "76", "77"]}]},
    "BA": {"name": "Bosnia and Herzegovina", "calling_code": "+387", "length": 8, "locale": "bs_BA", "tz": "Europe/Sarajevo", "carriers": [{"name": "BH Telecom", "mcc": "218", "mnc": "90", "prefixes": ["61", "62"]}, {"name": "m:tel", "mcc": "218", "mnc": "05", "prefixes": ["65", "66"]}]},
    "ME": {"name": "Montenegro", "calling_code": "+382", "length": 8, "locale": "sr_ME", "tz": "Europe/Podgorica", "carriers": [{"name": "Crnogorski Telekom", "mcc": "297", "mnc": "02", "prefixes": ["67"]}, {"name": "One ME", "mcc": "297", "mnc": "01", "prefixes": ["69"]}]},
    "MD": {"name": "Moldova", "calling_code": "+373", "length": 8, "locale": "ro_MD", "tz": "Europe/Chisinau", "carriers": [{"name": "Orange MD", "mcc": "259", "mnc": "01", "prefixes": ["68", "69"]}, {"name": "Moldcell", "mcc": "259", "mnc": "02", "prefixes": ["78", "79"]}]},
    "BY": {"name": "Belarus", "calling_code": "+375", "length": 9, "locale": "be_BY", "tz": "Europe/Minsk", "carriers": [{"name": "A1 BY", "mcc": "257", "mnc": "01", "prefixes": ["29", "44"]}, {"name": "MTS BY", "mcc": "257", "mnc": "02", "prefixes": ["29", "33"]}]},
    "KZ": {"name": "Kazakhstan", "calling_code": "+7", "length": 10, "locale": "kk_KZ", "tz": "Asia/Almaty", "carriers": [{"name": "Kcell", "mcc": "401", "mnc": "02", "prefixes": ["701", "702", "775"]}, {"name": "Beeline KZ", "mcc": "401", "mnc": "01", "prefixes": ["705", "771", "777"]}, {"name": "Tele2 KZ", "mcc": "401", "mnc": "77", "prefixes": ["707", "747"]}]},
    "UZ": {"name": "Uzbekistan", "calling_code": "+998", "length": 9, "locale": "uz_UZ", "tz": "Asia/Tashkent", "carriers": [{"name": "Ucell", "mcc": "434", "mnc": "05", "prefixes": ["93", "94"]}, {"name": "Beeline UZ", "mcc": "434", "mnc": "04", "prefixes": ["90", "91"]}, {"name": "Mobiuz", "mcc": "434", "mnc": "07", "prefixes": ["97", "88"]}]},
    "GE": {"name": "Georgia", "calling_code": "+995", "length": 9, "locale": "ka_GE", "tz": "Asia/Tbilisi", "carriers": [{"name": "MagtiCom", "mcc": "282", "mnc": "02", "prefixes": ["595", "599"]}, {"name": "Silknet", "mcc": "282", "mnc": "01", "prefixes": ["577", "593"]}]},
    "AM": {"name": "Armenia", "calling_code": "+374", "length": 8, "locale": "hy_AM", "tz": "Asia/Yerevan", "carriers": [{"name": "Viva-MTS", "mcc": "283", "mnc": "05", "prefixes": ["77", "93", "94"]}, {"name": "Team Telecom", "mcc": "283", "mnc": "01", "prefixes": ["91", "96", "99"]}]},
    "AZ": {"name": "Azerbaijan", "calling_code": "+994", "length": 9, "locale": "az_AZ", "tz": "Asia/Baku", "carriers": [{"name": "Azercell", "mcc": "400", "mnc": "01", "prefixes": ["50", "51"]}, {"name": "Bakcell", "mcc": "400", "mnc": "02", "prefixes": ["55", "99"]}]},
    "KG": {"name": "Kyrgyzstan", "calling_code": "+996", "length": 9, "locale": "ky_KG", "tz": "Asia/Bishkek", "carriers": [{"name": "MegaCom", "mcc": "437", "mnc": "05", "prefixes": ["550", "555"]}, {"name": "Beeline KG", "mcc": "437", "mnc": "01", "prefixes": ["770", "772"]}]},
    "TJ": {"name": "Tajikistan", "calling_code": "+992", "length": 9, "locale": "tg_TJ", "tz": "Asia/Dushanbe", "carriers": [{"name": "Tcell", "mcc": "436", "mnc": "01", "prefixes": ["93", "92"]}, {"name": "MegaFon TJ", "mcc": "436", "mnc": "03", "prefixes": ["90", "88"]}]},
    "MN": {"name": "Mongolia", "calling_code": "+976", "length": 8, "locale": "mn_MN", "tz": "Asia/Ulaanbaatar", "carriers": [{"name": "Mobicom", "mcc": "428", "mnc": "99", "prefixes": ["99", "94"]}, {"name": "Unitel", "mcc": "428", "mnc": "88", "prefixes": ["88", "86"]}]},
    "MA": {"name": "Morocco", "calling_code": "+212", "length": 9, "locale": "ar_MA", "tz": "Africa/Casablanca", "carriers": [{"name": "Maroc Telecom", "mcc": "604", "mnc": "01", "prefixes": ["61", "66"]}, {"name": "Orange MA", "mcc": "604", "mnc": "00", "prefixes": ["63", "67"]}, {"name": "inwi", "mcc": "604", "mnc": "02", "prefixes": ["64", "70"]}]},
    "DZ": {"name": "Algeria", "calling_code": "+213", "length": 9, "locale": "ar_DZ", "tz": "Africa/Algiers", "carriers": [{"name": "Mobilis", "mcc": "603", "mnc": "01", "prefixes": ["65", "66"]}, {"name": "Djezzy", "mcc": "603", "mnc": "02", "prefixes": ["77", "79"]}]},
    "TN": {"name": "Tunisia", "calling_code": "+216", "length": 8, "locale": "ar_TN", "tz": "Africa/Tunis", "carriers": [{"name": "Tunisie Telecom", "mcc": "605", "mnc": "02", "prefixes": ["9"]}, {"name": "Ooredoo TN", "mcc": "605", "mnc": "01", "prefixes": ["2"]}, {"name": "Orange TN", "mcc": "605", "mnc": "03", "prefixes": ["5"]}]},
    "KW": {"name": "Kuwait", "calling_code": "+965", "length": 8, "locale": "ar_KW", "tz": "Asia/Kuwait", "carriers": [{"name": "Zain KW", "mcc": "419", "mnc": "02", "prefixes": ["9"]}, {"name": "Ooredoo KW", "mcc": "419", "mnc": "03", "prefixes": ["6"]}, {"name": "STC KW", "mcc": "419", "mnc": "04", "prefixes": ["5"]}]},
    "QA": {"name": "Qatar", "calling_code": "+974", "length": 8, "locale": "ar_QA", "tz": "Asia/Qatar", "carriers": [{"name": "Ooredoo QA", "mcc": "427", "mnc": "01", "prefixes": ["55", "66"]}, {"name": "Vodafone QA", "mcc": "427", "mnc": "02", "prefixes": ["77", "70"]}]},
    "BH": {"name": "Bahrain", "calling_code": "+973", "length": 8, "locale": "ar_BH", "tz": "Asia/Bahrain", "carriers": [{"name": "Batelco", "mcc": "426", "mnc": "01", "prefixes": ["39", "38"]}, {"name": "Zain BH", "mcc": "426", "mnc": "02", "prefixes": ["36", "37"]}]},
    "OM": {"name": "Oman", "calling_code": "+968", "length": 8, "locale": "ar_OM", "tz": "Asia/Muscat", "carriers": [{"name": "Omantel", "mcc": "422", "mnc": "02", "prefixes": ["91", "92", "99"]}, {"name": "Ooredoo OM", "mcc": "422", "mnc": "03", "prefixes": ["94", "95", "96"]}]},
    "JO": {"name": "Jordan", "calling_code": "+962", "length": 9, "locale": "ar_JO", "tz": "Asia/Amman", "carriers": [{"name": "Zain JO", "mcc": "416", "mnc": "01", "prefixes": ["79"]}, {"name": "Orange JO", "mcc": "416", "mnc": "77", "prefixes": ["77"]}]},
    "LB": {"name": "Lebanon", "calling_code": "+961", "length": 8, "locale": "ar_LB", "tz": "Asia/Beirut", "carriers": [{"name": "Touch", "mcc": "415", "mnc": "03", "prefixes": ["70", "76", "81"]}, {"name": "Alfa", "mcc": "415", "mnc": "01", "prefixes": ["71", "79"]}]},
    "IQ": {"name": "Iraq", "calling_code": "+964", "length": 10, "locale": "ar_IQ", "tz": "Asia/Baghdad", "carriers": [{"name": "Zain IQ", "mcc": "418", "mnc": "20", "prefixes": ["78", "79"]}, {"name": "Asiacell", "mcc": "418", "mnc": "05", "prefixes": ["77"]}]},
    "IR": {"name": "Iran", "calling_code": "+98", "length": 10, "locale": "fa_IR", "tz": "Asia/Tehran", "carriers": [{"name": "MCI", "mcc": "432", "mnc": "11", "prefixes": ["912", "919"]}, {"name": "MTN Irancell", "mcc": "432", "mnc": "35", "prefixes": ["935", "936"]}]},
    "KE": {"name": "Kenya", "calling_code": "+254", "length": 9, "locale": "sw_KE", "tz": "Africa/Nairobi", "carriers": [{"name": "Safaricom", "mcc": "639", "mnc": "02", "prefixes": ["70", "71", "72"]}, {"name": "Airtel KE", "mcc": "639", "mnc": "03", "prefixes": ["73", "75"]}]},
    "GH": {"name": "Ghana", "calling_code": "+233", "length": 9, "locale": "en_GH", "tz": "Africa/Accra", "carriers": [{"name": "MTN GH", "mcc": "620", "mnc": "01", "prefixes": ["24", "54", "55"]}, {"name": "Vodafone GH", "mcc": "620", "mnc": "02", "prefixes": ["20", "50"]}]},
    "CI": {"name": "Ivory Coast", "calling_code": "+225", "length": 10, "locale": "fr_CI", "tz": "Africa/Abidjan", "carriers": [{"name": "Orange CI", "mcc": "612", "mnc": "03", "prefixes": ["07"]}, {"name": "MTN CI", "mcc": "612", "mnc": "05", "prefixes": ["05"]}]},
    "SN": {"name": "Senegal", "calling_code": "+221", "length": 9, "locale": "fr_SN", "tz": "Africa/Dakar", "carriers": [{"name": "Orange SN", "mcc": "608", "mnc": "01", "prefixes": ["77", "78"]}, {"name": "Free SN", "mcc": "608", "mnc": "02", "prefixes": ["76"]}]},
    "CM": {"name": "Cameroon", "calling_code": "+237", "length": 9, "locale": "fr_CM", "tz": "Africa/Douala", "carriers": [{"name": "MTN CM", "mcc": "624", "mnc": "01", "prefixes": ["67", "68"]}, {"name": "Orange CM", "mcc": "624", "mnc": "02", "prefixes": ["69", "65"]}]},
    "UG": {"name": "Uganda", "calling_code": "+256", "length": 9, "locale": "en_UG", "tz": "Africa/Kampala", "carriers": [{"name": "MTN UG", "mcc": "641", "mnc": "10", "prefixes": ["77", "78"]}, {"name": "Airtel UG", "mcc": "641", "mnc": "01", "prefixes": ["70", "75"]}]},
    "ET": {"name": "Ethiopia", "calling_code": "+251", "length": 9, "locale": "am_ET", "tz": "Africa/Addis_Ababa", "carriers": [{"name": "Ethio Telecom", "mcc": "636", "mnc": "01", "prefixes": ["9"]}, {"name": "Safaricom ET", "mcc": "636", "mnc": "02", "prefixes": ["7"]}]},
    "TZ": {"name": "Tanzania", "calling_code": "+255", "length": 9, "locale": "sw_TZ", "tz": "Africa/Dar_es_Salaam", "carriers": [{"name": "Vodacom TZ", "mcc": "640", "mnc": "04", "prefixes": ["74", "75"]}, {"name": "Airtel TZ", "mcc": "640", "mnc": "05", "prefixes": ["68", "69"]}]},
    "LK": {"name": "Sri Lanka", "calling_code": "+94", "length": 9, "locale": "si_LK", "tz": "Asia/Colombo", "carriers": [{"name": "Dialog", "mcc": "413", "mnc": "02", "prefixes": ["77", "76"]}, {"name": "Mobitel", "mcc": "413", "mnc": "01", "prefixes": ["71", "70"]}]},
    "NP": {"name": "Nepal", "calling_code": "+977", "length": 10, "locale": "ne_NP", "tz": "Asia/Kathmandu", "carriers": [{"name": "Ncell", "mcc": "429", "mnc": "02", "prefixes": ["980", "981"]}, {"name": "Nepal Telecom", "mcc": "429", "mnc": "01", "prefixes": ["984", "985"]}]},
    "BN": {"name": "Brunei", "calling_code": "+673", "length": 7, "locale": "ms_BN", "tz": "Asia/Brunei", "carriers": [{"name": "DST", "mcc": "528", "mnc": "11", "prefixes": ["7", "8"]}, {"name": "Progresif", "mcc": "528", "mnc": "02", "prefixes": ["7", "8"]}]},
    "MO": {"name": "Macau", "calling_code": "+853", "length": 8, "locale": "zh_MO", "tz": "Asia/Macau", "carriers": [{"name": "CTM", "mcc": "455", "mnc": "01", "prefixes": ["66", "68"]}, {"name": "3 Macau", "mcc": "455", "mnc": "03", "prefixes": ["62", "63"]}]},
    "FJ": {"name": "Fiji", "calling_code": "+679", "length": 7, "locale": "en_FJ", "tz": "Pacific/Fiji", "carriers": [{"name": "Vodafone FJ", "mcc": "542", "mnc": "01", "prefixes": ["7", "8", "9"]}, {"name": "Digicel FJ", "mcc": "542", "mnc": "02", "prefixes": ["7", "8"]}]},
    "PG": {"name": "Papua New Guinea", "calling_code": "+675", "length": 8, "locale": "en_PG", "tz": "Pacific/Port_Moresby", "carriers": [{"name": "Digicel PNG", "mcc": "537", "mnc": "01", "prefixes": ["7"]}, {"name": "Telikom PNG", "mcc": "537", "mnc": "03", "prefixes": ["7"]}]},
    "MV": {"name": "Maldives", "calling_code": "+960", "length": 7, "locale": "dv_MV", "tz": "Indian/Maldives", "carriers": [{"name": "Dhiraagu", "mcc": "472", "mnc": "01", "prefixes": ["7", "9"]}, {"name": "Ooredoo MV", "mcc": "472", "mnc": "02", "prefixes": ["7", "9"]}]},
}



WORLD_CALLING_CODES = {
    "AQ": "+672", "EH": "+212", "GS": "+500", "PN": "+64", "UM": "+1", "AD": "+376", "AE": "+971", "AF": "+93", "AG": "+1268", "AI": "+1264", "AL": "+355", "AM": "+374", "AO": "+244",
    "AR": "+54", "AS": "+1684", "AT": "+43", "AU": "+61", "AW": "+297", "AX": "+358", "AZ": "+994", "BA": "+387",
    "BB": "+1246", "BD": "+880", "BE": "+32", "BF": "+226", "BG": "+359", "BH": "+973", "BI": "+257", "BJ": "+229",
    "BL": "+590", "BM": "+1441", "BN": "+673", "BO": "+591", "BQ": "+599", "BR": "+55", "BS": "+1242", "BT": "+975",
    "BW": "+267", "BY": "+375", "BZ": "+501", "CA": "+1", "CC": "+61", "CD": "+243", "CF": "+236", "CG": "+242",
    "CH": "+41", "CI": "+225", "CK": "+682", "CL": "+56", "CM": "+237", "CN": "+86", "CO": "+57", "CR": "+506",
    "CU": "+53", "CV": "+238", "CW": "+599", "CX": "+61", "CY": "+357", "CZ": "+420", "DE": "+49", "DJ": "+253",
    "DK": "+45", "DM": "+1767", "DO": "+1809", "DZ": "+213", "EC": "+593", "EE": "+372", "EG": "+20", "ER": "+291",
    "ES": "+34", "ET": "+251", "FI": "+358", "FJ": "+679", "FK": "+500", "FM": "+691", "FO": "+298", "FR": "+33",
    "GA": "+241", "GB": "+44", "GD": "+1473", "GE": "+995", "GF": "+594", "GG": "+44", "GH": "+233", "GI": "+350",
    "GL": "+299", "GM": "+220", "GN": "+224", "GP": "+590", "GQ": "+240", "GR": "+30", "GT": "+502", "GU": "+1671",
    "GW": "+245", "GY": "+592", "HK": "+852", "HN": "+504", "HR": "+385", "HT": "+509", "HU": "+36", "ID": "+62",
    "IE": "+353", "IL": "+972", "IM": "+44", "IN": "+91", "IO": "+246", "IQ": "+964", "IR": "+98", "IS": "+354",
    "IT": "+39", "JE": "+44", "JM": "+1876", "JO": "+962", "JP": "+81", "KE": "+254", "KG": "+996", "KH": "+855",
    "KI": "+686", "KM": "+269", "KN": "+1869", "KP": "+850", "KR": "+82", "KW": "+965", "KY": "+1345", "KZ": "+7",
    "LA": "+856", "LB": "+961", "LC": "+1758", "LI": "+423", "LK": "+94", "LR": "+231", "LS": "+266", "LT": "+370",
    "LU": "+352", "LV": "+371", "LY": "+218", "MA": "+212", "MC": "+377", "MD": "+373", "ME": "+382", "MF": "+590",
    "MG": "+261", "MH": "+692", "MK": "+389", "ML": "+223", "MM": "+95", "MN": "+976", "MO": "+853", "MP": "+1670",
    "MQ": "+596", "MR": "+222", "MS": "+1664", "MT": "+356", "MU": "+230", "MV": "+960", "MW": "+265", "MX": "+52",
    "MY": "+60", "MZ": "+258", "NA": "+264", "NC": "+687", "NE": "+227", "NF": "+672", "NG": "+234", "NI": "+505",
    "NL": "+31", "NO": "+47", "NP": "+977", "NR": "+674", "NU": "+683", "NZ": "+64", "OM": "+968", "PA": "+507",
    "PE": "+51", "PF": "+689", "PG": "+675", "PH": "+63", "PK": "+92", "PL": "+48", "PM": "+508", "PR": "+1787",
    "PS": "+970", "PT": "+351", "PW": "+680", "PY": "+595", "QA": "+974", "RE": "+262", "RO": "+40", "RS": "+381",
    "RU": "+7", "RW": "+250", "SA": "+966", "SB": "+677", "SC": "+248", "SD": "+249", "SE": "+46", "SG": "+65",
    "SH": "+290", "SI": "+386", "SJ": "+47", "SK": "+421", "SL": "+232", "SM": "+378", "SN": "+221", "SO": "+252",
    "SR": "+597", "SS": "+211", "ST": "+239", "SV": "+503", "SX": "+1721", "SY": "+963", "SZ": "+268", "TC": "+1649",
    "TD": "+235", "TG": "+228", "TH": "+66", "TJ": "+992", "TK": "+690", "TL": "+670", "TM": "+993", "TN": "+216",
    "TO": "+676", "TR": "+90", "TT": "+1868", "TV": "+688", "TW": "+886", "TZ": "+255", "UA": "+380", "UG": "+256",
    "US": "+1", "UY": "+598", "UZ": "+998", "VA": "+379", "VC": "+1784", "VE": "+58", "VG": "+1284", "VI": "+1340",
    "VN": "+84", "VU": "+678", "WF": "+681", "WS": "+685", "YE": "+967", "YT": "+262", "ZA": "+27", "ZM": "+260", "ZW": "+263"
}

DEFAULT_COUNTRY_ENTRY = COUNTRY_TELEPHONY_DATABASE["VN"]

MNO_PREFIXES = {
    "viettel": ["098", "097", "096", "086", "039", "038", "037", "036", "035", "034", "033", "032"],
    "vinaphone": ["091", "094", "088", "081", "082", "083", "084", "085"],
    "mobifone": ["090", "093", "089", "070", "076", "077", "078", "079"],
    "vietnamobile": ["092", "056", "058"],
    "gmobile": ["099", "059"],
    "wintel": ["055"],
}


class OfflineGeoIP:
    """Tra cuu dai IPv4 toan cau Offline sieu toc (0 network request, 5-10 microseconds)."""
    _starts = []
    _ends = []
    _codes = []
    _loaded = False
    _load_lock = threading.Lock()

    @classmethod
    def load(cls) -> None:
        if cls._loaded:
            return
        with cls._load_lock:
            if cls._loaded:
                return
            bin_path = os.path.join(os.path.dirname(__file__), "ip2country.bin")
            if not os.path.exists(bin_path):
                alt_path = "core/ip2country.bin"
                if os.path.exists(alt_path):
                    bin_path = alt_path
                else:
                    return
            try:
                import struct
                with open(bin_path, "rb") as f:
                    data = f.read()
                n = len(data) // 10
                cls._starts = [0] * n
                cls._ends = [0] * n
                cls._codes = [""] * n
                for i, (s, e, c) in enumerate(struct.iter_unpack("!II2s", data)):
                    cls._starts[i] = s
                    cls._ends[i] = e
                    cls._codes[i] = c.decode("ascii")
                cls._loaded = True
            except Exception as e:
                logger.debug(f"OfflineGeoIP load error: {e}")

    @classmethod
    def lookup(cls, ip_str: str):
        if not cls._loaded:
            cls.load()
        if not cls._loaded or not cls._starts:
            return None
        try:
            import struct, socket, bisect
            ip_int = struct.unpack("!I", socket.inet_aton(ip_str))[0]
            idx = bisect.bisect_right(cls._starts, ip_int) - 1
            if idx >= 0 and cls._starts[idx] <= ip_int <= cls._ends[idx]:
                return cls._codes[idx]
        except Exception:
            pass
        return None


class GeoTelephonyResolver:
    """Bo may phan giai dia ly IP & doi soat nha mang vien thong tu dong kem bo nho dem."""

    _CACHE: Dict[str, GeoTelephonyProfile] = {}
    _CACHE_FILE: str = "geoip_cache.json"
    _LOCK = threading.Lock()

    @classmethod
    def _load_cache(cls) -> None:
        if not cls._CACHE and os.path.exists(cls._CACHE_FILE):
            try:
                with open(cls._CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for ip_key, d in data.items():
                        cls._CACHE[ip_key] = GeoTelephonyProfile(**d)
            except Exception as e:
                logger.debug(f"Error reading geoip cache: {e}")

    _LAST_SAVE_TIME: float = 0.0
    _DIRTY_COUNT: int = 0

    @classmethod
    def _save_cache(cls, force: bool = False) -> None:
        cls._DIRTY_COUNT += 1
        now = time.time()
        if not force and cls._DIRTY_COUNT < 20 and (now - cls._LAST_SAVE_TIME) < 10.0:
            return
        cls._DIRTY_COUNT = 0
        cls._LAST_SAVE_TIME = now
        try:
            with open(cls._CACHE_FILE, "w", encoding="utf-8") as f:
                dump_data = {k: v.__dict__ for k, v in cls._CACHE.items()}
                json.dump(dump_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"Error saving geoip cache: {e}")

    @classmethod
    def get_profile_for_country(
        cls,
        country_code: str,
        ip: str = "127.0.0.1",
        city: str = "",
        timezone: str = "",
        isp_name: str = ""
    ) -> GeoTelephonyProfile:
        code = normalize_country_code(country_code) or "VN"
        data = COUNTRY_TELEPHONY_DATABASE.get(code)
        if not data and code in GLOBAL_COUNTRY_CALLING_CODES:
            g_info = GLOBAL_COUNTRY_CALLING_CODES[code]
            data = {
                "country_name": g_info["name"],
                "locale": g_info.get("locale", f"en_{code}"),
                "accept_language": f"{g_info.get('locale', 'en')},en;q=0.9",
                "timezones": [g_info.get("tz", "UTC")],
                "timezone_offset": 0,
                "phone_calling_code": g_info["calling_code"],
                "phone_length": g_info["length"],
                "carriers": g_info["carriers"],
            }

        if not data:
            c_calling = WORLD_CALLING_CODES.get(code)
            if not c_calling:
                c_calling = "+1"
            clean_calling = c_calling.lstrip("+")
            # Chuẩn hóa tự động ITU-T E.164 Dynamic Telephony:
            # Chiều dài thuê bao di động tương thích quy chuẩn quốc gia và tổng độ dài <= 15 ký tự E.164.
            if len(clean_calling) == 1:
                dynamic_len = 10
            elif len(clean_calling) == 2:
                dynamic_len = 9
            elif len(clean_calling) == 3:
                dynamic_len = 8
            else:
                dynamic_len = 7

            dynamic_prefixes = ["7", "8", "9"]
            data = DEFAULT_COUNTRY_ENTRY if code == "VN" else {
                "country_name": f"Country {code}",
                "locale": f"en_{code}",
                "accept_language": f"en-{code},en;q=0.9",
                "timezones": ["UTC"],
                "timezone_offset": 0,
                "phone_calling_code": c_calling,
                "phone_length": dynamic_len,
                "carriers": [
                    {
                        "name": f"{code} Telecom",
                        "mcc": "901",
                        "mnc": "01",
                        "prefixes": dynamic_prefixes,
                    }
                ],
            }

        chosen_tz = timezone or (random.choice(data["timezones"]) if data.get("timezones") else "Asia/Ho_Chi_Minh")
        chosen_city = city or (data["country_name"] if code != "VN" else "Hanoi")

        carriers = data.get("carriers") or [{"name": "Carrier", "mcc": "999", "mnc": "01", "prefixes": ["999"]}]
        matched_carrier = None
        if isp_name:
            isp_lower = isp_name.lower()
            for c in carriers:
                if c["name"].lower() in isp_lower:
                    matched_carrier = c
                    break

        if not matched_carrier:
            matched_carrier = random.choice(carriers)

        mcc = matched_carrier["mcc"]
        mnc = matched_carrier["mnc"]
        operator_num = f"{mcc}{mnc}"

        return GeoTelephonyProfile(
            ip=ip,
            country_code=code,
            country_name=data["country_name"],
            city=chosen_city,
            region=chosen_city,
            timezone=chosen_tz,
            timezone_offset_minutes=data.get("timezone_offset", 420),
            locale=data.get("locale", "vi_VN"),
            accept_language=data.get("accept_language", "vi-VN,vi;q=0.9"),
            carrier_name=matched_carrier["name"],
            mcc=mcc,
            mnc=mnc,
            operator_numeric=operator_num,
            sim_country_iso=code.lower(),
            phone_calling_code=data["phone_calling_code"],
            phone_prefixes=list(matched_carrier.get("prefixes", ["098"])),
            phone_number_length=data.get("phone_length", 10),
            soc_preference="Qualcomm Snapdragon 8 Gen 2" if code in ("US", "VN", "DE") else "MediaTek Dimensity 9200+",
            gl_renderer_preference="Adreno (TM) 740" if code in ("US", "VN", "DE") else "Mali-G715",
        )

    @classmethod
    def resolve_ip(
        cls,
        ip_or_host: str,
        hint_country: Optional[str] = None,
        proxy: Optional[str] = None,
        timeout: float = 2.5
    ) -> GeoTelephonyProfile:
        clean_ip = (ip_or_host or "").strip()
        if "://" in clean_ip:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(clean_ip)
                clean_ip = parsed.hostname or clean_ip
            except Exception:
                pass
        if "@" in clean_ip:
            clean_ip = clean_ip.split("@")[-1]
        if ":" in clean_ip:
            clean_ip = clean_ip.split(":")[0]
        clean_ip = clean_ip.strip()

        hint_c = normalize_country_code(hint_country)

        if not clean_ip or clean_ip.lower() in ("127.0.0.1", "localhost", "direct", "none", "0.0.0.0"):
            if hint_c:
                return cls.get_profile_for_country(hint_c, ip="Direct", city="Hanoi" if hint_c == "VN" else "")
            return cls.get_profile_for_country("VN", ip="Direct", city="Hanoi")

        with cls._LOCK:
            cls._load_cache()
            if clean_ip in cls._CACHE:
                cached = cls._CACHE[clean_ip]
                if hint_c and cached.country_code != hint_c and hint_c != "VN":
                    pass
                else:
                    return cached

        is_ipv4 = bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", clean_ip))
        if not is_ipv4 and clean_ip and not clean_ip.startswith("http"):
            try:
                import socket
                resolved_ip = socket.gethostbyname(clean_ip)
                if resolved_ip and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", resolved_ip):
                    clean_ip = resolved_ip
                    is_ipv4 = True
            except Exception:
                pass

        if is_ipv4:
            # 0. Tra cuu tuc thi Offline qua CSDL dai IP toan cau (10 microsecond, 0 network, khong gioi han luong)
            try:
                offline_c = OfflineGeoIP.lookup(clean_ip)
                if offline_c:
                    profile = cls.get_profile_for_country(
                        country_code=offline_c,
                        ip=clean_ip,
                    )
                    with cls._LOCK:
                        cls._CACHE[clean_ip] = profile
                        cls._save_cache()
                    return profile
            except Exception:
                pass

            # 0. Tra cứu siêu tốc ip2c.org (20-40ms, không giới hạn request/phút)
            try:
                r_c = requests.get(f"http://ip2c.org/{clean_ip}", timeout=1.8)
                if r_c.status_code == 200 and r_c.text.startswith("1;"):
                    parts = r_c.text.strip().split(";")
                    if len(parts) >= 2 and len(parts[1]) == 2:
                        found_code = parts[1].upper()
                        country_full = parts[3] if len(parts) >= 4 else ""
                        profile = cls.get_profile_for_country(
                            country_code=found_code,
                            ip=clean_ip,
                            city=country_full
                        )
                        with cls._LOCK:
                            cls._CACHE[clean_ip] = profile
                            cls._save_cache()
                        return profile
            except Exception:
                pass

            # 1. Tra cứu ip-api.com (Direct, 2.5s)
            try:
                url = f"http://ip-api.com/json/{clean_ip}?fields=status,country,countryCode,city,regionName,timezone,isp,org,query"
                resp = requests.get(url, timeout=min(timeout, 2.5))
                if resp.status_code == 200:
                    d = resp.json()
                    if d.get("status") == "success":
                        c_code = d.get("countryCode") or hint_c or "VN"
                        profile = cls.get_profile_for_country(
                            country_code=c_code,
                            ip=clean_ip,
                            city=d.get("city", ""),
                            timezone=d.get("timezone", ""),
                            isp_name=d.get("isp", "") or d.get("org", "")
                        )
                        with cls._LOCK:
                            cls._CACHE[clean_ip] = profile
                            cls._save_cache()
                        return profile
            except Exception:
                pass

            # 2. Tra cứu dự phòng ipwho.is (Direct, 2.0s)
            try:
                resp2 = requests.get(f"https://ipwho.is/{clean_ip}", timeout=2.0)
                if resp2.status_code == 200:
                    d2 = resp2.json()
                    if d2.get("success"):
                        c_code = d2.get("country_code") or hint_c or "VN"
                        tz_val = d2.get("timezone", {}).get("id", "") if isinstance(d2.get("timezone"), dict) else ""
                        isp_val = d2.get("connection", {}).get("isp", "") if isinstance(d2.get("connection"), dict) else ""
                        profile = cls.get_profile_for_country(
                            country_code=c_code,
                            ip=clean_ip,
                            city=d2.get("city", ""),
                            timezone=tz_val,
                            isp_name=isp_val
                        )
                        with cls._LOCK:
                            cls._CACHE[clean_ip] = profile
                            cls._save_cache()
                        return profile
            except Exception:
                pass

            # 3. Tra cứu dự phòng freeipapi.com (Direct, 2.0s)
            try:
                resp3 = requests.get(f"https://freeipapi.com/api/json/{clean_ip}", timeout=2.0)
                if resp3.status_code == 200:
                    d3 = resp3.json()
                    if d3.get("countryCode"):
                        c_code = d3.get("countryCode") or hint_c or "VN"
                        profile = cls.get_profile_for_country(
                            country_code=c_code,
                            ip=clean_ip,
                            city=d3.get("cityName", ""),
                            timezone=d3.get("timeZone", ""),
                        )
                        with cls._LOCK:
                            cls._CACHE[clean_ip] = profile
                            cls._save_cache()
                        return profile
            except Exception:
                pass

        if proxy:
            try:
                proxies_dict = {"http": proxy, "https": proxy} if proxy.startswith(("http://", "socks5://")) else {"http": f"http://{proxy}", "https": f"http://{proxy}"}
                url = f"http://ip-api.com/json/{clean_ip}?fields=status,country,countryCode,city,regionName,timezone,isp,org,query"
                resp = requests.get(url, proxies=proxies_dict, timeout=timeout)
                if resp.status_code == 200:
                    d = resp.json()
                    if d.get("status") == "success":
                        c_code = d.get("countryCode") or hint_c or "VN"
                        profile = cls.get_profile_for_country(
                            country_code=c_code,
                            ip=clean_ip,
                            city=d.get("city", ""),
                            timezone=d.get("timezone", ""),
                            isp_name=d.get("isp", "") or d.get("org", "")
                        )
                        with cls._LOCK:
                            cls._CACHE[clean_ip] = profile
                            cls._save_cache()
                        return profile
            except Exception as e:
                logger.debug(f"GeoIP proxy lookup failed for {clean_ip}: {e}")

        if hint_c:
            return cls.get_profile_for_country(hint_c, ip=clean_ip)

        fallback_profile = cls.get_profile_for_country("VN", ip=clean_ip)
        return fallback_profile


def generate_mno_carrier_phone(
    country_code: Any = "VN",
    carrier: Optional[str] = None,
    geo_profile: Optional[Any] = None,
    ip: Optional[str] = None,
    force_vn: bool = False,
    force_fresh: bool = False,
    e164: bool = False,
    **kwargs
) -> str:
    """
    Sinh số điện thoại di động mồi đa dạng nhà mạng và quốc gia,
    khớp hoàn toàn với mã vùng quốc tế và đầu số nhà mạng của IP Proxy.
    """
    if not isinstance(country_code, str):
        geo_profile = country_code
        country_code = getattr(geo_profile, "country_code", "VN") if geo_profile else "VN"

    c_code = normalize_country_code(country_code) or "VN"
    target_ip = ip
    if not target_ip and geo_profile:
        g_ip = getattr(geo_profile, "ip", None) or (geo_profile.get("ip") if isinstance(geo_profile, dict) else None)
        if g_ip and str(g_ip).lower() not in ("127.0.0.1", "0.0.0.0", "direct", "none", ""):
            target_ip = str(g_ip)

    if geo_profile and hasattr(geo_profile, "generate_phone"):
        return geo_profile.generate_phone(ip=target_ip, e164=e164)

    if c_code == "VN":
        carrier_choice = (carrier or "").lower().strip()
        if not carrier_choice or carrier_choice not in MNO_PREFIXES:
            carrier_choice = random.choices(
                ["viettel", "vinaphone", "mobifone", "vietnamobile", "gmobile", "wintel"],
                weights=[0.45, 0.25, 0.20, 0.05, 0.03, 0.02]
            )[0]
        prefix = random.choice(MNO_PREFIXES.get(carrier_choice, MNO_PREFIXES["viettel"]))
        if force_fresh or not target_ip:
            suffix = f"{random.randint(2, 9)}{''.join(str(random.randint(0, 9)) for _ in range(6))}"
        else:
            suffix = generate_phone_suffix_from_ip(target_ip, length=7)
            if len(suffix) != 7 or not suffix.isdigit():
                suffix = f"{random.randint(2, 9)}{''.join(str(random.randint(0, 9)) for _ in range(6))}"
        local_p = f"{prefix}{suffix}"
        if e164:
            return f"+84{local_p.lstrip('0')}"
        return local_p

    prof = GeoTelephonyResolver.get_profile_for_country(country_code=c_code, ip=target_ip or "127.0.0.1")
    return prof.generate_phone(ip=target_ip, e164=e164)
