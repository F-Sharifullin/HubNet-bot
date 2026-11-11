import os

from dotenv import load_dotenv

load_dotenv()

#Telegram
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = os.getenv("ADMIN_ID")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")

#PostgreSQL
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

#3x-ui
PANEL_TOKEN = os.getenv("PANEL_TOKEN")
PANEL_URL = os.getenv("PANEL_URL")
SUB_URL = os.getenv("SUB_URL")
SUB_PORT = int(os.getenv("SUB_PORT"))
SUB_PATH=os.getenv("SUB_PATH")
# Список ID инбаундов-локаций (через запятую в .env)
INBOUND_IDS = [
    int(x.strip()) for x in os.getenv("INBOUND_IDS", "").split(",") if x.strip()
]

#RollyPay
ROLLYPAY_BASE_URL = os.getenv("ROLLYPAY_BASE_URL", "https://rollypay.io")
ROLLYPAY_API_KEY = os.getenv("ROLLYPAY_API_KEY")
ROLLYPAY_SIGNING_SECRET = os.getenv("ROLLYPAY_SIGNING_SECRET")
ROLLYPAY_TERMINAL_ID = os.getenv("ROLLYPAY_TERMINAL_ID")
ROLLYPAY_WEBHOOK_PATH = os.getenv("ROLLYPAY_WEBHOOK_PATH", "/webhooks/rollypay")


#Tribute
TRIBUTE_API_KEY = os.getenv("TRIBUTE_API_KEY")
TRIBUTE_WEBHOOK_HOST = os.getenv("TRIBUTE_WEBHOOK_HOST", "0.0.0.0")
TRIBUTE_WEBHOOK_PORT = int(os.getenv("TRIBUTE_WEBHOOK_PORT", 8081))
TRIBUTE_WEBHOOK_PATH = os.getenv("TRIBUTE_WEBHOOK_PATH", "/tribute-webhook")
#TRIBUTE_DONATE_LINK = os.getenv("TRIBUTE_DONATE_LINK")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
#Ссылки на оплату
TRIBUTE_AMOUNTS_RUB = (150, 300, 450, 250, 500, 750, 350, 700, 1050)

TRIBUTE_LINKS = {
    amount: link
    for amount in TRIBUTE_AMOUNTS_RUB
    if (link := os.getenv(f"TRIBUTE_LINK_{amount}", "").strip())
}

#Redis
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

#Документы
PRIVACY_POLICY_URL = os.getenv("PRIVACY_POLICY_URL")
USER_AGREEMENT_URL = os.getenv("USER_AGREEMENT_URL")