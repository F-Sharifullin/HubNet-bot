from bot.app.keyboards.user.bonuses import bonus_menu, invite_user
from bot.app.keyboards.user.devices import (
    confirm_delete,
    device_button,
    devices_list,
    execute_replace,
    platform_choice,
    subscription_device,
)
from bot.app.keyboards.user.fortune import activate, claim, fortune_luck
from bot.app.keyboards.user.menu import balance_menu, home_button, main_menu
from bot.app.keyboards.user.payment import (
    documents_menu,
    pay_menu,
    rollypay_pay,
    topup_rollypay,
    tribute_pay,
    tribute_topup,
)
from bot.app.keyboards.user.promo import promo_cancel
from bot.app.keyboards.user.start import apps_keyboard, connect_vpn, start
from bot.app.keyboards.user.support import support_cancel
from bot.app.keyboards.user.tariffs import change_tariff, plan_tariffs, tariff_downgrade

__all__ = [
    "activate",
    "apps_keyboard",
    "balance_menu",
    "bonus_menu",
    "change_tariff",
    "claim",
    "confirm_delete",
    "connect_vpn",
    "device_button",
    "devices_list",
    "documents_menu",
    "execute_replace",
    "fortune_luck",
    "home_button",
    "invite_user",
    "main_menu",
    "pay_menu",
    "plan_tariffs",
    "platform_choice",
    "promo_cancel",
    "rollypay_pay",
    "start",
    "subscription_device",
    "support_cancel",
    "tariff_downgrade",
    "topup_rollypay",
    "tribute_pay",
    "tribute_topup",
]