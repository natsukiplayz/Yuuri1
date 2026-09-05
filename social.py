#!/usr/bin/env python3
"""Fun/social commands: kiss, hug, slap, bite, kick, punch, murder gifs;
quote-sticker generator; font converter; TTS voice; sticker pack saving."""

import os
import random
import base64
import asyncio
import logging
from io import BytesIO

import httpx
import edge_tts
from telegram import Update, InputSticker
from telegram.ext import ContextTypes

from bot.helpers import get_fancy_text

# ============================ GIF INTERACTIONS ============================

KISS_GIFS = [
    "CgACAgQAAxkBAAFEqUpps88XuvzJ7gKt9RgT8r3_MgpGhwACgAcAAvwpjFMTm9An_6_McToE",
    "CgACAgQAAxkBAAFEqThps851iVq2fmWNXo3sq1HTx8qP4QACggMAAp897VKT2Ktemaxp2joE",
    "CgACAgQAAxkBAAFEqUxps89ecJSnnN0UOSk13Y6xp7ZI3QACvgQAAp-RzVId4q-39NiNDjoE"
]
HUG_GIFS = [
    "CgACAgQAAxkBAAFEqVVps9AQMt85jqkHjtSeCzgLLfaFngAC7QUAAkWIzFF_W-zVNIr6QjoE",
    "CgACAgQAAxkBAAFEqVZps9AQUhBv94fq6VuPvtMeifMetQACpwgAAsq9fFK5IuJw0Q6KazoE",
    "CgACAgQAAxkBAAFEqVRps9AQLzL3MSq0ciO-AAEzsh47bOEAAq4FAAIL_z1TzpL3e-CUa0I6BA"
]
BITE_GIFS = [
    "CgACAgQAAxkBAAFEqXhps9F32LDcpcXH9NOS-ktnVDG-HgACOwMAAqV6RFELerv_D_rO8joE",
    "CgACAgQAAxkBAAFEqXlps9F3rRMKmv4PISyGVOxXs4v4EAACJQMAAudMBVPQtxclFSEtgDoE",
    "CgACAgQAAxkBAAFEqXdps9F3CUDP_uXjN4HWcMBiacvatQACBQMAAsV7BVM4j4JdPptQDzoE"
]
SLAP_GIFS = [
    "CgACAgQAAxkBAAFEqaJps9JRC5Mfb5jNr5XgAm6RMWovEAACyQUAApZrVVAar3BemvEERjoE",
    "CgACAgQAAxkBAAFEqaNps9JRkv0XbMCeGvsQFLaGGUyuwAACbAMAAvp45FPnsYLcLNShDToE",
    "CgACAgQAAxkBAAFEqaRps9JRPuXBNf7aa9v_whuwU2nLEgACPQMAAhreBFPkfVHAxMcKpjoE"
]
KICK_GIFS = [
    "CgACAgQAAxkBAAFEq3Zps-hFW0CEBmL6u7njUYLGr22q3AAC0gYAAog2jFBmFZXucvqURjoE",
    "CgACAgQAAxkBAAFEq3Vps-hF0AJg7zywn9El8BJUA3DzEwAC8wIAAnvgBFMZAV2MHSAZlzoE",
    "CgACAgQAAxkBAAFEq3dps-hFNX4ZQ4rdT5s32Wnn3NhVAAPIBwACgbe1UVl5Z4WkKnrHOgQ"
]
PUNCH_GIFS = [
    "CgACAgQAAxkBAAFEq4pps-jh2SYq4RCb0d3QXA1ano0ihgACmQYAAmNlfVBPu8eB0yXiOzoE",
    "CgACAgQAAxkBAAFEq4tps-jh9BFfmDjK6XNDKL15Pjzn9wAC8wIAAoSnLVNyqAKuMP98wjoE",
    "CgACAgQAAxkBAAFEq4xps-jh_GtyKDOrEQABr0ParkF7kpEAAsMCAAInZQ1THZgTJK0G2bA6BA"
]
MURDER_GIFS = [
    "CgACAgQAAxkBAAFEq5tps-nhOiSq-vuyjmk13zm30l7R5gAC8AIAAvmANVPbgt6AF05WbzoE",
    "CgACAgQAAxkBAAFEq5xps-nhBH8Ml1UEBCjctbNpBmH1jwACLQMAAuLJDFMgyege_IFM2ToE",
    "CgACAgQAAxkBAAFEq51ps-nhCb0TEIbTPAIBrY2fjxF4cgACQQMAAhQTJVOQ4cLMXsbquToE"
]

