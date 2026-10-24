from enums.bot_entity import BotEntity
from enums.language import Language
from models.item import ItemDTO
from services.facebook import extract_uid
from utils.utils import get_text


class MessageService:
    @staticmethod
    def create_message_with_bought_items(items: list[ItemDTO], language: Language):
        message = "<b>"
        for count, item in enumerate(items, start=1):
            private_data = item.private_data
            uid = extract_uid(private_data)
            if uid:
                message += f"📦 Clone #{count} [UID: <code>{uid}</code> | LIVE ✅]\nĐịnh dạng: <code>{private_data}</code>\n\n"
            else:
                message += get_text(language, BotEntity.USER, "purchased_item").format(count=count,
                                                                                       private_data=private_data)
        message += "</b>\n"
        return message
