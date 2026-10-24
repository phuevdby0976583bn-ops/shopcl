from enum import Enum


class Language(str, Enum):
    VI = "vi"
    EN = "en"
    HI = "hi"
    ZH = "zh"
    FR = "fr"
    DE = "de"
    IT = "it"

    @staticmethod
    def from_locale(locale: str) -> 'Language':
        try:
            if not locale:
                return Language.EN
            prefix = locale.lower().split("-")[0].split("_")[0]
            return Language(prefix)
        except (ValueError, AttributeError):
            return Language.EN

    def get_country_code(self):
        match self:
            case Language.VI:
                return "VN"
            case Language.EN:
                return "US"
            case Language.HI:
                return "IN"
            case Language.ZH:
                return "CN"
            case _:
                return self.name

    def get_flag_emoji(self):
        match self:
            case Language.VI:
                return "🇻🇳"
            case Language.EN:
                return "🇬🇧"
            case Language.HI:
                return "🇮🇳"
            case Language.ZH:
                return "🇨🇳"
            case _:
                return "🌐"
