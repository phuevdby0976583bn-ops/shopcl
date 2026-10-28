import random

# Android 4-6 (Old Devices)
ANDROID_4_6_VERSIONS = ['4.1.2', '4.2.2', '4.3', '4.4', '4.4.2', '4.4.4', '5.0', '5.0.1', '5.0.2', '5.1', '5.1.1', '6.0', '6.0.1']
ANDROID_4_6_DEVICES = [
    ('Nexus 4', 'KOT49H'), ('Nexus 5', 'LMY48B'), ('Nexus 6', 'LRX22G'),
    ('SM-G900F', 'KTU84P'), ('SM-G920F', 'LRX21T'), ('SM-G930F', 'MMB29K'),
    ('SM-G925F', 'NRD90M'), ('SM-N900', 'JSS15J'), ('SM-N910F', 'KTU84P'),
    ('GT-I9300', 'JSS15J'), ('GT-I9500', 'JDQ39'), ('GT-I9505', 'JDQ39E'),
    ('HTC One M8', 'KOT49H'), ('HTC One M9', 'LMY47O'),
    ('LG-D855', 'KTU84P'), ('LG-H815', 'LMY47D'),
    ('Sony D6603', 'KTU84P'), ('Sony E6653', 'LMY47D'),
    ('Moto G', 'KXB21.14-L1.40'), ('Moto X', 'KXA21.12-L1.26'),
    ('HUAWEI P8', 'GRA-L09'), ('HUAWEI P9', 'EVA-L09'),
    ('ONE A2001', 'LMY47V'), ('ONE A2003', 'LMY47V'), ('ONE A2005', 'LMY47V'),
    ('SM-A300F', 'KTU84P'), ('SM-A500F', 'KTU84P'), ('SM-A700F', 'KTU84P'),
    ('SM-J100H', 'KTU84P'), ('SM-J500F', 'LMY48B'), ('SM-J700F', 'LMY48B'),
    ('LG-H440n', 'LRX21Y'), ('LG-H340n', 'LRX21Y'), ('LG-D722', 'KOT49I'),
    ('HTC Desire 816', 'KOT49H'), ('HTC Desire 820', 'KTU84P'),
    ('Sony D5803', 'KTU84P'), ('Sony D6503', 'KOT49H'), ('Sony E2303', 'LRX22G'),
    ('HUAWEI G7-L01', 'KTU84P'), ('HUAWEI MT7-L09', 'KOT49H'),
    ('ASUS_Z00AD', 'LRX21V'), ('ASUS_Z008D', 'LRX21V'), ('ASUS_T00F', 'KVT49L'),
    ('Lenovo K50-t5', 'LRX21M'), ('Lenovo A6000', 'KTU84P'), ('Lenovo P70-A', 'KOT49H'),
    ('ZTE Blade L3', 'LRX21M'), ('ZTE Blade S6', 'LRX21M'),
    ('vivo Y21', 'KOT49H'), ('vivo Y31', 'LMY47V'), ('vivo V1', 'LMY47V'),
    ('OPPO R7', 'KTU84P'), ('OPPO F1', 'LMY47V'), ('OPPO A33', 'LMY47V'),
]

def get_android_4_6():
    chrome_major = random.randint(30, 55)
    chrome_version = f"{chrome_major}.0.{random.randint(1500, 2900)}.{random.randint(50, 200)}"
    android_ver = random.choice(ANDROID_4_6_VERSIONS)
    device, build = random.choice(ANDROID_4_6_DEVICES)
    return f'Mozilla/5.0 (Linux; Android {android_ver}; {device} Build/{build}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Mobile Safari/537.36'


