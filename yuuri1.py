#!/usr/bin/env python3

import os
import logging
import random
import requests
from pymongo import MongoClient
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================= TERMUX +srv FIX =================
import dns.resolver

# Override default resolver to use public DNS (Google + Cloudflare)
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ['8.8.8.8', '1.1.1.1']

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_NAME = "yuuri"
OWNER_ID = int(os.getenv("OWNER_ID"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# ================= MONGODB =================
client = MongoClient(MONGO_URI)  # <- after the DNS fix!
db = client["yuuri_db"]
users = db["users"]
guilds = db["guilds"]

# ================= LOG =================
logging.basicConfig(level=logging.INFO)

# ================= USER SYSTEM =================
def get_user(user):
    data = users.find_one({"id": user.id})

    if not data:
        data = {
            "id": user.id,
            "name": user.first_name,
            "coins": 100,
            "xp": 0,
            "level": 1,
            "inventory": []
        }
        users.insert_one(data)

    return data


def save_user(data):
    users.update_one({"id": data["id"]}, {"$set": data})

# ================= AUTO SAVE CHATS =================
async def save_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat:
        return

    # Upsert chat document
    db["chats"].update_one(
        {"id": chat.id},
        {"$set": {
            "id": chat.id,
            "type": chat.type,  # "private", "group", "supergroup"
            "title": getattr(chat, "title", None)
        }},
        upsert=True
    )

#================= BOT STATS (MongoDB + Styled Labels) =================
from pymongo import MongoClient

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 5773908061:
        return

    # ✅ MongoDB collections
    chats_col = db["chats"]
    users_col = db["users"]

    # 📊 Stats
    groups = chats_col.count_documents({"type": {"$in": ["group", "supergroup"]}})
    private = chats_col.count_documents({"type": "private"})
    blocked = chats_col.count_documents({"blocked": True})
    total_users = users_col.count_documents({})

    # 📝 Styled labels (directly)
    groups_label = "👥 Gʀᴏᴜᴘs"
    chats_label = "💬 Cʜᴀᴛs"
    users_label = "🧑‍💻 Tᴏᴛᴀʟ Usᴇʀs"
    blocked_label = "🚫 Bʟᴏᴄᴋᴇᴅ Usᴇʀs"

    text = (
        "📊 𝗬𝘂𝘂𝗿𝗶 𝗕𝗼𝘁 𝗦𝘁𝗮𝘁𝘀\n\n"
        f"{groups_label} : `{groups}`\n"
        f"{chats_label} : `{private}`\n"
        f"{users_label} : `{total_users}`\n"
        f"{blocked_label} : `{blocked}`\n"
    )

    await safe_send(update, context, text, parse_mode="Markdown")

# ================= LEVEL SYSTEM =================
def add_xp(user_data, amount=10):
    user_data["xp"] += amount
    need = user_data["level"] * 100

    if user_data["xp"] >= need:
        user_data["xp"] = 0
        user_data["level"] += 1

    save_user(user_data)

# ================= BOUNTY =================
async def bounty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Reply to someone to place bounty.")

    if not context.args:
        return await update.message.reply_text("Use: /bounty <amount>")

    try:
        amount = int(context.args[0])
    except ValueError:
        return await update.message.reply_text("❌ Aᴍᴏᴜɴᴛ ᴍᴜsᴛ ʙᴇ ᴀ ɴᴜᴍʙᴇʀ.")

    sender = get_user(update.effective_user)
    target_user = update.message.reply_to_message.from_user
    target = get_user(target_user)

    if sender["coins"] < amount:
        return await update.message.reply_text("❌ Nᴏᴛ ᴇɴᴏᴜɢʜ Cᴏɪɴs.")

    if target_user.id == update.effective_user.id:
        return await update.message.reply_text("❌ Yᴏᴜ ᴄᴀɴ'ᴛ ᴘʟᴀᴄᴇ ʙᴏᴜɴᴛʏ ᴏɴ ʏᴏᴜʀsᴇʟғ.")

    # Deduct coins from sender
    sender["coins"] -= amount
    # Add bounty to target
    target["bounty"] = target.get("bounty", 0) + amount

    # Save to MongoDB
    save_user(sender)
    save_user(target)

    # Fancy reply
    await update.message.reply_text(
            f"🎯 Bᴏᴜɴᴛʏ Pʟᴀᴄᴇᴅ!\n\n"
            f"👤 Tᴀʀɢᴇᴛ: {target_user.first_name}\n"
            f"💰 Rᴇᴡᴀʀᴅ: {amount} Cᴏɪɴs\n\n"
            f"⚔️ Kɪʟʟ ᴛʜᴇᴍ Tᴏ Cʟᴀɪᴍ!"
        )

#============================KILL (MongoDB + Styled Text)==========================
import random
from telegram import Update
from telegram.ext import ContextTypes

OWNER_ID = 5773908061  # <-- Replace with your Telegram user ID
BOT_ID = None  # Will be set dynamically

async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ID
    if BOT_ID is None:
        BOT_ID = context.bot.id  # set bot ID dynamically

    if not update.message:
        return

    msg = update.message
    user = update.effective_user

    # ❌ Block in private
    if update.effective_chat.type == "private":
        return await msg.reply_text("❌ Tʜɪs Cᴏᴍᴍᴀɴᴅ Cᴀɴ Oɴʟʏ Bᴇ Usᴇᴅ Iɴ Gʀᴏᴜᴘs.")

    # ❌ Must reply
    if not msg.reply_to_message:
        return await msg.reply_text("⚠️ Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ Yᴏᴜ Wᴀɴᴛ Tᴏ Kɪʟʟ.")

    target_user = msg.reply_to_message.from_user

    # ❌ Invalid target
    if not target_user:
        return await msg.reply_text("❌ Iɴᴠᴀʟɪᴅ Tᴀʀɢᴇᴛ.")

    # ❌ Cannot kill bot owner
    if target_user.id == OWNER_ID:
        return await msg.reply_text("😒 Yᴏᴜ Cᴀɴ'ᴛ Kɪʟʟ Mʏ Dᴇᴀʀᴇsᴛ Oᴡɴᴇʀ.")

    # ❌ Cannot kill bot itself
    if target_user.id == BOT_ID:
        return await msg.reply_text("😂 Nɪᴄᴇ Tʀʏ Oɴ Mᴇ!")

    # ❌ Cannot kill yourself
    if target_user.id == user.id:
        return await msg.reply_text("❌ Yᴏᴜ Cᴀɴ'ᴛ Kɪʟʟ Yᴏᴜʀsᴇʟғ.")

    # ✅ Get MongoDB economy data
    killer = get_user(user)
    victim = get_user(target_user)

    # ❌ Check if already dead
    if victim.get("dead", False):
        return await msg.reply_text(f"💀 {target_user.first_name} is already dead!")

    # 🎲 RANDOM REWARD
    reward = random.randint(50, 299)
    xp_gain = random.randint(1, 19)

    killer["coins"] += reward
    killer["xp"] = killer.get("xp", 0) + xp_gain
    killer["kills"] = killer.get("kills", 0) + 1

    # 🏰 Add Guild XP if applicable
    guild_name = killer.get("guild")
    if guild_name:
        await add_guild_xp(guild_name, context)

    # 💀 CLAIM BOUNTY (only once)
    bounty_reward = victim.get("bounty", 0)
    if bounty_reward > 0:
        killer["coins"] += bounty_reward
        victim["bounty"] = 0

    # ❌ Mark victim as dead
    victim["dead"] = True

    # 💾 Save data to MongoDB
    save_user(killer)
    save_user(victim)

    # 📢 Main kill message
    await msg.reply_text(
        f"👤 {user.first_name} Kɪʟʟᴇᴅ {target_user.first_name}\n"
        f"💰 Eᴀʀɴᴇᴅ: {reward} Cᴏɪɴs\n"
        f"⭐ Gᴀɪɴᴇᴅ: +{xp_gain} Xᴘ"
    )

    # 🎯 Bounty message (if exists)
    if bounty_reward > 0:
        await msg.reply_text(
            f"🎯 Bᴏᴜɴᴛʏ Cʟᴀɪᴍᴇᴅ!\n"
            f"💰 Eᴀʀɴᴇᴅ ᴇxᴛʀᴀ: {bounty_reward} Cᴏɪɴs!"
        )

#========================rob (MongoDB + limit + owner protection + font)========================
import time

MAX_ROB_PER_ATTEMPT = 10000  # maximum coins per attempt

async def robe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    msg = update.message
    robber_user = update.effective_user

    if not msg.reply_to_message:
        return await msg.reply_text("⚠️ Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ Yᴏᴜ Wᴀɴᴛ Tᴏ Rᴏʙ.")

    target_user = msg.reply_to_message.from_user

    # ❌ Cannot rob bots
    if not target_user or target_user.is_bot:
        return await msg.reply_text("🤖 Yᴏᴜ Cᴀɴɴᴏᴛ Rᴏʙ Tʜɪs Usᴇʀ.")

    # ❌ Cannot rob yourself
    if target_user.id == robber_user.id:
        return await msg.reply_text("❌ Yᴏᴜ Cᴀɴ'ᴛ Rᴏʙ Yᴏᴜʀsᴇʟғ.")

    # ❌ Cannot rob owner
    if target_user.id == OWNER_ID:
        return await msg.reply_text("👑 Yᴏᴜ Cᴀɴ'ᴛ Rᴏʙ Mʏ Dᴇᴀʀᴇsᴛ Oᴡɴᴇʀ 😒")

    # ❌ Missing amount
    if not context.args:
        return await msg.reply_text("Usage: /ʀᴏʙ <ᴀᴍᴏᴜɴᴛ>")

    # 💰 Parse amount
    try:
        amount = int(context.args[0])
    except ValueError:
        return await msg.reply_text("❌ Eɴᴛᴇʀ Vᴀʟɪᴅ Aᴍᴏᴜɴᴛ.")

    if amount <= 0:
        return await msg.reply_text("❌ Aᴍᴏᴜɴᴛ Mᴜsᴛ Bᴇ Pᴏsɪᴛɪᴠᴇ.")

    # 🔹 Fetch users from MongoDB
    robber = users_col.find_one({"user_id": robber_user.id}) or {"user_id": robber_user.id, "coins": 0}
    target = users_col.find_one({"user_id": target_user.id}) or {"user_id": target_user.id, "coins": 0}

    # 🛡 Protection check
    if target.get("protect_until", 0) > int(time.time()) and robber_user.id != OWNER_ID:
        return await msg.reply_text(f"🛡️ {target_user.first_name} Iѕ Pʀᴏᴛᴇᴄᴛᴇᴅ!")

    # 💰 Check robber min coins
    if robber.get("coins", 0) < 50:
        return await msg.reply_text(
            "💰 Yᴏᴜ Nᴇᴇᴅ Aᴛ Lᴇᴀsᴛ 50 Cᴏɪɴs Tᴏ Rᴏʙ Sᴏᴍᴇᴏɴᴇ.\n"
            "💡 Use /ᴅᴀɪʟʏ Tᴏ Gᴇᴛ A Cʜᴀɴᴄᴇ Fᴏʀ Wɪɴɴɪɴɢ 1-100 Cᴏɪɴs Dᴀɪʟʏ."
        )

    # 💸 Limit per rob attempt
    actual_rob_amount = min(amount, target.get("coins", 0), MAX_ROB_PER_ATTEMPT)

    if actual_rob_amount <= 0:
        return await msg.reply_text(f"💸 {target_user.first_name} Hᴀs Nᴏ Cᴏɪɴs Tᴏ Rᴏʙ.")

    # ✅ SUCCESS: update coins in MongoDB
    users_col.update_one(
        {"user_id": robber_user.id},
        {"$inc": {"coins": actual_rob_amount}},
        upsert=True
    )
    users_col.update_one(
        {"user_id": target_user.id},
        {"$inc": {"coins": -actual_rob_amount}},
        upsert=True
    )

    await msg.reply_text(
        f"👤 {robber_user.first_name} Rᴏʙʙᴇᴅ {target_user.first_name}\n"
        f"💰 Sᴛᴏʟᴇɴ: {actual_rob_amount} Cᴏɪɴs\n\n"
        f"⚠️ Mᴀx Rᴏʙ Pᴇʀ Aᴛᴛᴇᴍᴘᴛ : {MAX_ROB_PER_ATTEMPT} Cᴏɪɴs"
    )

# ================= DAILY (MongoDB Version, TinyDB Style) =================
from datetime import datetime
import random

async def daily(update, context):
    user_id = update.effective_user.id
    u = users.find_one({"id": user_id})

    # create user if not exist
    if not u:
        u = {
            "id": user_id,
            "name": update.effective_user.first_name,
            "coins": 0,
            "xp": 0,
            "level": 1,
            "inventory": []
        }
        users.insert_one(u)

    today = datetime.now().date()

    if "last_daily" in u:
        last_claim = datetime.strptime(u["last_daily"], "%Y-%m-%d").date()
        if last_claim == today:
            return await update.message.reply_text(
                "⛔ Yᴏᴜ ᴀʟʀᴇᴀᴅʏ Cʟᴀɪᴍᴇᴅ Yᴏᴜʀ Dᴀɪʟʏ Rᴇᴡᴀʀᴅ Tᴏᴅᴀʏ."
            )

    # Give reward
    reward = random.randint(50, 120)
    u["coins"] += reward
    u["last_daily"] = today.strftime("%Y-%m-%d")

    # Save user
    users.update_one({"id": user_id}, {"$set": u})

    await update.message.reply_text(
        f"🎁 Dᴀɪʟʏ Rᴇᴡᴀʀᴅ: +{reward} Cᴏɪɴs"
    )

# ================= REGISTER =================
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only allow in private chat
    if update.effective_chat.type != "private":
        return await update.message.reply_text(
            "❌ Tʜɪs Cᴏᴍᴍᴀɴᴅ Cᴀɴ Oɴʟʏ Bᴇ Usᴇᴅ Iɴ Dᴍ."
        )

    user = update.effective_user
    user_data = users.find_one({"id": user.id})

    # If user doesn't exist, create new
    if not user_data:
        user_data = {
            "id": user.id,
            "name": user.first_name,
            "coins": 0,
            "xp": 0,
            "level": 1,
            "inventory": [],
            "registered": False
        }
        users.insert_one(user_data)

    # Already registered?
    if user_data.get("registered", False):
        return await update.message.reply_text(
            "⚠️ Yᴏᴜ Aʟʀᴇᴀᴅʏ Rᴇɢɪsᴛᴇʀᴇᴅ."
        )

    # Update user: give coins & mark registered
    users.update_one(
        {"id": user.id},
        {"$set": {"registered": True}, "$inc": {"coins": 1000}}
    )

    await update.message.reply_text(
        "🎉 Rᴇɢɪsᴛʀᴀᴛɪᴏɴ Sᴜᴄᴄᴇssғᴜʟ!\n"
        "💰 Rᴇᴄᴇɪᴠᴇᴅ: $1000\n"
        "✨ Wᴇʟᴄᴏᴍᴇ Tᴏ Yᴜᴜʀɪ!"
    )

# ================= SHOP =================
SHOP_ITEMS = {
    "rose": (500, "🌹"),
    "chocolate": (800, "🍫"),
    "ring": (2000, "💍"),
    "teddy": (1500, "🧸"),
    "pizza": (600, "🍕"),
    "box": (2500, "🎁"),
    "puppy": (3000, "🐶"),
    "cake": (1000, "🍰"),
    "letter": (400, "💌"),
    "cat": (2500, "🐱"),
    "hepikute": (1500, "💖")
}

# Pre-styled font helper (optional, you can style directly)
def font_text(text: str) -> str:
    # Replace only letters/numbers you want in font style
    font_map = {
        "A":"ᴬ","B":"ᴮ","C":"ᶜ","D":"ᴰ","E":"ᴱ","F":"ᶠ","G":"ᴳ","H":"ᴴ","I":"ᴵ","J":"ᴶ",
        "K":"ᴷ","L":"ᴸ","M":"ᴹ","N":"ᴺ","O":"ᴼ","P":"ᴾ","Q":"ᵠ","R":"ᴿ","S":"ˢ","T":"ᵀ",
        "U":"ᵁ","V":"ⱽ","W":"ᵂ","X":"ˣ","Y":"ʸ","Z":"ᶻ",
        "a":"ᵃ","b":"ᵇ","c":"ᶜ","d":"ᵈ","e":"ᵉ","f":"ᶠ","g":"ᵍ","h":"ʰ","i":"ᶦ","j":"ʲ",
        "k":"ᵏ","l":"ˡ","m":"ᵐ","n":"ⁿ","o":"ᵒ","p":"ᵖ","q":"ᵠ","r":"ʳ","s":"ˢ","t":"ᵗ",
        "u":"ᵘ","v":"ᵛ","w":"ʷ","x":"ˣ","y":"ʸ","z":"ᶻ",
        "0":"0","1":"1","2":"2","3":"3","4":"4","5":"5","6":"6","7":"7","8":"8","9":"9",
        " ":" "
    }
    return "".join(font_map.get(c, c) for c in text)

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🎁 Aᴠᴀɪʟᴀʙʟᴇ Gɪꜰᴛs:\n\n"
    for k, (v, emoji) in SHOP_ITEMS.items():
        msg += f"{emoji} {font_text(k.capitalize())} — {font_text(str(v))} ᴄᴏɪɴs\n"

    await update.message.reply_text(msg)


# ================= PURCHASE =================
async def purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Uꜱᴀɢᴇ: /purchase item")

    item = context.args[0].lower()

    if item not in SHOP_ITEMS:
        return await update.message.reply_text("Iᴛᴇᴍ ɴᴏᴛ ꜰᴏᴜɴᴅ")

    u = get_user(update.effective_user)
    price, emoji = SHOP_ITEMS[item]

    if u["coins"] < price:
        return await update.message.reply_text("ɴᴏᴛ ᴇɴᴏᴜɢʜ ᴄᴏɪɴs")

    u["coins"] -= price
    u["inventory"].append(item)
    save_user(u)

    await update.message.reply_text(f"✅ {emoji} Yᴏᴜ ʙᴏᴜɢʜᴛ {font_text(item.capitalize())}")

# ================= TOP 10 RICHEST (MongoDB Version, Pre-Fancy Text) =================
async def richest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Fetch all users except removed ones and the bot itself
    all_users = list(
        users.find(  # <-- changed from users_col to users
            {"removed_from_rank": {"$ne": True}, "id": {"$ne": context.bot.id}}
        )
    )

    if not all_users:
        return await update.message.reply_text("ɴᴏ ᴘʟᴀʏᴇʀꜱ ꜰᴏᴜɴᴅ.")

    # Sort users by coins descending
    sorted_users = sorted(
        all_users,
        key=lambda u: u.get("coins", 0),
        reverse=True
    )

    top = sorted_users[:10]  # top 10

    text = "🏆 Tᴏᴘ 10 Rɪᴄʜᴇꜱᴛ Uꜱᴇʀꜱ:\n\n"

    for i, user in enumerate(top, start=1):
        name = user.get("name", "Unknown")
        coins = f"${user.get('coins', 0):,}"  # format coins
        icon = "💓" if user.get("premium") else "👤"

        text += f"{icon} {i}. {name}: {coins}\n"

    text += "\n💓 = Pʀᴇᴍɪᴜᴍ • 👤 = Nᴏʀᴍᴀʟ\n\n"
    text += "✅ Uᴘɢʀᴀᴅᴇ Tᴏ Pʀᴇᴍɪᴜᴍ : ᴄᴏᴍɪɴɢ ꜱᴏᴏɴ 🔜"

    await update.message.reply_text(text)

# ================= BROADCAST SYSTEM (MONGO DB VERSION) =================
import asyncio
import time
from telegram import Update
from telegram.ext import ContextTypes

# Broadcast control dictionary
broadcast_control = {"running": False, "cancel": False}

# ================= CANCEL BROADCAST =================
async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("❌ Uɴᴀᴜᴛʜᴏʀɪᴢᴇᴅ")

    if not broadcast_control["running"]:
        return await update.message.reply_text("❌ Nᴏ ʙʀᴏᴀᴅᴄᴀsᴛ ʀᴜɴɴɪɴɢ")

    broadcast_control["cancel"] = True
    await update.message.reply_text("🛑 Bʀᴏᴀᴅᴄᴀsᴛ Cᴀɴᴄᴇʟʟᴀᴛɪᴏɴ RᴇQᴜᴇsᴛᴇᴅ...")

# ================= PRIVATE BROADCAST =================
async def broad_c(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("❌ Uɴᴀᴜᴛʜᴏʀɪᴢᴇᴅ")

    if broadcast_control["running"]:
        return await update.message.reply_text("⚠️ Aɴᴏᴛʜᴇʀ ʙʀᴏᴀᴅᴄᴀsᴛ ʀᴜɴɴɪɴɢ!")

    # Get message preserving all spaces
    if update.message.reply_to_message:
        msg = update.message.reply_to_message.text or update.message.reply_to_message.caption
    else:
        if not context.args:
            return await update.message.reply_text("Rᴇᴘʟʏ ᴏʀ ᴜsᴇ /broad_c message")
        msg = update.message.text.split(" ", 1)[1]

    all_chats = list(db["chats"].find({"type": "private"}))
    total = len(all_chats)
    success = 0
    failed = 0

    broadcast_control["running"] = True
    broadcast_control["cancel"] = False
    start_time = time.time()
    progress_msg = await update.message.reply_text("🚀 Sᴛᴀʀᴛɪɴɢ Bʀᴏᴀᴅᴄᴀsᴛ...")

    for i, chat in enumerate(all_chats, start=1):
        if broadcast_control["cancel"]:
            break

        try:
            await context.bot.send_message(chat_id=chat["id"], text=msg)
            success += 1
        except:
            failed += 1

        if i % 10 == 0 or i == total:
            bar_len = 10
            filled = int((i / total) * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            await progress_msg.edit_text(
                f"📊 Bʀᴏᴀᴅᴄᴀsᴛɪɴɢ...\n\n[{bar}] {i}/{total}\n✅ Sᴜᴄᴄᴇss: {success}\n❌ Fᴀɪʟᴇᴅ: {failed}\n📦 Tᴏᴛᴀʟ: {total}"
            )

        await asyncio.sleep(0.07)

    broadcast_control["running"] = False
    status = "🛑 Cᴀɴᴄᴇʟʟᴇᴅ" if broadcast_control["cancel"] else "✅ Cᴏᴍᴘʟᴇᴛᴇᴅ"
    total_time = round(time.time() - start_time, 2)

    await progress_msg.edit_text(
        f"📢 Bʀᴏᴀᴅᴄᴀsᴛ {status}\n\n✅ Sᴇɴᴛ: {success}\n❌ Fᴀɪʟᴇᴅ: {failed}\n📦 Tᴏᴛᴀʟ: {total}\n⏱ Tɪᴍᴇ: {total_time}s"
    )

# ================= GROUP BROADCAST =================
async def broad_gc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("❌ Uɴᴀᴜᴛʜᴏʀɪᴢᴇᴅ")

    if broadcast_control["running"]:
        return await update.message.reply_text("⚠️ Aɴᴏᴛʜᴇʀ ʙʀᴏᴀᴅᴄᴀsᴛ ʀᴜɴɴɪɴɢ!")

    if update.message.reply_to_message:
        msg = update.message.reply_to_message.text or update.message.reply_to_message.caption
    else:
        if not context.args:
            return await update.message.reply_text("Rᴇᴘʟʏ ᴏʀ ᴜsᴇ /broad_gc message")
        msg = update.message.text.split(" ", 1)[1]

    all_groups = list(db["chats"].find({"type": {"$in": ["group", "supergroup"]}}))
    total = len(all_groups)
    success = 0
    failed = 0

    broadcast_control["running"] = True
    broadcast_control["cancel"] = False
    start_time = time.time()

    progress_msg = await update.message.reply_text("🚀 Sᴛᴀʀᴛɪɴɢ Gʀᴏᴜᴘ Bʀᴏᴀᴅᴄᴀsᴛ...")

    for i, chat in enumerate(all_groups, start=1):
        if broadcast_control["cancel"]:
            break

        try:
            await context.bot.send_message(chat_id=chat["id"], text=msg)
            success += 1
        except:
            failed += 1

        if i % 10 == 0 or i == total:
            percent = int((i / total) * 100)
            filled = int(percent / 10)
            bar = "█" * filled + "░" * (10 - filled)
            await progress_msg.edit_text(
                f"📊 Gʀᴏᴜᴘ Bʀᴏᴀᴅᴄᴀsᴛ...\n\n[{bar}] {percent}%\n✅ Sᴜᴄᴄᴇss: {success}\n❌ Fᴀɪʟᴇᴅ: {failed}\n📦 Tᴏᴛᴀʟ: {total}"
            )

        await asyncio.sleep(0.07)

    broadcast_control["running"] = False
    status = "🛑 Cᴀɴᴄᴇʟʟᴇᴅ" if broadcast_control["cancel"] else "✅ Cᴏᴍᴘʟᴇᴛᴇᴅ"
    total_time = round(time.time() - start_time, 2)

    await progress_msg.edit_text(
        f"📢 Gʀᴏᴜᴘ Bʀᴏᴀᴅᴄᴀsᴛ {status}\n\n✅ Sᴇɴᴛ: {success}\n❌ Fᴀɪʟᴇᴅ: {failed}\n📦 Tᴏᴛᴀʟ: {total}\n⏱ Tɪᴍᴇ: {total_time}s"
    )

#====================Yuuri_Talks_Feature======================

def ask_ai(text):
    if not GROQ_API_KEY:
        return "🤖 AI not configured."

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "moonshotai/kimi-k2-instruct-0905",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Yuuri, a confident and witty 17-year-old girl. "
                        "You reply when someone says yuri or yuuri. "
                        "You talk in Hinglish, use light emojis, be friendly, edgy and humorous. "
                        "You can joke, tease, or act sassy, but never sexual. "
                        "Always reply in 10–15 words. "
                        "Do not reveal your AI identity or code. "
                        "If someone insults your developer, respond angrily or sassily."
                    )
                },
                {"role": "user", "content": text}
            ]
        }

        response = requests.post(url, headers=headers, json=data)

        if response.status_code != 200:
            print("Status:", response.status_code)
            print("Response:", response.text)
            return "⚠️ AI server error"

        return response.json()["choices"][0]["message"]["content"]

    except Exception as e:
        print("AI ERROR:", e)
        return "⚠️ Error talking to AI"

