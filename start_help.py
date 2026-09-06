#!/usr/bin/env python3
"""/start (with all deep-link routing), /help menu, group welcome
message, /referral, and the /pay premium page."""

import uuid
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.config import OWNER_ID, users, referrals_db, async_db
from bot.helpers import get_user
from bot.captcha import handle_captcha_verify

IMG_MAIN = "https://i.ibb.co/sJvdmLDR/x.jpg"
IMG_HELP = "https://i.ibb.co/HT6fHBP9/x.jpg"

WELCOME_STYLES = [
    "🤗 𝗪𝗲𝗹𝗰𝗼𝗺𝗲 {user} 🧸✨", "🤗 𝙒𝙚𝙡𝙘𝙤𝙢𝙚 {user} 🧸✨", "🤗 𝑾𝒆𝒍𝒄𝒐𝒎𝒆 {user} 🧸✨",
    "🤗 𝒲𝑒𝓁𝒸𝑜𝓂𝑒 {user} 🧸✨", "🤗 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 {user} 🧸✨", "🤗 𝘞𝘦𝘭𝘤𝘰𝘮𝘦 {user} 🧸✨",
    "🤗 𝚆𝚎𝚕𝚌𝚘𝚖𝚎 {user} 🧸✨", "🤗 𝕎𝕖𝕝𝕔𝕠𝕞𝕖 {user} 🧸✨", "🤗 𝓦𝓮𝓵𝓬𝓸𝓶𝓮 {user} 🧸✨"
]