# Android 7-11 (Mid Devices)
ANDROID_7_11_VERSIONS = ['7.0', '7.1', '7.1.1', '7.1.2', '8.0.0', '8.1.0', '9', '10', '11']
ANDROID_7_11_DEVICES = [
    ('SM-G935F', 'NRD90M'), ('SM-G950F', 'R16NW'), ('SM-G960F', 'PPR1.180610.011'),
    ('SM-G970F', 'PPR1.180610.011'), ('SM-G973F', 'PPR1.180610.011'),
    ('SM-G991B', 'RP1A.200720.012'), ('SM-A505F', 'QP1A.190711.020'),
    ('SM-A515F', 'QP1A.190711.020'), ('SM-A715F', 'QP1A.190711.020'),
    ('SM-N950F', 'NMF26X'), ('SM-N960F', 'PPR1.180610.011'),
    ('Pixel 2', 'OPD3.170816.012'), ('Pixel 3', 'QQ3A.200805.001'),
    ('Pixel 4', 'RQ3A.210905.001'), ('Pixel 4a', 'RQ3A.211001.001'),
    ('Redmi Note 7', 'PKQ1.181203.001'), ('Redmi Note 8 Pro', 'PPR1.180610.011'),
    ('Redmi Note 9', 'QP1A.190711.020'), ('Redmi Note 10 Pro', 'RKQ1.200826.002'),
    ('Mi 9', 'PKQ1.181121.001'), ('Mi 10', 'QKQ1.191222.002'),
    ('POCO F1', 'PKQ1.180729.001'), ('POCO X3', 'QQ3A.200805.001'),
    ('HUAWEI P20', 'HUAWEIEML-L29'), ('HUAWEI P30', 'HUAWEIELE-L29'),
    ('OnePlus 6', 'ONEPLUS A6003'), ('OnePlus 7 Pro', 'ONEPLUS A7010'),
    ('RMX1911', 'QKQ1.200209.002'), ('CPH1909', 'QP1A.190711.020'),
    ('SM-G981B', 'QP1A.190711.020'), ('SM-G986B', 'QP1A.190711.020'), ('SM-G988B', 'QP1A.190711.020'),
    ('SM-N970F', 'QP1A.190711.020'), ('SM-N975F', 'QP1A.190711.020'), ('SM-N986B', 'QP1A.190711.020'),
    ('SM-A105F', 'PPR1.180610.011'), ('SM-A205F', 'PPR1.180610.011'), ('SM-A305F', 'PPR1.180610.011'),
    ('SM-M315F', 'QP1A.190711.020'), ('SM-M515F', 'QP1A.190711.020'),
    ('Pixel 3a', 'QQ3A.200805.001'), ('Pixel 5', 'RQ3A.210905.001'),
    ('Redmi Note 8', 'PKQ1.190616.001'), ('Redmi 9', 'QP1A.190711.020'), ('Redmi 9T', 'QKQ1.200830.002'),
    ('Mi 9T Pro', 'QKQ1.190825.002'), ('Mi 10T Pro', 'RKQ1.200826.002'), ('POCO M3', 'QKQ1.200830.002'),
    ('HUAWEI Mate 20 Pro', 'HUAWEILYA-L29'), ('HUAWEI Mate 30 Pro', 'HUAWEILIO-L29'),
    ('VOG-L29', 'HUAWEIVOG-L29'), ('MAR-LX1A', 'HUAWEIMAR-LX1A'),
    ('OnePlus 8 Pro', 'IN2023'), ('OnePlus 8T', 'KB2003'), ('OnePlus 9 Pro', 'LE2123'),
    ('RMX2001', 'QP1A.190711.020'), ('RMX2061', 'QP1A.190711.020'), ('RMX2151', 'QP1A.190711.020'),
    ('CPH2083', 'QP1A.190711.020'), ('CPH2127', 'RKQ1.200903.002'), ('CPH2205', 'RKQ1.200903.002'),
    ('vivo 1904', 'PPR1.180610.011'), ('vivo 1920', 'QP1A.190711.020'), ('vivo 2018', 'RKQ1.200819.002'),
    ('motorola one vision', 'QSAS30.62-24-3'), ('moto g(8) plus', 'QPI30.28-Q3-28'), ('moto g(9) play', 'QPZ30.30-Q3-38'),
    ('Nokia 7.2', 'QKQ1.191014.001'), ('Nokia 8.1', 'QKQ1.190828.002'), ('Nokia 5.3', 'QKQ1.191014.001'),
    ('LM-G710', 'PKQ1.181105.001'), ('LM-G810', 'PKQ1.190416.001'), ('LM-V600', 'QKQ1.191222.002'),
    ('Sony G8142', 'PKQ1.190118.001'), ('Sony H8216', 'PKQ1.190118.001'), ('Sony J9110', 'QKQ1.190918.001'),
]

