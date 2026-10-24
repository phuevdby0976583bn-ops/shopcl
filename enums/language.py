from enum import Enum


class Language(str, Enum):
    VI = 'vi'
    EN = 'en'
    HI = 'hi'
    ZH = 'zh'
    FR = 'fr'
    DE = 'de'
    IT = 'it'
    ES = 'es'

    @staticmethod
    def from_locale(locale: str) -> 'Language':
        try:
            if not locale:
                return Language.VI
            prefix = locale.lower().split('-')[0].split('_')[0]
            if prefix in ('vi', 'vn'):
                return Language.VI
            if prefix in ('hi', 'zh', 'fr', 'de', 'it', 'es'):
                return Language(prefix)
            # Mặc định ưu tiên Tiếng Việt cho shop Clone Facebook
            return Language.VI
        except (ValueError, AttributeError):
            return Language.VI

    def get_country_code(self):
        match self:
            case Language.VI:
                return 'VN'
            case Language.EN:
                return 'US'
            case Language.HI:
                return 'IN'
            case Language.ZH:
                return 'CN'
            case Language.FR:
                return 'FR'
            case Language.DE:
                return 'DE'
            case Language.IT:
                return 'IT'
            case Language.ES:
                return 'ES'
            case _:
                return self.name

    def get_flag_emoji(self):
        match self:
            case Language.VI:
                return '\U0001f1fb\U0001f1f3'
            case Language.EN:
                return '\U0001f1ec\U0001f1e7'
            case Language.HI:
                return '\U0001f1ee\U0001f1f3'
            case Language.ZH:
                return '\U0001f1e8\U0001f1f3'
            case Language.FR:
                return '\U0001f1eb\U0001f1f7'
            case Language.DE:
                return '\U0001f1e9\U0001f1ea'
            case Language.IT:
                return '\U0001f1ee\U0001f1f9'
            case Language.ES:
                return '\U0001f1ea\U0001f1f8'
            case _:
                return '\U0001f310'

    def get_display_name(self):
        match self:
            case Language.VI:
                return 'Ti\u1ebfng Vi\u1ec7t'
            case Language.EN:
                return 'English'
            case Language.HI:
                return '\u0939\u093f\u0928\u094d\u0926\u0940'
            case Language.ZH:
                return '\u7b80\u4f53\u4e2d\u6587'
            case Language.FR:
                return 'Fran\u00e7ais'
            case Language.DE:
                return 'Deutsch'
            case Language.IT:
                return 'Italiano'
            case Language.ES:
                return 'Espa\u00f1ol'
            case _:
                return self.name
