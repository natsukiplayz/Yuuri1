#!/usr/bin/env python3
"""Russian Roulette group game (/rullate, /join, /shot, /out, /rullrank)
and the Snake mini-game (Telegram WebApp + FastAPI endpoints)."""

import uuid
import random
import asyncio
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

from bot.config import users, async_db, users_async
from fastapi import Request

roulette_games: dict = {}

# ============================ ROULETTE ============================

async def rullate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    if not context.args:
        return await update.message.reply_text("❌ Uꜱᴀɢᴇ : /ʀᴜʟʟᴀᴛᴇ <ᴀᴍᴏᴜɴᴛ>")

    amount = int(context.args[0])
    user_data = users.find_one({"id": user.id})
    if not user_data:
        return await update.message.reply_text("❌ Uꜱᴇ /sᴛᴀʀᴛ ғɪʀsᴛ")
    if user_data["coins"] < amount:
        return await update.message.reply_text("💸 Nᴏᴛ ᴇɴᴏᴜɢʜ ᴄᴏɪɴs")
    if chat_id in roulette_games:
        return await update.message.reply_text("🎮 Gᴀᴍᴇ ᴀʟʀᴇᴀᴅʏ ʀᴜɴɴɪɴɢ")

    users.update_one({"id": user.id}, {"$inc": {"coins": -amount}})
    roulette_games[chat_id] = {
        "host": user.id, "bet": amount,
        "players": [{"id": user.id, "name": user.first_name}],
        "pot": amount, "started": False, "turn": 0
    }

    await update.message.reply_text(f"""
🎰 Rᴜssɪᴀɴ Rᴜʟʟᴇᴛᴇ Hᴏsᴛᴇᴅ

👤 Hᴏsᴛ : {user.first_name}
💰 Bᴇᴛ : {amount}

👉 Uꜱᴇ /ᴊᴏɪɴ

⏳ Sᴛᴀʀᴛs ɪɴ 2 ᴍɪɴ
Oʀ ᴜꜱᴇ /ᴏɴ
""")
    asyncio.create_task(auto_start(chat_id, context))


async def auto_start(chat_id, context):
    await asyncio.sleep(120)
    game = roulette_games.get(chat_id)
    if not game or game["started"]:
        return

    if len(game["players"]) < 2:
        host = game["players"][0]["id"]
        users.update_one({"id": host}, {"$inc": {"coins": game["bet"]}})
        await context.bot.send_message(chat_id, "❌ Nᴏ ᴏɴᴇ ᴊᴏɪɴᴇᴅ\n💰 Rᴇғᴜɴᴅᴇᴅ")
        del roulette_games[chat_id]
        return

    await start_game(chat_id, context)


async def on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = roulette_games.get(chat_id)
    if not game:
        return
    if user.id != game["host"]:
        return await update.message.reply_text("⛔ Oɴʟʏ Hᴏsᴛ")
    await start_game(chat_id, context)