def get_android_7_11():
    chrome_major = random.randint(56, 95)
    chrome_version = f"{chrome_major}.0.{random.randint(2900, 4700)}.{random.randint(50, 200)}"
    android_ver = random.choice(ANDROID_7_11_VERSIONS)
    device, build = random.choice(ANDROID_7_11_DEVICES)
    return f'Mozilla/5.0 (Linux; Android {android_ver}; {device} Build/{build}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Mobile Safari/537.36'


# Android 12-15 (New Devices)
ANDROID_12_15_VERSIONS = ['12', '12L', '13', '14', '15']
ANDROID_12_15_DEVICES = [
    ('Pixel 6', 'SD1A.210817.036'), ('Pixel 6 Pro', 'SD1A.210817.036'),
    ('Pixel 7', 'TQ3A.230901.001'), ('Pixel 7 Pro', 'TQ3A.230901.001'),
    ('Pixel 8', 'UD1A.230803.041'), ('Pixel 8 Pro', 'UD1A.230803.041'),
    ('Pixel 9', 'AP3A.241005.015'), ('Pixel 9 Pro', 'AP3A.241005.015'),
    ('SM-S908B', 'SP1A.210812.016'), ('SM-S911B', 'TP1A.220624.014'),
    ('SM-S918B', 'TP1A.220624.014'), ('SM-S928B', 'UP1A.231005.007'),
    ('SM-S938B', 'AP3A.241105.008'), ('SM-A546B', 'TP1A.220624.014'),
    ('SM-A556B', 'UP1A.231005.007'), ('SM-A736B', 'SP1A.210812.016'),
    ('SM-S901B', 'SP1A.210812.016'), ('SM-S906B', 'SP1A.210812.016'),
    ('Redmi Note 11', 'SKQ1.211006.001'), ('Redmi Note 12 Pro', 'TP1A.220624.014'),
    ('Redmi Note 13 Pro', 'UP1A.231005.007'), ('POCO F5', 'TKQ1.221114.001'),
    ('OnePlus 10 Pro', 'SKQ1.211006.001'), ('OnePlus 11', 'TP1A.220624.014'),
    ('OnePlus 12', 'UP1A.231005.007'), ('CPH2491', 'TP1A.220624.014'),
    ('V2227A', 'SP1A.210812.016'), ('M2101K6G', 'SKQ1.210908.001'),
    ('Nothing Phone (2)', 'TQ3A.230901.001'), ('ASUS_AI2302', 'TP1A.220624.014'),
    ('SM-F711B', 'SP1A.210812.016'), ('SM-F926B', 'SP1A.210812.016'), ('SM-F721B', 'TP1A.220624.014'),
    ('SM-F936B', 'TP1A.220624.014'), ('SM-F731B', 'UP1A.231005.007'), ('SM-F946B', 'UP1A.231005.007'),
    ('SM-F741B', 'UP1A.231005.007'), ('SM-F956B', 'UP1A.231005.007'),
    ('SM-A146B', 'TP1A.220624.014'), ('SM-A346B', 'TP1A.220624.014'),
    ('SM-A156B', 'UP1A.231005.007'), ('SM-A256B', 'UP1A.231005.007'), ('SM-A356B', 'UP1A.231005.007'),
    ('Pixel 6a', 'SD2A.220601.003'), ('Pixel 7a', 'TQ3A.230901.001'), ('Pixel 8a', 'UD1A.230803.041'),
    ('Pixel Fold', 'TQ3A.230901.001'), ('Pixel 9 Pro Fold', 'AP3A.241005.015'),
    ('2201116SG', 'SKQ1.211006.001'), ('22101320G', 'TP1A.220624.014'), ('23049PCD8G', 'TP1A.220624.014'),
    ('23122PCD1G', 'UP1A.231005.007'), ('POCO X4 Pro 5G', 'SKQ1.211103.001'), ('POCO X5 Pro 5G', 'TP1A.220624.014'),
    ('POCO F4', 'SKQ1.211006.001'), ('POCO X6 Pro', 'UP1A.231005.007'),
    ('Xiaomi 12', 'SKQ1.211006.001'), ('Xiaomi 13', 'TP1A.220624.014'), ('Xiaomi 14', 'UP1A.231005.007'),
    ('OnePlus Nord 2T', 'SP1A.210812.016'), ('OnePlus Nord 3', 'TP1A.220624.014'), ('OnePlus Open', 'UP1A.231005.007'),
    ('RMX3363', 'SP1A.210812.016'), ('RMX3561', 'SP1A.210812.016'), ('RMX3771', 'TP1A.220624.014'), ('RMX3840', 'UP1A.231005.007'),
    ('CPH2359', 'SP1A.210812.016'), ('CPH2437', 'TP1A.220624.014'), ('CPH2525', 'UP1A.231005.007'),
    ('V2109', 'SP1A.210812.016'), ('V2207', 'TP1A.220624.014'), ('V2303', 'UP1A.231005.007'), ('V2338', 'UP1A.231005.007'),
    ('motorola edge 30', 'S1RDS32.55-73-2'), ('motorola edge 40', 'T1TL33.72-22-2'), ('motorola razr 40 ultra', 'T1TZ33.3-62-2'),
    ('Nothing Phone (1)', 'SKQ1.211230.001'), ('Nothing Phone (2a)', 'UP1A.231005.007'),
    ('Sony XQ-CT54', 'TP1A.220624.014'), ('Sony XQ-DQ54', 'TP1A.220624.014'),
]

