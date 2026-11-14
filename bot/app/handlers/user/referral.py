from urllib.parse import quote

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.app.database.users import get_referral_stats
from bot.app.keyboards.user import invite_user

router = Router()


@router.callback_query(F.data == 'referral')
async def referral(callback: CallbackQuery):
    await callback.answer()
    bot_info = await callback.bot.get_me()

    referral_link = (
        f"https://t.me/{bot_info.username}"
        f"?start={callback.from_user.id}"
    )

    share_text = (
        "Пользуюсь HubNet VPN — работает стабильно, подключение занимает пару минут.\n\n"
        "Присоединяйся к HubNet и пользуйся целый месяц бесплатно."
    )

    share_url = (
        "https://t.me/share/url"
        f"?url={quote(referral_link, safe='')}"
        f"&text={quote(share_text, safe='')}"
    )
    
# НУЖНЫ ПЕРЕМЕННЫЕ...
    stats = await get_referral_stats(callback.from_user.id)
    invited = stats["invited"]
    active = stats["active"]
    bonuses = f"{stats['bonuses']:,}".replace(",", " ") 
    text = (
        "<b>Реферальная программа</b>\n\n"
        "Приглашайте друзей и получайте 100₽ на баланс за каждого друга.\n\n"
        "<b>📊 Ваша статистика</b>\n"
        f"├ Приглашено друзей: {invited}\n"
        f"├ Пользуются: {active}\n"
        f"╰ Начислено бонусов: {bonuses} ₽\n\n"
        "🔗 <b>Ваша ссылка:</b>\n"
        f"{referral_link}\n\n"
        '<blockquote>'
        "Когда ваш друг зайдет в наш бот по этой ссылке и создаст аккаунт, вы получите 100₽ на баланс!"
        '</blockquote>\n\n'     
    )

    await callback.message.answer(text, reply_markup=invite_user(share_url), parse_mode='HTML')