HELP_TEXTS = {
    "help_manage": (
        "🛡️ <b>𝐆𝐫𝐨𝐮𝐩 𝐌𝐚𝐧𝐚𝐠𝐞𝐦𝐞𝐧𝐭</b>\n<i>ᴀᴅᴍɪɴ ᴛᴏᴏʟs ᴛᴏ ᴇɴғᴏʀᴄᴇ ᴛʜᴇ ʟᴀᴡ.</i>\n\n"
        "• <code>/ban</code> | <code>/unban</code> : ᴍᴀɴᴀɢᴇ ʙᴀɴs\n"
        "• <code>/mute</code> | <code>/unmute</code> : sɪʟᴇɴᴄᴇ ᴜsᴇʀs\n"
        "• <code>/tmute</code> : ᴛᴇᴍᴘᴏʀᴀʀʏ ᴍᴜᴛᴇ\n"
        "• <code>/warn</code> | <code>/unwarn</code> : ᴡᴀʀɴɪɴɢ sʏsᴛᴇᴍ\n"
        "• <code>/promote</code> | <code>/demote</code> : ᴀᴅᴍɪɴ ʀᴏʟᴇs\n"
        "• <code>/pin</code> | <code>/unpin</code> : sᴛɪᴄᴋʏ ᴍsɢs\n"
        "• <code>/dlt</code> : ᴄʟᴇᴀɴ ᴄʜᴀᴛ"
    ),
    "help_eco": (
        "💰 <b>𝐄𝐜𝐨𝐧𝐨𝐦𝐲 & 𝐖𝐞𝐚𝐥𝐭𝐡</b>\n<i>ɢʀɪɴᴅ, ᴛʀᴀᴅᴇ, ᴀɴᴅ sᴛᴀᴄᴋ ᴄᴀsʜ.</i>\n\n"
        "• <code>/daily</code> : ᴄʟᴀɪᴍ ᴅᴀɪʟʏ ᴄᴏɪɴs\n"
        "• <code>/give [ɪᴅ] [ᴀᴍᴛ]</code> : ᴛʀᴀɴsғᴇʀ ꜰᴜɴᴅs\n"
        "• <code>/shop</code> | <code>/buy</code> : ʙᴜʏ ɪᴛᴇᴍs\n"
        "• <code>/claim</code> : Cʟᴀɪᴍ Rᴇᴡᴀʀᴅꜱ Iɴ Gʀᴏᴜᴘꜱ\n"
        "• <code>/redeem [ᴄᴏᴅᴇ]</code> : ᴜsᴇ ᴘʀᴏᴍᴏ ᴄᴏᴅᴇ\n"
        "• <code>/toprich</code> : ᴡᴇᴀʟᴛʜ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ"
    ),
    "help_game": (
        "🕹️ <b>𝐆𝐚𝐦𝐞 & 𝐂𝐨𝐦𝐛𝐚𝐭</b>\n<i>ʜᴜɴᴛ, ꜰɪɢʜᴛ, ᴀɴᴅ sᴜʀᴠɪᴠᴇ.</i>\n\n"
        "⚔️ <b>ᴄᴏᴍʙᴀᴛ</b>\n"
        "• <code>/card &lt;amount&gt;</code> : Cᴀʀᴅ Gᴀᴍᴇ\n"
        "• <code>/heist</code> : Gʀᴏᴜᴘ Hᴇɪsᴛ\n"
        "• <code>/kill [reply]</code>: Kɪʟʟ Uꜱᴇʀꜱ\n"
        "• <code>/rob [reply] [amt]</code> : ʀᴏʙ ᴄᴏɪɴs\n"
        "• <code>/revive</code> : ʙʀɪɴɢ ʙᴀᴄᴋ ᴛʜᴇ ᴅᴇᴀᴅ\n"
        "• <code>/protect</code> : ʜɪʀᴇ ᴀʀᴍᴏʀ\n\n"
        "📊 <b>sᴛᴀᴛs & ʀᴀɴᴋ</b>\n"
        "• <code>/bal</code> | <code>/status</code> : ᴠɪᴇᴡ ᴘʀᴏꜰɪʟᴇ\n"
        "• <code>/topkills</code> : ᴅᴇᴀᴅʟɪᴇsᴛ ᴘʟᴀʏᴇʀs\n"
        "• <code>/rankers</code> : ɢʟᴏʙᴀʟ ᴇxᴘ ʀᴀɴᴋs"
    ),
    "help_ai": (
        "🧠 <b>𝐀𝐈 & 𝐔𝐭𝐢𝐥𝐢𝐭𝐢𝐞𝐬</b>\n<i>sᴍᴀʀᴛ ᴛᴏᴏʟs ꜰᴏʀ ᴇᴠᴇʀʏᴅᴀʏ ᴜsᴇ.</i>\n\n"
        "• <code>/q</code> : ᴍᴀᴋᴇ ᴀ ǫᴜᴏᴛᴇ sᴛɪᴄᴋᴇʀ\n"
        "• <code>/font [ᴛᴇxᴛ]</code> : sᴛʏʟɪsʜ ᴛᴇxᴛ\n"
        "• <code>/id</code> : ɢᴇᴛ ᴜɴɪǫᴜᴇ ɪᴅs\n"
        "• <code>/voice [reply]</code>: Tᴇxᴛ Tᴏ Vᴏɪᴄᴇ\n"
        "• <code>/feedback</code> : ʀᴇᴘᴏʀᴛ ɪssᴜᴇs"
    ),
    "help_social": (
        "🚩 <b>𝐒𝐨𝐜𝐢𝐚𝐥 & 𝐅𝐮𝐧</b>\n<i>ɪɴᴛᴇʀᴀᴄᴛ ᴡɪᴛʜ ᴛʜᴇ ᴄᴏᴍᴍᴜɴɪᴛʏ.</i>\n\n"
        "• <code>/kiss</code> | <code>/hug</code> | <code>/slap</code>\n"
        "• <code>/bite</code> | <code>/punch</code>\n"
        "• <code>/referral</code> : ɪɴᴠɪᴛᴇ ꜰʀɪᴇɴᴅs\n"
        "• <code>/stats</code> : ᴄʜᴀᴛ sᴛᴀᴛɪsᴛɪᴄs (ᴏᴡɴᴇʀ ᴏɴʟʏ)"
    )
}