async def start_game(chat_id, context):
    game = roulette_games[chat_id]
    game["started"] = True
    players = game["players"]
    count = len(players)

    chambers = 6 if count == 2 else (8 if count == 3 else 10)
    game["chambers"] = chambers
    game["bullet"] = random.randint(1, chambers)
    game["current"] = 1

    await context.bot.send_message(chat_id, f"""
🥳 Rᴜssɪᴀɴ Rᴜʟʟᴇᴛᴇ Sᴛᴀʀᴛᴇᴅ

🔫 Uꜱᴇ /sʜᴏᴛ ᴏɴ ʏᴏᴜʀ ᴛᴜʀɴ

💨 Eᴍᴘᴛʏ → Sᴀғᴇ  
💀 Bᴜʟʟᴇᴛ → Oᴜᴛ

👥 Pʟᴀʏᴇʀs : {len(players)}
🍯 Pᴏᴛ : {game['pot']}
🔄 Cʜᴀᴍʙᴇʀs : {chambers}
""")
    first = players[0]["name"]
    await context.bot.send_message(chat_id, f"🎯 Nᴏᴡ Tᴜʀɴ : {first}\n🔫 Uꜱᴇ /sʜᴏᴛ")


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    game = roulette_games.get(chat_id)

    if not game:
        return await update.message.reply_text("❌ Nᴏ Gᴀᴍᴇ")
    if game["started"]:
        return await update.message.reply_text("⛔ Gᴀᴍᴇ Sᴛᴀʀᴛᴇᴅ")

    bet = game["bet"]
    user_data = users.find_one({"id": user.id})
    if user_data["coins"] < bet:
        return await update.message.reply_text("💸 Nᴏᴛ ᴇɴᴏᴜɢʜ")

    for p in game["players"]:
        if p["id"] == user.id:
            return

    users.update_one({"id": user.id}, {"$inc": {"coins": -bet}})
    game["players"].append({"id": user.id, "name": user.first_name})
    game["pot"] += bet
    await update.message.reply_text(f"✅ {user.first_name} Jᴏɪɴᴇᴅ\n💰 Pᴏᴛ : {game['pot']}")


async def shot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = roulette_games.get(chat_id)

    if not game or not game["started"]:
        return

    players = game["players"]
    turn = game["turn"]
    current = players[turn]

    if current["id"] != user.id:
        return await update.message.reply_text("⏳ Nᴏᴛ Yᴏᴜʀ Tᴜʀɴ")

    msg = await update.message.reply_text("🔫 Cʟɪᴄᴋ... Cʟɪᴄᴋ...")
    await asyncio.sleep(2)

    if game["current"] == game["bullet"]:
        await msg.edit_text(f"""💥 Bᴏᴏᴍ!

💀 {user.first_name} ɪs Oᴜᴛ""")
        players.pop(turn)

        if len(players) == 1:
            winner = players[0]
            pot = game["pot"]
            xp_reward = random.randint(40, 80)
            users.update_one({"id": winner["id"]}, {"$inc": {"coins": pot, "xp": xp_reward, "roulette_won": 1}})

            photos = await context.bot.get_user_profile_photos(winner["id"], limit=1)
            caption = f"""
🎰 **Rᴜssɪᴀɴ Rᴜʟʟᴇᴛᴇ Rᴇsᴜʟᴛ**

━━━━━━━━━━━━━━━

🏆 **Wɪɴɴᴇʀ**
👤 [{winner['name']}](tg://user?id={winner['id']})

💰 **Pᴏᴛ Wᴏɴ**
`{pot}` ᴄᴏɪɴs

⭐ **XP Gᴀɪɴᴇᴅ**
`+{xp_reward}` XP

━━━━━━━━━━━━━━━
🎉 **Cᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏɴs!**
"""
            if photos.total_count > 0:
                file_id = photos.photos[0][0].file_id
                await context.bot.send_photo(chat_id, photo=file_id, caption=caption, parse_mode="Markdown")
            else:
                await context.bot.send_message(chat_id, caption, parse_mode="Markdown")

            del roulette_games[chat_id]
            return

        if turn >= len(players):
            game["turn"] = 0
    else:
        await msg.edit_text("😮‍💨 Sᴀғᴇ!")
        game["current"] += 1
        game["turn"] = (turn + 1) % len(players)

    next_player = players[game["turn"]]["name"]
    await context.bot.send_message(chat_id, f"""
🎯 Nᴇxᴛ Tᴜʀɴ : {next_player}

🔫 Uꜱᴇ /shot
""")


