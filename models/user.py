from typing import Any
from datetime import datetime
from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, DateTime, String, Boolean, Float, func, CheckConstraint, Enum, ForeignKey, BigInteger
from sqlalchemy.orm import relationship

from enums.bot_entity import BotEntity
from enums.language import Language
from models.base import Base
from utils.utils import get_text


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_username = Column(String, unique=True, index=True)
    telegram_id = Column(BigInteger, nullable=False, unique=True, index=True)
    top_up_amount = Column(Float, default=0.0)
    consume_records = Column(Float, default=0.0)
    registered_at = Column(DateTime(timezone=True), default=func.now())
    can_receive_messages = Column(Boolean, default=True)
    language = Column(Enum(Language), default=Language.VI, nullable=False)
    is_banned = Column(Boolean, default=False)
    referral_code = Column(String(8), nullable=True, unique=True, index=True)
    referred_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    referred_at = Column(DateTime(timezone=True), nullable=True)
    received_referral_bonuses = relationship(
        "ReferralBonus",
        foreign_keys="ReferralBonus.referral_user_id",
        back_populates="referral_user_dto",
        cascade="all, delete-orphan"
    )
    earned_referral_bonuses = relationship(
        "ReferralBonus",
        foreign_keys="ReferralBonus.referrer_user_id",
        back_populates="referrer_user_dto",
        cascade="all, delete-orphan"
    )
    buys = relationship(
        "Buy",
        back_populates="buyer",
        cascade="all, delete-orphan"
    )
    deposits = relationship(
        "Deposit",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    payments = relationship(
        "Payment",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    cart = relationship(
        "Cart",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint('top_up_amount >= 0', name='check_top_up_amount_positive'),
        CheckConstraint('consume_records >= 0', name='check_consume_records_positive'),
        CheckConstraint('referred_by_user_id != id', name='check_no_self_referral'),
    )

    def __repr__(self):
        return f"@{self.telegram_username}" if self.telegram_username else f"{self.telegram_id}"


class UserDTO(BaseModel):
    id: int | None = None
    telegram_username: str | None = None
    telegram_id: int | None = None
    top_up_amount: float | None = None
    consume_records: float | None = None
    registered_at: datetime | None = None
    can_receive_messages: bool | None = None
    language: Language = Language.VI
    is_banned: bool = False
    referral_code: str | None = None
    referred_by_user_id: int | None = None
    referred_at: datetime | None = None

    @staticmethod
    def get_chart_text(language: Language) -> tuple[str, str]:
        return (get_text(language, BotEntity.ADMIN, "users_ylabel"),
                get_text(language, BotEntity.ADMIN, "users_chart_title"))


class UserAdmin(ModelView, model=User):
    name = "Khách hàng"
    name_plural = "Khách hàng"
    icon = "fa-solid fa-users"
    column_labels = {
        "id": "ID",
        "telegram_username": "Username Telegram",
        "telegram_id": "Telegram ID",
        "top_up_amount": "Tổng nạp ($)",
        "consume_records": "Đã tiêu ($)",
        "registered_at": "Ngày đăng ký",
        "can_receive_messages": "Nhận tin",
        "language": "Ngôn ngữ",
        "is_banned": "Bị khóa",
        "referral_code": "Mã GT",
        "referred_at": "Ngày được mời"
    }
    column_exclude_list = [User.buys,
                           User.deposits,
                           User.earned_referral_bonuses,
                           User.received_referral_bonuses,
                           User.referred_by_user_id,
                           User.payments,
                           User.cart]
    can_delete = True
    can_edit = True
    can_create = False
    can_export = True

    async def delete_model(self, request, pk: Any) -> None:
        from models.cart import Cart
        from models.cartItem import CartItem
        from models.deposit import Deposit
        from models.binance_pay import BinancePayOrder
        from models.buy import Buy
        from models.buyItem import BuyItem
        from models.review import Review
        from models.payment import Payment
        from models.referral import ReferralBonus
        from sqlalchemy import delete, update, select
        u_id = int(pk)
        async with self.session_maker() as session:
            await session.execute(update(User).where(User.referred_by_user_id == u_id).values(referred_by_user_id=None))
            await session.execute(delete(BinancePayOrder).where(BinancePayOrder.user_id == u_id))
            await session.execute(delete(Deposit).where(Deposit.user_id == u_id))
            await session.execute(delete(Payment).where(Payment.user_id == u_id))
            await session.execute(delete(ReferralBonus).where((ReferralBonus.referral_user_id == u_id) | (ReferralBonus.referrer_user_id == u_id)))
            c_res = await session.execute(select(Cart.id).where(Cart.user_id == u_id))
            c_ids = c_res.scalars().all()
            if c_ids:
                await session.execute(delete(CartItem).where(CartItem.cart_id.in_(c_ids)))
                await session.execute(delete(Cart).where(Cart.id.in_(c_ids)))
            b_res = await session.execute(select(Buy.id).where(Buy.buyer_id == u_id))
            b_ids = b_res.scalars().all()
            if b_ids:
                bi_res = await session.execute(select(BuyItem.id).where(BuyItem.buy_id.in_(b_ids)))
                bi_ids = bi_res.scalars().all()
                if bi_ids:
                    await session.execute(delete(Review).where(Review.buyItem_id.in_(bi_ids)))
                    await session.execute(delete(BuyItem).where(BuyItem.id.in_(bi_ids)))
                await session.execute(delete(Buy).where(Buy.id.in_(b_ids)))
            await session.execute(delete(User).where(User.id == u_id))
            await session.commit()
    column_searchable_list = [User.telegram_username]
    column_sortable_list = [User.id,
                            User.telegram_username,
                            User.telegram_id,
                            User.top_up_amount,
                            User.consume_records,
                            User.registered_at,
                            User.can_receive_messages,
                            User.language,
                            User.is_banned,
                            User.registered_at,
                            User.referred_at]
