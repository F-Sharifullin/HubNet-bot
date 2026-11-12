from urllib.parse import quote

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.app.keyboards.user import invite_user

router = Router()

@router.callback_query(F.data == "referral")
async def tv_android(callback: CallbackQuery):
    await callback.answer("⚠️ Раздел в разработке", show_alert=True)

@router.callback_query(F.data == 'referral_disabled')
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
    text = (
        "<b>Реферальная программа</b>\n\n"
        "Приглашайте друзей и получайте 100₽ на баланс за каждого друга.\n\n"
        "<b>📊 Ваша статистика</b>\n"
        "├ Приглашено друзей: 12\n"
        "├ Пользуются: 8\n"
        "╰ Начислено бонусов: 1 200 ₽\n\n"
        "🔗 <b>Ваша ссылка:</b>\n"
        f"{referral_link}\n\n"
        '<blockquote>'
        "Когда ваш друг зайдет в наш бот по этой ссылке и создаст аккаунт, вы получите 100₽ на баланс!"
        '</blockquote>\n\n'     
    )

    await callback.message.answer(text, reply_markup=invite_user(share_url), parse_mode='HTML')