def get_android_12_15():
    chrome_major = random.randint(96, 133)
    chrome_version = f"{chrome_major}.0.{random.randint(4664, 6917)}.{random.randint(30, 150)}"
    android_ver = random.choice(ANDROID_12_15_VERSIONS)
    device, build = random.choice(ANDROID_12_15_DEVICES)
    return f'Mozilla/5.0 (Linux; Android {android_ver}; {device} Build/{build}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Mobile Safari/537.36'


# iOS Old (iPhone, iOS 10-12)
IOS_OLD_VERSIONS = [
    ('10_0', '602.1', '10.0', '14A403'),
    ('10_2', '602.4.6', '10.0', '14C92'),
    ('10_2_1', '602.4.6', '10.0', '14D27'),
    ('10_3', '603.1.30', '10.0', '14E277'),
    ('10_3_3', '603.3.8', '10.0', '14G60'),
    ('11_0', '604.1.38', '11.0', '15A372'),
    ('11_2', '604.4.7', '11.0', '15C114'),
    ('11_2_6', '604.5.6', '11.0', '15D100'),
    ('11_3', '605.1.15', '11.0', '15E216'),
    ('11_4', '605.1.15', '11.0', '15F79'),
    ('11_4_1', '605.1.15', '11.0', '15G77'),
    ('12_0', '605.1.15', '12.0', '16A366'),
    ('12_1', '605.1.15', '12.1', '16B92'),
    ('12_2', '605.1.15', '12.1', '16E227'),
    ('12_3', '605.1.15', '12.1.1', '16F203'),
    ('12_4', '605.1.15', '12.1.2', '16G77'),
    ('12_4_1', '605.1.15', '12.1.2', '16G102'),
]

def get_ios_old():
    ios_ver, webkit, safari_ver, build = random.choice(IOS_OLD_VERSIONS)
    return f'Mozilla/5.0 (iPhone; CPU iPhone OS {ios_ver} like Mac OS X) AppleWebKit/{webkit} (KHTML, like Gecko) Version/{safari_ver} Mobile/{build} Safari/{webkit.split(".")[0]}.1'