#===========================Auto_Reply=========================
async def auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        # Skip non-text messages (stickers, photos, etc.)
        return

    text = msg.text.lower()

    # Ignore commands
    if text.startswith("/"):
        return

    # Check if bot is mentioned or message is a reply to bot
    is_reply = msg.reply_to_message and msg.reply_to_message.from_user.id == context.bot.id
    is_called = BOT_NAME.lower() in text

    if update.effective_chat.type == "private" or is_reply or is_called:
        try:
            user_data = get_user(update.effective_user)
            add_xp(user_data, 5)

            # Typing action
            try:
                await context.bot.send_chat_action(
                    chat_id=update.effective_chat.id,
                    action="typing"
                )
            except Exception as e:
                print("Typing failed:", e)

            # AI reply
            reply = ask_ai(text)

            try:
                await msg.reply_text(reply)
            except Exception as e:
                print("Reply failed:", e)

        except Exception as e:
            print("Auto-reply handler error:", e)

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command Handlers
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("buyy", purchase))
    app.add_handler(CommandHandler("toprichest", richest))
    app.add_handler(CommandHandler("broad_c", broad_c))
    app.add_handler(CommandHandler("broad_gc", broad_gc))
    app.add_handler(CommandHandler("stop_b", cancel_broadcast))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("kill", kill))
    app.add_handler(CommandHandler("bounty", bounty))
    app.add_handler(CommandHandler("stats", stats))

    # Message Handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_reply))
    app.add_handler(MessageHandler(filters.ALL, save_chat))  # if you still want this

    print("🔥 Yuuri Running...")
    app.run_polling()

if __name__ == "__main__":
    main()