WARNING_TEXT = "Cʜᴜᴘᴘ!! Wᴀʀɴᴀ Yᴜᴜᴋɪ Kᴏ Bᴛᴀ Dᴜɴɢɪ 😒"


async def check_target(update: Update, context: ContextTypes.DEFAULT_TYPE, action):
    if not update.message.reply_to_message:
        await update.message.reply_text("ʀᴇᴘʟʏ ᴛᴏ sᴏᴍᴇᴏɴᴇ ғɪʀsᴛ")
        return None

    sender = update.effective_user
    target = update.message.reply_to_message.from_user
    bot_id = context.bot.id

    if sender.id == target.id:
        await update.message.reply_text(f"ʏᴏᴜ ᴄᴀɴ'ᴛ {action} ʏᴏᴜʀsᴇʟғ")
        return None
    if target.id == bot_id:
        await update.message.reply_text(WARNING_TEXT)
        return None
    return sender, target


async def kiss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = await check_target(update, context, "ᴋɪss")
    if not data:
        return
    sender, target = data
    await update.message.reply_animation(random.choice(KISS_GIFS), caption=f"{sender.mention_html()} Kɪꜱꜱᴇᴅ {target.mention_html()}", parse_mode="HTML")


async def hug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = await check_target(update, context, "ʜᴜɢ")
    if not data:
        return
    sender, target = data
    await update.message.reply_animation(random.choice(HUG_GIFS), caption=f"{sender.mention_html()} Hᴜɢɢᴇᴅ {target.mention_html()}", parse_mode="HTML")


async def bite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = await check_target(update, context, "ʙɪᴛᴇ")
    if not data:
        return
    sender, target = data
    await update.message.reply_animation(random.choice(BITE_GIFS), caption=f"{sender.mention_html()} Bɪᴛ {target.mention_html()}", parse_mode="HTML")


async def slap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = await check_target(update, context, "sʟᴀᴘ")
    if not data:
        return
    sender, target = data
    await update.message.reply_animation(random.choice(SLAP_GIFS), caption=f"{sender.mention_html()} Sʟᴀᴘᴘᴇᴅ {target.mention_html()}", parse_mode="HTML")


async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = await check_target(update, context, "ᴋɪᴄᴋ")
    if not data:
        return
    sender, target = data
    await update.message.reply_animation(random.choice(KICK_GIFS), caption=f"{sender.mention_html()} Kɪᴄᴋᴇᴅ {target.mention_html()}", parse_mode="HTML")


async def punch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = await check_target(update, context, "ᴘᴜɴᴄʜ")
    if not data:
        return
    sender, target = data
    await update.message.reply_animation(random.choice(PUNCH_GIFS), caption=f"{sender.mention_html()} Pᴜɴᴄʜᴇᴅ {target.mention_html()}", parse_mode="HTML")


async def murder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = await check_target(update, context, "ᴍᴜʀᴅᴇʀ")
    if not data:
        return
    sender, target = data
    await update.message.reply_animation(random.choice(MURDER_GIFS), caption=f"{sender.mention_html()} Mᴜʀᴅᴇʀᴇᴅ {target.mention_html()}", parse_mode="HTML")


# ============================ RANDOM STICKER REPLY ============================

MY_PACKS = ["YUUKI321", "Slaybie_by_fStikBot", "Bocchi_the_Rock_Part_1_by_Fix_x_Fox"]


async def reply_with_random_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import constants
    if not update.message or not update.message.sticker:
        return

    chat_type = update.effective_chat.type
    is_reply_to_bot = (
        update.message.reply_to_message and
        update.message.reply_to_message.from_user.id == context.bot.id
    )

    if chat_type == constants.ChatType.PRIVATE or is_reply_to_bot:
        chosen_pack = random.choice(MY_PACKS)
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.CHOOSE_STICKER)
            await asyncio.sleep(1)
            sticker_set = await context.bot.get_sticker_set(name=chosen_pack)
            if sticker_set and sticker_set.stickers:
                random_sticker = random.choice(sticker_set.stickers)
                await update.message.reply_sticker(sticker=random_sticker.file_id)
        except Exception as e:
            logging.error(f"Sticker Pack {chosen_pack} error: {e}")