# iOS Medium (iPhone, iOS 13-15)
IOS_MEDIUM_VERSIONS = [
    ('13_0', '605.1.15', '13.0', '17A577'),
    ('13_1', '605.1.15', '13.0.1', '17A844'),
    ('13_3', '605.1.15', '13.0.4', '17C54'),
    ('13_4', '605.1.15', '13.1', '17E255'),
    ('13_5', '605.1.15', '13.1.1', '17F75'),
    ('13_5_1', '605.1.15', '13.1.1', '17F80'),
    ('13_6', '605.1.15', '13.1.2', '17G68'),
    ('13_7', '605.1.15', '13.1.2', '17H35'),
    ('14_0', '605.1.15', '14.0', '18A373'),
    ('14_2', '605.1.15', '14.0.1', '18B92'),
    ('14_4', '605.1.15', '14.0.3', '18D52'),
    ('14_6', '605.1.15', '14.1.1', '18F72'),
    ('14_7_1', '605.1.15', '14.1.2', '18G82'),
    ('14_8', '605.1.15', '14.1.2', '18H17'),
    ('15_0', '605.1.15', '15.0', '19A346'),
    ('15_1', '605.1.15', '15.1', '19B74'),
    ('15_4', '605.1.15', '15.4', '19E241'),
    ('15_5', '605.1.15', '15.5', '19F77'),
    ('15_6', '605.1.15', '15.6', '19G71'),
    ('15_6_1', '605.1.15', '15.6.1', '19G82'),
]

def get_ios_medium():
    ios_ver, webkit, safari_ver, build = random.choice(IOS_MEDIUM_VERSIONS)
    return f'Mozilla/5.0 (iPhone; CPU iPhone OS {ios_ver} like Mac OS X) AppleWebKit/{webkit} (KHTML, like Gecko) Version/{safari_ver} Mobile/{build} Safari/{webkit.split(".")[0]}.1'


# iOS New (iPhone, iOS 16-18)
IOS_NEW_VERSIONS = [
    ('16_0', '605.1.15', '16.0', '20A362'),
    ('16_1', '605.1.15', '16.1', '20B82'),
    ('16_3', '605.1.15', '16.3', '20D47'),
    ('16_4', '605.1.15', '16.4', '20E247'),
    ('16_5', '605.1.15', '16.5', '20F66'),
    ('16_6', '605.1.15', '16.6', '20G75'),
    ('17_0', '605.1.15', '17.0', '21A329'),
    ('17_1', '605.1.15', '17.1', '21B74'),
    ('17_2', '605.1.15', '17.2', '21C62'),
    ('17_3', '605.1.15', '17.3', '21D50'),
    ('17_4', '605.1.15', '17.4', '21E219'),
    ('17_4_1', '605.1.15', '17.4.1', '21E236'),
    ('17_5', '605.1.15', '17.5', '21F79'),
    ('17_6', '605.1.15', '17.6', '21G80'),
    ('18_0', '605.1.15', '18.0', '22A3354'),
    ('18_1', '605.1.15', '18.1', '22B83'),
    ('18_2', '605.1.15', '18.2', '22C152'),
]

def get_ios_new():
    ios_ver, webkit, safari_ver, build = random.choice(IOS_NEW_VERSIONS)
    return f'Mozilla/5.0 (iPhone; CPU iPhone OS {ios_ver} like Mac OS X) AppleWebKit/{webkit} (KHTML, like Gecko) Version/{safari_ver} Mobile/{build} Safari/{webkit.split(".")[0]}.1'


# iPad Old (iPadOS 10-13)
IPAD_OLD_VERSIONS = [
    ('10_3_3', '603.3.8', '10.0', '14G60'),
    ('11_0', '604.1.34', '11.0', '15A5341f'),
    ('11_2', '604.4.7', '11.0', '15C114'),
    ('11_4', '605.1.15', '11.0', '15F79'),
    ('11_4_1', '605.1.15', '11.0', '15G77'),
    ('12_0', '605.1.15', '12.0', '16A366'),
    ('12_1', '605.1.15', '12.1', '16B92'),
    ('12_4', '605.1.15', '12.1.2', '16G77'),
    ('12_4_1', '605.1.15', '12.1.2', '16G102'),
    ('13_0', '605.1.15', '13.0', '17A577'),
    ('13_1', '605.1.15', '13.0.1', '17A844'),
    ('13_3', '605.1.15', '13.0.4', '17C54'),
    ('13_5', '605.1.15', '13.1.1', '17F75'),
    ('13_6', '605.1.15', '13.1.2', '17G68'),
    ('13_7', '605.1.15', '13.1.2', '17H35'),
]