async def out(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    game = roulette_games.get(chat_id)
    if not game:
        return

    players = game["players"]
    for p in players:
        if p["id"] == user.id:
            players.remove(p)
            await update.message.reply_text(f"{user.first_name} Lᴇғᴛ Tʜᴇ Gᴀᴍᴇ")

            if len(players) == 1:
                winner = players[0]
                pot = game["pot"]
                xp_reward = random.randint(40, 80)
                users.update_one({"id": winner["id"]}, {"$inc": {"coins": pot, "xp": xp_reward, "roulette_won": 1}})
                await context.bot.send_message(chat_id, f"""
🏆 Rᴜssɪᴀɴ Rᴜʟʟᴇᴛᴇ Wɪɴɴᴇʀ

👤 {winner['name']}

💰 Wᴏɴ : {pot} ᴄᴏɪɴs
⭐ XP : +{xp_reward}
""")
                del roulette_games[chat_id]
            return


async def rullrank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_users = users.find().sort("roulette_won", -1).limit(10)
    text = "🏆 Rᴜssɪᴀɴ Rᴜʟʟᴇᴛᴇ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ\n\n"
    rank = 1
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    for user in top_users:
        name = user.get("name", "Pʟᴀʏᴇʀ")
        amount = user.get("roulette_won", 0)
        medal = medals.get(rank, "🔹")
        text += f"{medal} {rank}. {name} — `{amount}` Wɪɴꜱ\n"
        rank += 1

    if rank == 1:
        text += "Nᴏ Rᴏᴜʟᴇᴛᴛᴇ Wɪɴɴᴇʀs Yᴇᴛ."
    text += "\n\n🎰 Kᴇᴇᴘ Pʟᴀʏɪɴɢ & Wɪɴ Tʜᴇ Pᴏᴛ 🍯"
    await update.message.reply_text(text, parse_mode="Markdown")


# ============================ SNAKE (WebApp) ============================

ENTRY_FEE = 1000
MAX_PAYOUT = 10000
SNAKE_GAME_URL = "https://snake_event.oneapp.dev/"


async def cmd_snake(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    bot_username = context.bot.username

    if chat.type != "private":
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🎮 Pʟᴀʏ Sɴᴀᴋᴇ", url=f"https://t.me/{bot_username}?start=play_snake")
        ]])
        await update.message.reply_text(
            "<b>Cʟɪᴄᴋ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴘʟᴀʏ Sɴᴀᴋᴇ ɪɴ ᴍʏ DM!</b>",
            reply_markup=keyboard, parse_mode="HTML"
        )
        return

    user_doc = await users_async.find_one({"id": user.id})
    coins = user_doc.get("coins", 0) if user_doc else 0

    text = (
        f"🐍 <b>Sɴᴀᴋᴇ Aʀᴄᴀᴅᴇ</b>\n\n💰 Yᴏᴜʀ Cᴏɪɴs: <b>{coins}</b>\n🎟 Eɴᴛʀʏ Fᴇᴇ: <b>{ENTRY_FEE} coins</b>\n\n"
        "Eᴀʀɴ ᴄᴏɪɴs ʙᴀsᴇᴅ ᴏɴ ʏᴏᴜʀ sᴄᴏʀᴇ!\nHɪɢʜᴇʀ sᴄᴏʀᴇ = ᴍᴏʀᴇ ᴄᴏɪɴs ✨\n\n"
        "• Iᴍᴘᴏʀᴛᴀɴᴛ:-\n"
        "Wʜᴇɴᴇᴠᴇʀ Yᴏᴜ Sᴀᴡ Tʜᴇ 'Sᴀᴠɪɴɢ...' Tᴀᴋɪɴɢ Tᴏᴏ Lᴏɴɢ Sᴏ Jᴜꜱᴛ Pʀᴇꜱꜱ Eɴᴛᴇʀ Fʀᴏᴍ Yᴏᴜ Kᴇʏʙᴏᴀʀᴅ Iᴛ Wɪʟʟ Gɪᴠᴇ Yᴏᴜ Eᴀʀɴᴇᴅ Mᴏɴᴇʏ Aɴᴅ Sᴀᴠᴇ Cʜᴀɴɢᴇꜱ 👀❤️"
    )
    game_url = f"{SNAKE_GAME_URL}?user_id={user.id}&name={user.first_name[:8]}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🎮 Sᴛᴀʀᴛ Gᴀᴍᴇ", web_app=WebAppInfo(url=game_url))]])
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")