# ============================ SAVE STICKER TO USER PACK ============================

async def save_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    user_id = user.id

    if not message.reply_to_message or not message.reply_to_message.sticker:
        await message.reply_text("❌ Rᴇᴘʟʏ Tᴏ A Sᴛɪᴄᴋᴇʀ Tᴏ Sᴀᴠᴇ Iᴛ.")
        return

    sticker = message.reply_to_message.sticker

    if sticker.is_animated:
        st_logic, fancy_type, type_desc = "animated", "Aɴɪᴍᴀᴛᴇᴅ", "ᴀʟʟ Aɴɪᴍᴀᴛᴇᴅ"
    elif sticker.is_video:
        st_logic, fancy_type, type_desc = "video", "Vɪᴅᴇᴏ", "ᴀʟʟ Vɪᴅᴇᴏ"
    else:
        st_logic, fancy_type, type_desc = "static", "Sᴛᴀᴛɪᴄ", "ᴀʟʟ Nᴏɴ-ᴀɴɪᴍᴀᴛᴇᴅ"

    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    pack_name = f"user_{user_id}_{st_logic}_by_{bot_username}".lower()
    pack_title = f"{user.first_name[:15]}'s {fancy_type} Sᴛɪᴄᴋᴇʀs"

    saving_msg = await message.reply_text("🪄 Sᴀᴠɪɴɢ Sᴛɪᴄᴋᴇʀ...")

    try:
        input_sticker = InputSticker(sticker=sticker.file_id, emoji_list=[sticker.emoji or "🙂"], format=st_logic)
        try:
            await context.bot.add_sticker_to_set(user_id=user_id, name=pack_name, sticker=input_sticker)
        except Exception as e:
            err = str(e).lower()
            if "stickerset_invalid" in err or "not found" in err:
                await context.bot.create_new_sticker_set(
                    user_id=user_id, name=pack_name, title=pack_title,
                    stickers=[input_sticker], sticker_format=st_logic
                )
            else:
                raise e

        description = (
            f"🔰 ꜱᴛɪᴄᴋᴇʀ Sᴀᴠᴇᴅ Tᴏ Yᴏᴜʀ {fancy_type} Pᴀᴄᴋ\n\n"
            f"{type_desc}\nʟɪᴍɪᴛ: 120 Sᴛɪᴄᴋᴇʀꜱ\n\n"
            f"🤖 Tᴀᴋᴇꜱ 2-3 Mɪɴᴜᴛᴇꜱ Tᴏ Sʜᴏᴡ Tʜᴇ Sᴛɪᴄᴋᴇʀ Iɴ Yᴏᴜʀ Pᴀᴄᴋ 🪄"
        )
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        await saving_msg.edit_text(
            text=description,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👀 Oᴘᴇɴ Pᴀᴄᴋ", url=f"https://t.me/addstickers/{pack_name}")]])
        )
    except Exception as e:
        logging.error(f"Sticker Error: {e}")
        error_msg = str(e)
        if "Peer_id_invalid" in error_msg:
            await saving_msg.edit_text("⚠️ Sᴛᴀʀᴛ ᴍᴇ ɪɴ Private Chat (PM) ꜰɪʀꜱᴛ!")
        else:
            await saving_msg.edit_text(f"❌ Cᴀɴ'ᴛ Sᴀᴠᴇ: {error_msg[:50]}")


# ============================ QUOTE STICKER GENERATOR ============================

COLOR_MAP = {
    "red": "#FF595A", "blue": "#3E885B", "green": "#008000",
    "yellow": "#FFD700", "pink": "#FFC0CB", "purple": "#800080",
    "dark": "#1b1429", "black": "#000000"
}