def get_main_keyboard(bot_username):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👨‍💻 ᴅᴇᴠᴇʟᴏᴘᴇʀ", url=f"tg://user?id={OWNER_ID}")],
        [InlineKeyboardButton("✨ sᴜᴘᴘᴏʀᴛ", url="https://t.me/+wlkvrPKG8wdkMDNl"),
         InlineKeyboardButton("📢 ᴜᴘᴅᴀᴛᴇs", url="https://t.me/ig_yuukii")],
        [InlineKeyboardButton("📚 ʜᴇʟᴘ & ᴄᴏᴍᴍᴀɴᴅs", callback_data="help_main")],
        [InlineKeyboardButton("➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ", url=f"https://t.me/{bot_username}?startgroup=true")]
    ])


def get_help_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛡️ ᴍᴀɴᴀɢᴇ", callback_data="help_manage"), InlineKeyboardButton("💰 ᴇᴄᴏɴᴏᴍʏ", callback_data="help_eco")],
        [InlineKeyboardButton("🕹️ ɢᴀᴍᴇ", callback_data="help_game"), InlineKeyboardButton("🚩 sᴏᴄɪᴀʟ", callback_data="help_social")],
        [InlineKeyboardButton("🧠 ᴀɪ & ᴛᴏᴏʟs", callback_data="help_ai")],
        [InlineKeyboardButton("❌ ᴄʟᴏsᴇ ᴍᴇɴᴜ", callback_data="close_menu")]
    ])


# ============================ REFERRAL ============================

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot = await context.bot.get_me()
    unique_code = str(uuid.uuid4())[:8]

    referrals_db.insert_one({"code": unique_code, "creator_id": user.id, "claimed_by": []})
    link = f"https://t.me/{bot.username}?start=ref_{unique_code}"

    text = f"""
🎁 <b>ʏᴏᴜʀ ɴᴇᴡ ʀᴇꜰᴇʀʀᴀʟ ʟɪɴᴋ</b>

🔗 {link}

ɪɴᴠɪᴛᴇ ꜰʀɪᴇɴᴅꜱ ᴜꜱɪɴɢ ᴛʜɪꜱ ʟɪɴᴋ
💰 ʀᴇᴡᴀʀᴅ: <code><b>1000 ᴄᴏɪɴꜱ</b></code>

🧩 <b>ɴᴏᴛᴇ :</b>
• ᴇᴠᴇʀʏ ᴛɪᴍᴇ ʏᴏᴜ ᴜsᴇ /referral, ᴀ ɴᴇᴡ ʟɪɴᴋ ɪs ᴍᴀᴅᴇ.
• ᴀ ꜰʀɪᴇɴᴅ ᴄᴀɴ ᴜsᴇ ᴍᴜʟᴛɪᴘʟᴇ ʟɪɴᴋs ꜰʀᴏᴍ ʏᴏᴜ ᴛᴏ ɢɪᴠᴇ ʏᴏᴜ ᴍᴏɴᴇʏ!
"""
    await update.message.reply_text(text, parse_mode='HTML')


# ============================ WELCOME ============================

async def set_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram.constants import ChatMemberStatus
    from bot.config import chat as chat_col

    if not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    member = await context.bot.get_chat_member(chat_id, user_id)
    is_admin = member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    is_creator = user_id == OWNER_ID

    if not (is_admin or is_creator):
        await update.message.reply_text("❌ 𝖸𝗈𝗎 𝗇𝖾𝖾𝖽 𝗍𝗈 𝖻𝖾 𝖺𝗇 𝖠𝖽𝗆𝗂𝗇 𝗍𝗈 𝗎𝗌𝖾 𝗍𝗁𝗂𝗌 𝖼𝗈ᴍ𝗆𝖺𝗇𝖽!")
        return

    if not context.args:
        await update.message.reply_text("📝 𝖴𝗌𝖺𝗀𝖾: <code>/setlink https://t.me/yourlink</code>", parse_mode="HTML")
        return

    new_link = context.args[0]
    chat_col.update_one({"chat_id": chat_id}, {"$set": {"welcome_link": new_link}}, upsert=True)
    await update.message.reply_text(f"✅ <b>𝖶𝖾𝗅𝖼𝗈ᴍ𝖾 𝗅𝗂𝗇𝗄 𝗌𝖺𝗏𝖾𝖽!</b>\nNew Link: {new_link}", parse_mode="HTML")


