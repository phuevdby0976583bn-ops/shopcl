from typing import Any
from datetime import datetime

from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, func, CheckConstraint, Enum, String
from sqlalchemy.orm import relationship

import config
from enums.bot_entity import BotEntity
from enums.buy_status import BuyStatus
from enums.language import Language
from models.base import Base
from utils.utils import get_text


class Buy(Base):
    __tablename__ = 'buys'

    id = Column(Integer, primary_key=True)
    buyer_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    buyer = relationship("User", back_populates="buys")
    total_price = Column(Float, nullable=False)
    buy_datetime = Column(DateTime(timezone=True), default=func.now())
    status = Column(Enum(BuyStatus), nullable=False)
    coupon_id = Column(Integer, ForeignKey('coupons.id'), nullable=True)
    coupon = relationship("Coupon", back_populates="buys")
    discount = Column(Float, nullable=False, default=0.0)
    shipping_address = Column(String, nullable=True)
    track_number = Column(String, nullable=True)
    shipping_option_id = Column(Integer, ForeignKey('shipping_options.id'), nullable=True)
    shipping_option = relationship("ShippingOption", back_populates="buys")
    buy_items = relationship(
        "BuyItem",
        back_populates="buy",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint('total_price > 0', name='check_total_price_positive'),
    )

    def __repr__(self):
        return get_text(Language.EN, BotEntity.USER, "purchase_history_item").format(
            buy_id=self.id,
            total_price=self.total_price,
            currency_sym=config.CURRENCY.get_localized_symbol()
        )


class BuyDTO(BaseModel):
    id: int | None = None
    buyer_id: int | None = None
    total_price: float | None = None
    buy_datetime: datetime | None = None
    status: BuyStatus = BuyStatus.PAID
    coupon_id: int | None = None
    discount: float = 0.0
    shipping_address: str | None = None
    track_number: str | None = None
    shipping_option_id: int | None

    @staticmethod
    def get_chart_text(language: Language) -> tuple[str, str]:
        return (get_text(language, BotEntity.ADMIN, "sales_ylabel")
                .format(currency_sym=config.CURRENCY.get_localized_symbol()),
                get_text(language, BotEntity.ADMIN, "sales_chart_title"))


class RefundDTO(BaseModel):
    telegram_username: str | None = None
    telegram_id: int | None = None
    subcategory_name: str | None = None
    total_price: float | None = None
    item_ids: list[int] | None = None
    buy_id: int | None = None
    language: Language


class BuyAdmin(ModelView, model=Buy):
    name = "Đơn mua"
    name_plural = "Đơn mua"
    icon = "fa-solid fa-cart-shopping"
    column_labels = {
        "id": "Mã đơn",
        "buyer": "Người mua",
        "total_price": "Tổng tiền ($)",
        "quantity": "Số lượng",
        "buy_datetime": "Ngày mua",
        "status": "Trạng thái",
        "discount": "Giảm giá ($)",
        "shipping_address": "Địa chỉ giao",
        "track_number": "Mã vận đơn"
    }
    column_exclude_list = [Buy.shipping_option_id,
                           Buy.coupon_id,
                           Buy.buyer_id]
    column_sortable_list = [Buy.id,
                            Buy.total_price,
                            Buy.buy_datetime,
                            Buy.status,
                            Buy.discount,
                            Buy.shipping_address,
                            Buy.track_number]
    can_create = False
    can_delete = True
    can_edit = False
    can_export = True

    async def delete_model(self, request, pk: Any) -> None:
        from models.buyItem import BuyItem
        from models.review import Review
        from sqlalchemy import delete, select
        async with self.session_maker() as session:
            bi_res = await session.execute(select(BuyItem.id).where(BuyItem.buy_id == int(pk)))
            bi_ids = bi_res.scalars().all()
            if bi_ids:
                await session.execute(delete(Review).where(Review.buyItem_id.in_(bi_ids)))
                await session.execute(delete(BuyItem).where(BuyItem.id.in_(bi_ids)))
            await session.execute(delete(Buy).where(Buy.id == int(pk)))
            await session.commit()
