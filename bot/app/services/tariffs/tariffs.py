from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from bot.app.database.tariffs import TARIFFS, Tariff

MSK = ZoneInfo("Europe/Moscow")

def cheaper_tariff_for(current: str, devices: int) -> Tariff | None:
    cur = TARIFFS[current]
    for t in sorted(TARIFFS.values(), key=lambda t: t.monthly_price):
        if t.monthly_price < cur.monthly_price and devices <= t.max_keys:
            return t
    return None


def calc_expiry_ms(balance, tariff_name: str) -> int:
    """Срок ключа в мс: сегодняшняя полночь МСК + (дни баланса + 1).
    После ежедневного списания значение не меняется, бот и приложение показывают одно число."""
    days = int(Decimal(str(balance)) // TARIFFS[tariff_name].daily_price)
    today_midnight = datetime.now(MSK).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((today_midnight + timedelta(days=days)).timestamp() * 1000)