async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.config import chat as chat_col
    chat_id = update.effective_chat.id
    chat_data = chat_col.find_one({"chat_id": chat_id})

    if chat_data and chat_data.get("welcome_link"):
        group_link = chat_data.get("welcome_link")
        button_text = "🐜 Jᴏɪɴ Mʏ Sᴡᴇᴇᴛ Hᴏᴍᴇ 🏡"
    else:
        group_link = "https://t.me/im_yuuribot?start=welcome"
        button_text = "✨ Sᴛᴀʀᴛ Mᴇ Iɴ DM ✨"

    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            continue
        user_mention = member.mention_html()
        text = random.choice(WELCOME_STYLES).format(user=user_mention)
        keyboard = [[InlineKeyboardButton(button_text, url=group_link)]]
        await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ============================ PAY ============================

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.config import users_col
    msg = update.effective_message
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    bot_username = context.bot.username

    website_url = "https://yuuri_premium.oneapp.dev/"
    benefits_link = "https://t.me/ig_yuukii/51"
    banner_url = "https://i.ibb.co/GQPQGdNF/x.jpg"

    if chat_type in ["group", "supergroup"]:
        redirect_url = f"https://t.me/{bot_username}?start=pay"
        keyboard = [[InlineKeyboardButton("💳 Cᴏɴᴛɪɴᴜᴇ Tᴏ Pᴀʏ", url=redirect_url)]]
        return await msg.reply_text(
            "⚠️ <b>Usᴇ Tʜɪs Cᴏᴍᴍᴀɴᴅ Iɴ DM</b>\n\nCʟɪᴄᴋ ᴛʜᴇ ʙᴇʟᴏᴡ ʙᴜᴛᴛᴏɴ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ!",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML
        )

    user_data = await users_col.find_one({"id": user_id})
    is_prem = user_data.get("premium", False) if user_data else False
    expiry_date = user_data.get("premium_until", "N/A") if user_data else "N/A"

    if is_prem:
        text = (
            f"💓 <b>Yᴏᴜ ᴀʀᴇ ᴀʟʀᴇᴀᴅʏ ᴀ Pʀᴇᴍɪᴜᴍ Uꜱᴇʀ.</b>\n"
            f"⏳ <b>Pʀᴇᴍɪᴜᴍ Vᴀʟɪᴅ Uɴᴛɪʟ:</b> <code>{expiry_date}</code>\n"
            f"🔄 <i>Iꜰ Yᴏᴜ Rᴇʙᴜʏ Tʜᴇ Pʀᴇᴍɪᴜᴍ, Yᴏᴜʀ Pʀᴇᴍɪᴜᴍ Wɪʟʟ Bᴇ Exᴛᴇɴᴅᴇᴅ.</i>\n\n"
            f"👉 <b>Gɪꜰᴛ Tᴏ A Fʀɪᴇɴᴅ:</b>\n⚠️ <b>Iᴍᴘᴏʀᴛᴀɴᴛ:</b> Eɴᴛᴇʀ Tʜᴇɪʀ Tᴇʟᴇɢʀᴀᴍ ID Iɴ Tʜᴇ Wᴇʙsɪᴛᴇ."
        )
        keyboard = [[InlineKeyboardButton("🎁 Gɪғᴛ Pʀᴇᴍɪᴜᴍ", url=website_url)],
                    [InlineKeyboardButton("💎 Pʀᴇᴍɪᴜᴍ Bᴇɴᴇғɪᴛs", url=benefits_link)]]
    else:
        text = (
            "💓 <b>Yᴜᴜʀɪ Pʀᴇᴍɪᴜᴍ Aᴄᴄᴇꜱꜱ</b>\n\n"
            "⚠️ <b>Iᴍᴘᴏʀᴛᴀɴᴛ:</b> Eɴᴛᴇʀ Yᴏᴜʀ Tᴇʟᴇɢʀᴀᴍ ID Iɴ Tʜᴇ ID Fɪᴇʟᴅ.\n👉 <b>Cʜᴇᴄᴋ Tᴇʟᴇɢʀᴀᴍ Iᴅ:</b> <code>/id</code>"
        )
        keyboard = [[InlineKeyboardButton("💗 Pᴀʏ Nᴏᴡ 💗", url=website_url)],
                    [InlineKeyboardButton("💗 Pʀᴇᴍɪᴜᴍ Bᴇɴᴇғɪᴛs 💗", url=benefits_link)]]

    try:
        await msg.reply_photo(photo=banner_url, caption=text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        await msg.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))


