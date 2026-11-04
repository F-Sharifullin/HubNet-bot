import logging
import uuid
from typing import Optional

import aiohttp

from bot.config import ROLLYPAY_API_KEY, ROLLYPAY_BASE_URL, ROLLYPAY_TERMINAL_ID

logger = logging.getLogger(__name__)


# ---------- Хелперы для order_id / description ----------
def make_order_id(tg_id: int) -> str:
    """
    Формат: <tg_id>-<8 случайных символов>
    Пример: 123456789-a1b2c3d4
    Уникальный для каждого платежа, но Telegram ID виден сразу.
    """
    return f"{tg_id}-{uuid.uuid4().hex[:8]}"


def parse_tg_id(order_id: str) -> int:
    """Достаёт Telegram ID из order_id (для вебхука)."""
    return int(order_id.split("-", 1)[0])


def make_description(tg_id: int, username: Optional[str], plan: str = "VPN подписка") -> str:
    """Человекочитаемое описание: видно в кабинете RollyPay."""
    uname = f"@{username}" if username else "без username"
    # на случай лимита длины у шлюза — режем до 200 символов
    return f"{plan} | {uname} | ID {tg_id}"[:200]


# ---------- Клиент ----------

class RollyPay:
    """Клиент платёжного шлюза RollyPay (https://docs.rollypay.io/)."""

    def __init__(self):
        self.base_url = ROLLYPAY_BASE_URL.rstrip("/")
        self.api_key = ROLLYPAY_API_KEY
        self.terminal_id = ROLLYPAY_TERMINAL_ID
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    def _headers(self) -> dict:
        # X-Nonce обязателен в каждом запросе и должен быть уникальным
        return {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
            "X-Nonce": str(uuid.uuid4()),
        }

    async def create_payment(
        self,
        amount: str,
        order_id: str,
        description: str = "",
        payment_method: str | None = None,
        payment_currency: str = "RUB",
    ) -> Optional[dict]:
        """Создаёт платёж, возвращает ответ API (с pay_url) или None при ошибке."""
        payload = {
            "amount": amount,
            "payment_currency": payment_currency,
            "order_id": order_id,
        }
        if description:
            payload["description"] = description
        if payment_method:
            payload["payment_method"] = payment_method
        if self.terminal_id:
            payload["terminal_id"] = self.terminal_id

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/api/v1/payments",
                json=payload,
                headers=self._headers(),
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    logger.error("RollyPay create_payment error [%s]: %s", resp.status, data)
                    return None
                return data
        except aiohttp.ClientError as e:
            logger.error("RollyPay network error: %s", e)
            return None
        except Exception:
            logger.exception("RollyPay unexpected error while creating payment")
            return None

    async def create_user_payment(
        self,
        amount: str,
        tg_id: int,
        username: Optional[str] = None,
        plan: str = "VPN подписка",
        payment_method: str | None = None,
        payment_currency: str = "RUB",
    ) -> Optional[dict]:
        """
        Удобная обёртка: сама собирает order_id и description с ID/юзернеймом.
        Возвращает ответ API + добавляет ключ "order_id" для сохранения в БД.
        """
        order_id = make_order_id(tg_id)
        data = await self.create_payment(
            amount=amount,
            order_id=order_id,
            description=make_description(tg_id, username, plan),
            payment_method=payment_method,
            payment_currency=payment_currency,
        )
        if data is not None:
            data["order_id"] = order_id
        return data

    async def get_payment(self, payment_id: str) -> Optional[dict]:
        """Получить данные платежа — для доп. сверки статуса перед зачислением."""
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.base_url}/api/v1/payments/{payment_id}",
                headers=self._headers(),
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    logger.error("RollyPay get_payment error [%s]: %s", resp.status, data)
                    return None
                return data
        except aiohttp.ClientError as e:
            logger.error("RollyPay network error: %s", e)
            return None
        except Exception:
            logger.exception("RollyPay unexpected error while fetching payment")
            return None