async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
        return await msg.reply_text("❌ Rᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴛᴏ ᴄʀᴇᴀᴛᴇ Qᴜᴏᴛᴇ.")

    bg_color = "#1b1429"
    is_multi = False
    if context.args:
        args_str = [a.lower() for a in context.args]
        if "r" in args_str or "reply" in args_str:
            is_multi = True
        for name, hex_val in COLOR_MAP.items():
            if name in args_str:
                bg_color = hex_val

    target_msg = msg.reply_to_message
    messages_list = []

    if is_multi and target_msg.reply_to_message:
        parent = target_msg.reply_to_message
        messages_list.append({
            "entities": [], "avatar": True,
            "from": {"id": parent.from_user.id, "name": parent.from_user.full_name, "photo": True},
            "text": parent.text or parent.caption or "Media"
        })

    messages_list.append({
        "entities": [], "avatar": True,
        "from": {"id": target_msg.from_user.id, "name": target_msg.from_user.full_name, "photo": True},
        "text": target_msg.text or target_msg.caption or ""
    })

    loading = await msg.reply_text("🪄 Gᴇɴᴇʀᴀᴛɪɴɢ HD Qᴜᴏᴛᴇ...")

    payload = {
        "type": "quote", "format": "webp", "backgroundColor": bg_color,
        "width": 512, "height": 768 if is_multi else 512, "scale": 2,
        "messages": messages_list
    }

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post("https://bot.lyo.su/quote/generate", json=payload, timeout=30.0,
                                     headers={"Content-Type": "application/json"})

        if res.status_code == 200:
            data = res.json()
            img_data = data.get("result", {}).get("image") or data.get("image")
            sticker_file = BytesIO(base64.b64decode(img_data))
            sticker_file.name = "quote.webp"
            await msg.reply_sticker(sticker=sticker_file)
            await loading.delete()
        else:
            await loading.edit_text(f"❌ API Error: {res.status_code}")
    except Exception:
        await loading.edit_text("❌ Fᴀɪʟᴇᴅ ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ HD Qᴜᴏᴛᴇ.")


# ============================ FONT CONVERTER ============================

async def font_converter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usage_msg = (
        "❌ **Uꜱᴀɢᴇ:**\n"
        "1️⃣ `/font 1 Hello` (Direct text)\n"
        "2️⃣ Reply to a message with `/font 1`"
    )

    if not context.args:
        await update.message.reply_text(usage_msg, parse_mode="Markdown")
        return

    font_choice = context.args[0]
    if font_choice not in ["1", "2", "3"]:
        await update.message.reply_text(usage_msg, parse_mode="Markdown")
        return

    target_text = ""
    if len(context.args) > 1:
        target_text = " ".join(context.args[1:])
    elif update.message.reply_to_message:
        replied = update.message.reply_to_message
        target_text = replied.text or replied.caption

    if not target_text:
        await update.message.reply_text("❌ Nᴏ ᴛᴇxᴛ ꜰᴏᴜɴᴅ ᴛᴏ ᴄᴏɴᴠᴇʀᴛ!")
        return

    converted_text = get_fancy_text(target_text, font_choice)
    await update.message.reply_text(converted_text)


# ============================ VOICE (TTS) ============================

async def voice_msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usage_msg = "🎙️ Uꜱᴀɢᴇ: <code>/ᴠᴏɪᴄᴇ 1|2 Rᴇᴘʟʏ/Tᴇxᴛ.</code>"

    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text(usage_msg, parse_mode="HTML")
        return

    choice = context.args[0] if context.args else "1"

    if choice == "1":
        v_id, v_rate, v_pitch = "en-US-AvaNeural", "+12%", "+0Hz"
    elif choice == "2":
        v_id, v_rate, v_pitch = "hi-IN-SwaraNeural", "+10%", "+1Hz"
    else:
        v_id, v_rate, v_pitch = "en-US-AvaNeural", "+12%", "+0Hz"

    if update.message.reply_to_message and update.message.reply_to_message.text:
        text = update.message.reply_to_message.text
    else:
        text = " ".join(context.args[1:]) if len(context.args) > 1 else ""

    if not text:
        await update.message.reply_text(usage_msg, parse_mode="HTML")
        return

    file_name = f"v_{update.effective_user.id}.ogg"

    try:
        communicate = edge_tts.Communicate(text, v_id, rate=v_rate, pitch=v_pitch)
        await communicate.save(file_name)
        with open(file_name, 'rb') as vn:
            await update.message.reply_voice(voice=vn)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if os.path.exists(file_name):
            os.remove(file_name)