# ============================ START ============================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.games_roulette import cmd_snake
    from bot.economy import daily

    user = update.effective_user
    args = context.args

    if args and args[0].startswith("captcha_"):
        return await handle_captcha_verify(update, context)
    if args and args[0] == "daily":
        return await daily(update, context)
    if context.args and context.args[0] == "play_snake":
        await cmd_snake(update, context)
        return
    if args and args[0] == "pay":
        return await pay(update, context)

    if args and args[0].startswith("ref_"):
        ref_code = args[0].replace("ref_", "")
        ref_data = referrals_db.find_one({"code": ref_code})

        if ref_data:
            creator_id = ref_data["creator_id"]
            claimed_list = ref_data.get("claimed_by", [])

            if len(claimed_list) >= 100:
                await update.message.reply_text("🚫 <b>ᴛʜɪs ʀᴇꜰᴇʀʀᴀʟ ʟɪɴᴋ ɪs ꜰᴜʟʟ!</b>\nɪᴛ ʜᴀs ᴀʟʀᴇᴀᴅʏ ʀᴇᴀᴄʜᴇᴅ ᴛʜᴇ ʟɪᴍɪᴛ ᴏꜰ 100 ᴜsᴇʀs.", parse_mode=ParseMode.HTML)
            elif user.id == creator_id:
                await update.message.reply_text("❌ <b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ᴜsᴇ ʏᴏᴜʀ ᴏᴡɴ ʟɪɴᴋ!</b>", parse_mode=ParseMode.HTML)
            else:
                already_referred = referrals_db.find_one({"creator_id": creator_id, "claimed_by": user.id})
                if already_referred:
                    await update.message.reply_text("⚠️ <b>ʏᴏᴜ ᴀʀᴇ ᴀʟʀᴇᴀᴅʏ ʀᴇɢɪsᴛᴇʀᴇᴅ ɪɴ ᴛʜᴇ ᴜsᴇʀs ʀᴇꜰᴇʀʀᴀʟ ᴄᴀɴ'ᴛ ᴜsᴇ ʜɪs ʀᴇꜰᴇʀʀᴀʟs ᴀɢᴀɪɴ.</b>", parse_mode=ParseMode.HTML)
                else:
                    referrals_db.update_one({"code": ref_code}, {"$push": {"claimed_by": user.id}})
                    users.update_one({"id": creator_id}, {"$inc": {"coins": 1000}})
                    try:
                        await context.bot.send_message(creator_id, f"💰 <b>ʀᴇꜰᴇʀʀᴀʟ sᴜᴄᴄᴇss!</b>\n{user.first_name} ᴜsᴇᴅ ʏᴏᴜʀ ʟɪɴᴋ. +1000 ᴄᴏɪɴs!", parse_mode=ParseMode.HTML)
                    except Exception:
                        pass

    get_user(user)

    if args and args[0].startswith("recharge_"):
        try:
            payload_parts = args[0].split("_")
            target_uid = int(payload_parts[1])
            recharge_code = payload_parts[2]

            log_config = await async_db.settings.find_one({"config": "log_group"})
            target_chat = log_config["group_id"] if log_config else OWNER_ID

            alert_text = (
                "💳 <b>Gᴏᴏɢʟᴇ Pʟᴀʏ Cᴏᴅᴇ Sᴜʙᴍɪᴛᴛᴇᴅ</b>\n\n"
                f"👤 <b>User ID:</b> <code>{target_uid}</code>\n🔑 <b>Code:</b> <code>{recharge_code}</code>\n"
                f"💰 <b>Plan:</b> Check website selection\n\n<i>Verify and use:</i> <code>/activate premium 7d {target_uid}</code>"
            )
            await context.bot.send_message(chat_id=target_chat, text=alert_text, parse_mode=ParseMode.HTML)
            return await update.message.reply_text(
                "✅ <b>Sᴜʙᴍɪssɪᴏɴ Rᴇᴄᴇɪᴠᴇᴅ!</b>\n\nYᴏᴜʀ ₹20 Rᴇᴄʜᴀʀɢᴇ Cᴏᴅᴇ ʜᴀs ʙᴇᴇɴ sᴇɴᴛ ᴛᴏ RJ ғᴏʀ ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ.\nᴘʟᴇᴀsᴇ ᴡᴀɪᴛ 𝟷𝟻-𝟹𝟶 ᴍɪɴᴜᴛᴇs.",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"Website Bridge Error: {e}")

    caption = (
        f"<b>ᴡᴇʟᴄᴏᴍᴇ, {user.first_name}!</b> 👋\n\n"
        f"<blockquote>ɪ ᴀᴍ <b>ʏᴜᴜʀɪ</b> — ʜᴇʀᴇ ᴛᴏ ᴇɴʜᴀɴᴄᴇ ʏᴏᴜʀ ᴇxᴘᴇʀɪᴇɴᴄᴇ ᴏɴ ᴛᴇʟᴇɢʀᴀᴍ. ᴇɴᴊᴏʏ ʏᴏᴜʀ ᴊᴏᴜʀɴᴇʏ ᴡɪᴛʜ ᴍᴇ!\n\n"
        f"ᴜsᴇ: /referral ᴛᴏ sʜᴀʀᴇ ʏᴏᴜʀ ʟɪɴᴋ. ɪᴛ ʜᴇʟᴘs ᴍᴇ ɢʀᴏᴡ ᴀɴᴅ ʙᴏᴏsᴛs ʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ ᴀs ᴡᴇʟʟ.</blockquote>\n\n"
        f"ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴀɴᴅ ʟᴇᴛ ᴍᴇ ᴛᴀᴋᴇ ᴄᴀʀᴇ ᴏғ ᴛʜᴇ ʀᴇsᴛ."
    )
    await update.message.reply_photo(photo=IMG_MAIN, caption=caption, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(context.bot.username))