def get_ipad_old():
    ios_ver, webkit, safari_ver, build = random.choice(IPAD_OLD_VERSIONS)
    return f'Mozilla/5.0 (iPad; CPU OS {ios_ver} like Mac OS X) AppleWebKit/{webkit} (KHTML, like Gecko) Version/{safari_ver} Mobile/{build} Safari/{webkit.split(".")[0]}.1'


# iPad New (iPadOS 15-18)
IPAD_NEW_VERSIONS = [
    ('15_0', '605.1.15', '15.0', '19A346'),
    ('15_4', '605.1.15', '15.4', '19E241'),
    ('15_5', '605.1.15', '15.5', '19F77'),
    ('15_6', '605.1.15', '15.6', '19G71'),
    ('16_0', '605.1.15', '16.0', '20A362'),
    ('16_3', '605.1.15', '16.3', '20D47'),
    ('16_5', '605.1.15', '16.5', '20F66'),
    ('16_6', '605.1.15', '16.6', '20G75'),
    ('17_0', '605.1.15', '17.0', '21A329'),
    ('17_2', '605.1.15', '17.2', '21C62'),
    ('17_4', '605.1.15', '17.4', '21E219'),
    ('17_5', '605.1.15', '17.5', '21F79'),
    ('18_0', '605.1.15', '18.0', '22A3354'),
    ('18_1', '605.1.15', '18.1', '22B83'),
]

def get_ipad_new():
    ios_ver, webkit, safari_ver, build = random.choice(IPAD_NEW_VERSIONS)
    return f'Mozilla/5.0 (iPad; CPU OS {ios_ver} like Mac OS X) AppleWebKit/{webkit} (KHTML, like Gecko) Version/{safari_ver} Mobile/{build} Safari/{webkit.split(".")[0]}.1'


# KaiOS (Feature Phones)
KAIOS_VERSIONS = ['2.5', '2.5.1', '2.5.2', '2.5.3', '2.5.4', '3.0', '3.1']
KAIOS_DEVICES = [
    'Nokia 8110 4G', 'Nokia 2720 Flip', 'Nokia 6300 4G',
    'Nokia 800 Tough', 'Nokia 2780 Flip',
    'Alcatel ONETOUCH 4044O', 'Alcatel 3078',
    'LG-M150', 'JioPhone', 'JioPhone 2',
    'CAT B35', 'Doro 7010', 'Energizer E241S',
]
KAIOS_GECKO_VERSIONS = ['48.0', '84.0']

def get_kaios():
    kaios_ver = random.choice(KAIOS_VERSIONS)
    device = random.choice(KAIOS_DEVICES)
    gecko = random.choice(KAIOS_GECKO_VERSIONS)
    return f'Mozilla/5.0 (Mobile; {device}; rv:{gecko}) Gecko/{gecko} Firefox/{gecko} KAIOS/{kaios_ver}'


# Windows Phone
WP_CONFIGS = [
    ('10.0', '6.0.1', '15.15254'),
    ('10.0', '6.0.1', '15.15063'),
    ('10.0', '6.0.1', '14.14393'),
    ('10.0', '4.2.1', '14.14393'),
    ('10.0', '4.2.1', '13.10586'),
    ('8.1', None, None),
]
WP10_LUMIA_MODELS = [
    'Lumia 950 XL', 'Lumia 950', 'Lumia 650', 'Lumia 640 LTE',
    'Lumia 640 XL', 'Lumia 550', 'Lumia 535',
]
WP81_LUMIA_MODELS = [
    'Lumia 930', 'Lumia 830', 'Lumia 730', 'Lumia 635',
    'Lumia 630', 'Lumia 530', 'Lumia 1520', 'Lumia 1020',
]

