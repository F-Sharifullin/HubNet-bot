import logging
import random
import uuid
from typing import Optional

import aiohttp

from bot.app.database.subscriptions import create_subscription
from bot.app.services.tariffs import calc_expiry_ms
from bot.config import INBOUND_IDS, PANEL_TOKEN, PANEL_URL, SUB_PATH, SUB_PORT, SUB_URL

logger = logging.getLogger(__name__)


class X3UI:
    def __init__(self):
        self.base_url = PANEL_URL.rstrip("/")
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if PANEL_TOKEN:
            self.headers["Authorization"] = f"Bearer {PANEL_TOKEN}"

        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=10),
            )
        return self.session

    async def close(self):
        """Закрыть сессию — вызывать при остановке бота"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _request(self, method: str, endpoint: str, json_data=None) -> dict:
        """Общий метод для всех запросов к панели"""
        url = f"{self.base_url}{endpoint}"

        try:
            session = await self._get_session()
            async with session.request(method, url, json=json_data) as resp:
                try:
                    return await resp.json()
                except Exception:
                    text = await resp.text()
                    logger.error(f"Non-JSON response [{endpoint}] status={resp.status}: {text[:500]}")
                    return {"success": False, "msg": text}

        except aiohttp.ClientError as e:
            logger.error(f"Network error [{endpoint}]: {e}")
            return {"success": False, "msg": "Connection error"}
        except Exception as e:
            logger.exception(f"Unexpected error [{endpoint}]")
            return {"success": False, "msg": str(e)}

    # ====================== Helpers ======================

    def _build_client(self, client_uuid: str, remark: str, sub_id: str,
                      enable: bool = True, expiry_ms: int = 0) -> dict:
        return {
            "id": client_uuid,
            "alterId": 0,
            "email": remark,
            "limitIp": 0,
            "limitHwid": 1,
            "totalGB": 0,
            "expiryTime": expiry_ms,
            "enable": enable,
            "tgId": 0,
            "subId": sub_id,
            "flow": "xtls-rprx-vision",
        }

    # ====================== API методы ======================

    async def add_client(self, user_id: int, device: str) -> Optional[str]:
        """Создаёт нового клиента в панели и сохраняет в БД.
        Возвращает ссылку на подписку или None при неудаче."""
        from bot.app.database.users import get_user
        user = await get_user(user_id)
        expiry_ms = (
            calc_expiry_ms(user["balance"], user["tariff"])
            if user and user["balance"] > 0 else 0
        )
        prefix_map = {
            "android": "AND",
            "ios": "IOS",
            "windows": "PC",
        }
        prefix = prefix_map.get(device.lower(), "DEV")

        client_uuid = str(uuid.uuid4())
        sub_id = str(uuid.uuid4())

        for attempt in range(10):
            suffix = random.randint(10000, 999999)
            remark = f"WH-{prefix}{suffix}"

            client = self._build_client(client_uuid, remark, sub_id, True, expiry_ms)
            data = {
                "client": client,
                "inboundIds": INBOUND_IDS,
            }

            result = await self._request(
                "POST",
                "/panel/api/clients/add",
                json_data=data,
            )

            if result.get("success"):
                await create_subscription(
                    telegram_id=user_id,
                    device=device,
                    remark=remark,
                    sub_id=sub_id,
                    uuid=client_uuid,
                )
                return f"{SUB_URL}:{SUB_PORT}{SUB_PATH}{sub_id}"

            logger.warning(
                f"add_client attempt {attempt + 1}/10 failed "
                f"[user={user_id}, remark={remark}]: {result.get('msg', '')}"
            )

        logger.error(f"add_client failed after 10 attempts [user={user_id}]")
        return None

    async def delete_client(self, client_uuid: str, remark: str) -> bool:
        """Удаляет клиента из панели по remark"""
        if not remark:
            logger.warning("delete_client called with empty remark")
            return False

        result = await self._request(
            "POST",
            f"/panel/api/clients/del/{remark}",
        )
        return result.get("success", False)

    async def set_client_enable(self, client_uuid: str, remark: str, sub_id: str,
                                enable: bool, expiry_ms: int = 0) -> bool:
        if not client_uuid:
            logger.warning("set_client_enable called with empty client_uuid")
            return False
        client = self._build_client(client_uuid, remark, sub_id, enable, expiry_ms)
        result = await self._request(
            "POST", f"/panel/api/clients/update/{remark}", json_data=client
        )
        return result.get("success", False)

    async def disable_client(self, client_uuid: str, remark: str, sub_id: str) -> bool:
        """Отключает клиента (ключ перестаёт работать)"""
        return await self.set_client_enable(client_uuid, remark, sub_id, False)

    async def enable_client(self, client_uuid: str, remark: str, sub_id: str) -> bool:
        """Включает клиента обратно"""
        return await self.set_client_enable(client_uuid, remark, sub_id, True)