def register_snake_routes(app):
    """Call once from main.py with the FastAPI `app` instance."""

    @app.post("/snake/get_coins")
    async def snake_get_coins(request: Request):
        try:
            body = await request.json()
            user_id = int(body.get("user_id", 0))
            if not user_id:
                return {"ok": False, "error": "NO USER ID"}
            user_doc = await users_async.find_one({"id": user_id})
            if not user_doc:
                return {"ok": False, "error": "USER NOT FOUND"}
            return {"ok": True, "coins": user_doc.get("coins", 0)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.post("/snake/start_game")
    async def snake_start_game(request: Request):
        try:
            body = await request.json()
            user_id = int(body.get("user_id", 0))
            entry_fee = int(body.get("entry_fee", ENTRY_FEE))
            if not user_id:
                return {"ok": False, "error": "NO USER ID"}

            user_doc = await users_async.find_one({"id": user_id})
            if not user_doc:
                return {"ok": False, "error": "USER NOT FOUND"}

            coins = user_doc.get("coins", 0)
            if coins < entry_fee:
                return {"ok": False, "error": f"NOT ENOUGH COINS ({coins}/{entry_fee})"}

            session_id = str(uuid.uuid4())
            coins_after = coins - entry_fee

            await users_async.update_one(
                {"id": user_id},
                {"$set": {"coins": coins_after},
                 "$push": {"snake_sessions": {"session_id": session_id, "started_at": datetime.now(timezone.utc).isoformat(),
                                               "paid": True, "settled": False, "entry_fee": entry_fee}}}
            )
            return {"ok": True, "session_id": session_id, "coins_after": coins_after}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.post("/snake/end_game")
    async def snake_end_game(request: Request):
        try:
            body = await request.json()
            user_id = int(body.get("user_id", 0))
            session_id = body.get("session_id", "")
            score = int(body.get("score", 0))
            coins_earned = int(body.get("coins_earned", 0))
            name = str(body.get("name", "PLAYER"))[:8].upper()

            user_doc = await users_async.find_one({"id": user_id})
            if not user_doc:
                return {"ok": False, "error": "USER NOT FOUND"}

            sessions = user_doc.get("snake_sessions", [])
            session_obj = next((s for s in sessions if s.get("session_id") == session_id), None)
            if not session_obj or session_obj.get("settled"):
                return {"ok": False, "error": "INVALID OR SETTLED SESSION"}

            coins_earned = min(max(coins_earned, 0), MAX_PAYOUT)
            current_coins = user_doc.get("coins", 0)
            coins_after = current_coins + coins_earned

            await users_async.update_one(
                {"id": user_id, "snake_sessions.session_id": session_id},
                {"$set": {"coins": coins_after, "snake_sessions.$.settled": True, "snake_sessions.$.score": score,
                          "snake_sessions.$.coins_earned": coins_earned,
                          "snake_sessions.$.ended_at": datetime.now(timezone.utc).isoformat()}}
            )
            await async_db["snake_leaderboard"].update_one(
                {"user_id": user_id},
                {"$set": {"user_id": user_id, "name": name, "best_score": max(score, user_doc.get("snake_best", 0)),
                          "last_score": score, "coins_earned": coins_earned,
                          "date": datetime.now(timezone.utc).strftime("%b %d")}},
                upsert=True
            )
            if score > user_doc.get("snake_best", 0):
                await users_async.update_one({"id": user_id}, {"$set": {"snake_best": score}})

            return {"ok": True, "coins_after": coins_after, "coins_earned": coins_earned}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.get("/snake/leaderboard")
    async def snake_leaderboard():
        try:
            cursor = async_db["snake_leaderboard"].find({}, {"_id": 0}).sort("best_score", -1).limit(10)
            entries = await cursor.to_list(length=10)
            return [{"name": e.get("name", "???"), "score": e.get("best_score", 0),
                     "coins_earned": e.get("coins_earned", 0), "date": e.get("date", "")} for e in entries]
        except Exception:
            return []