def get_windows_phone():
    wp_ver, android_compat, edge_ver = random.choice(WP_CONFIGS)
    if wp_ver == '8.1':
        device = random.choice(WP81_LUMIA_MODELS)
        return f'Mozilla/5.0 (Windows Phone {wp_ver}; ARM; Trident/7.0; Touch; rv:11.0; IEMobile/11.0; NOKIA; {device}) like Gecko'
    else:
        device = random.choice(WP10_LUMIA_MODELS)
        chrome_build = random.randint(2700, 2900)
        chrome_patch = random.randint(100, 150)
        return f'Mozilla/5.0 (Windows Phone {wp_ver}; Android {android_compat}; Microsoft; {device}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.{chrome_build}.{chrome_patch} Mobile Safari/537.36 Edge/{edge_ver}'


# BlackBerry
BB10_TYPES = ['Touch', 'Keyboard']
BB10_VERSIONS = ['10.3.3.2205', '10.3.2.2836', '10.3.1.2726', '10.3.0.1418', '10.2.1.2141', '10.2.0.1803']
BBOS_MODELS = [
    ('9900', '7.1.0.346'), ('9930', '7.1.0.398'), ('9800', '6.0.0.448'),
    ('9780', '6.0.0.706'), ('9700', '6.0.0.546'), ('9360', '7.0.0.585'),
    ('9320', '7.1.0.714'), ('9790', '7.1.0.221'), ('9860', '7.0.0.261'),
]

def get_blackberry():
    use_bb10 = random.choice([True, False])
    if use_bb10:
        bb_type = random.choice(BB10_TYPES)
        bb_ver = random.choice(BB10_VERSIONS)
        webkit_minor = random.choice(['10+', '35+'])
        return f'Mozilla/5.0 (BB10; {bb_type}) AppleWebKit/537.{webkit_minor} (KHTML, like Gecko) Version/{bb_ver} Mobile Safari/537.{webkit_minor}'
    else:
        model, os_ver = random.choice(BBOS_MODELS)
        webkit = random.choice(['534.8+', '534.11+'])
        return f'Mozilla/5.0 (BlackBerry; U; BlackBerry {model}; en) AppleWebKit/{webkit} (KHTML, like Gecko) Version/{os_ver} Mobile Safari/{webkit}'


USER_AGENT_PROFILES = {
    'random': '🎲 Random Ngẫu Nhiên Tất Cả',
    'android_12_15': '📱 Android 12-15 (Hiện đại)',
    'android_7_11': '📱 Android 7-11 (Tầm trung)',
    'android_4_6': '📱 Android 4-6 (Cũ)',
    'ios_new': '🍎 iPhone iOS 16-18 (Mới)',
    'ios_medium': '🍎 iPhone iOS 13-15',
    'ios_old': '🍎 iPhone iOS 10-12 (Cũ)',
    'ipad_new': '📱 iPadOS 15-18 (Mới)',
    'ipad_old': '📱 iPad iOS 10-13 (Cũ)',
    'kaios': '📞 KaiOS (Nokia/Feature Phone)',
    'windows_phone': '🪟 Windows Phone / Lumia',
    'blackberry': '🍇 BlackBerry'
}

PROFILE_FUNCS = {
    'android_12_15': get_android_12_15,
    'android_7_11': get_android_7_11,
    'android_4_6': get_android_4_6,
    'ios_new': get_ios_new,
    'ios_medium': get_ios_medium,
    'ios_old': get_ios_old,
    'ipad_new': get_ipad_new,
    'ipad_old': get_ipad_old,
    'kaios': get_kaios,
    'windows_phone': get_windows_phone,
    'blackberry': get_blackberry,
}

def get_user_agent_by_profile(profile_name='random'):
    if not profile_name or profile_name == 'random' or profile_name not in PROFILE_FUNCS:
        fn = random.choice(list(PROFILE_FUNCS.values()))
        return fn()
    return PROFILE_FUNCS[profile_name]()

def get_random_user_agent():
    """Return a randomly chosen User-Agent string from all profiles."""
    return get_user_agent_by_profile('random')
