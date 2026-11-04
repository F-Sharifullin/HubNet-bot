import pytz

# Республика Башкортостан живёт по времени Екатеринбурга (UTC+5)
LOCAL_TZ = pytz.timezone("Asia/Yekaterinburg")


def to_local(dt) -> str:
    """Конвертирует TIMESTAMPTZ (хранится в UTC) в местное время Сибая."""
    if dt is None:
        return "—"
    return dt.astimezone(LOCAL_TZ).strftime("%d.%m.%Y %H:%M")