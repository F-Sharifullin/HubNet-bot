import time

PROMO_MAX_FAILS = 5        # неверных попыток подряд
PROMO_BLOCK_TTL = 600      # секунд (10 минут)

# user_id -> (число неверных попыток, момент окончания окна по time.monotonic())
# Хранится в памяти процесса: при перезапуске бота счётчики обнуляются.
_promo_fails: dict[int, tuple[int, float]] = {}

def _get_count(user_id: int) -> int:
    """Текущее число неверных попыток (просроченные записи удаляются)."""
    item = _promo_fails.get(user_id)
    if item is None:
        return 0
    count, expires_at = item
    if expires_at <= time.monotonic():
        _promo_fails.pop(user_id, None)
        return 0
    return count

def _cleanup() -> None:
    """Чистит просроченные записи, чтобы словарь не рос бесконечно."""
    now = time.monotonic()
    for uid in [u for u, (_, exp) in _promo_fails.items() if exp <= now]:
        _promo_fails.pop(uid, None)

async def is_promo_blocked(user_id: int) -> bool:
    """True, если пользователь исчерпал попытки ввода промокода."""
    return _get_count(user_id) >= PROMO_MAX_FAILS

async def add_promo_fail(user_id: int) -> int:
    """Увеличивает счётчик неверных попыток, возвращает текущее значение."""
    if len(_promo_fails) > 10000:
        _cleanup()

    count = _get_count(user_id)
    if count == 0:
        # Первая ошибка — запускаем окно на 10 минут
        _promo_fails[user_id] = (1, time.monotonic() + PROMO_BLOCK_TTL)
        return 1

    _, expires_at = _promo_fails[user_id]
    _promo_fails[user_id] = (count + 1, expires_at)
    return count + 1

async def reset_promo_fails(user_id: int) -> None:
    """Сбрасывает счётчик (после успешной активации)."""
    _promo_fails.pop(user_id, None)