# ============================ HELP ============================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "✨ <b>ʏᴜᴜʀɪ ʜᴇʟᴘ ᴍᴇɴᴜ</b>\n\n<i>sᴇʟᴇᴄᴛ ᴀ ᴍᴏᴅᴜʟᴇ ᴛᴏ ᴠɪᴇᴡ ᴜsᴀɢᴇ:</i>"
    await update.message.reply_photo(photo=IMG_HELP, caption=text, parse_mode=ParseMode.HTML, reply_markup=get_help_keyboard())


async def handle_help_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if not data.startswith(("help_", "close_menu", "back_to_start")):
        return

    await query.answer()
    try:
        if data == "help_main":
            text = "✨ <b>ʏᴜᴜʀɪ ʜᴇʟᴘ ᴍᴇɴᴜ</b>\n\n<i>sᴇʟᴇᴄᴛ ᴀ ᴍᴏᴅᴜʟᴇ ᴛᴏ ᴠɪᴇᴡ ᴜsᴀɢᴇ:</i>"
            await query.edit_message_media(media=InputMediaPhoto(media=IMG_HELP, caption=text, parse_mode=ParseMode.HTML), reply_markup=get_help_keyboard())
        elif data in HELP_TEXTS:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="help_main")]])
            await query.edit_message_caption(caption=HELP_TEXTS[data], reply_markup=keyboard, parse_mode=ParseMode.HTML)
        elif data == "close_menu":
            await query.delete_message()
        elif data == "back_to_start":
            caption = f"<b>ᴡᴇʟᴄᴏᴍᴇ, {update.effective_user.first_name}!</b> 👋\n\n<blockquote>ɪ ᴀᴍ <b>ʏᴜᴜʀɪ</b>.</blockquote>"
            await query.edit_message_media(media=InputMediaPhoto(media=IMG_MAIN, caption=caption, parse_mode=ParseMode.HTML), reply_markup=get_main_keyboard(context.bot.username))
    except Exception as e:
        print(f"Help Callback Error: {e}")
