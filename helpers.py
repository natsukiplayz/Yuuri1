#!/usr/bin/env python3
"""
Shared helper functions used across every module: user CRUD, premium
checks, small-caps / fancy fonts, rank tables, progress bars.
"""

import asyncio
from datetime import datetime, timezone
from telegram.ext import ContextTypes

from bot.config import users, groups_col

# ============================================================
#  USER SYSTEM
# ============================================================

DEFAULT_USER_FIELDS = {
    "coins": 100,
    "xp": 0,
    "level": 1,
    "kills": 0,
    "guild": None,
    "dead": False,
    "inventory": [],
    "claimed_groups": [],
    "blocked": False,
    "premium": False,
    "old_names": [],
}


def get_user(user):
    """Fetches (and lazily creates / migrates) a user document."""
    data = users.find_one({"id": user.id})

    default_data = {"id": user.id, "name": user.first_name, **DEFAULT_USER_FIELDS}

    if not data:
        users.insert_one(default_data)
        return default_data

    updated_fields = {}

    if data.get("name") != user.first_name:
        current_db_name = data.get("name")
        old_names_list = data.get("old_names", [])
        if current_db_name and current_db_name not in old_names_list:
            old_names_list.append(current_db_name)
            updated_fields["old_names"] = old_names_list
            data["old_names"] = old_names_list
        updated_fields["name"] = user.first_name
        data["name"] = user.first_name

    for key, value in default_data.items():
        if key not in data:
            updated_fields[key] = value
            data[key] = value

    if updated_fields:
        users.update_one({"id": user.id}, {"$set": updated_fields})

    return data


def save_user(data):
    if not data or "id" not in data:
        return
    users.update_one({"id": data["id"]}, {"$set": data}, upsert=True)


def is_premium(user_data, context=None):
    """Checks premium status; auto-expires + DMs the user if it lapsed."""
    if not user_data.get("premium"):
        return False

    expire_str = user_data.get("premium_until")
    if not expire_str:
        return False

    try:
        expire_time = datetime.strptime(expire_str, "%Y-%m-%d %H:%M:%S")

        if datetime.now(timezone.utc).replace(tzinfo=None) > expire_time:
            user_id = user_data.get("id")
            users.update_one(
                {"id": user_id},
                {"$set": {"premium": False}, "$unset": {"premium_until": "", "membership_type": ""}}
            )
            if context:
                msg = "⌛ <b>Yᴏᴜʀ Pʀᴇᴍɪᴜᴍ Hᴀs Exᴘɪʀᴇᴅ!</b>\n\nTᴏ rᴇɴᴇᴡ, use /pay."
                asyncio.create_task(
                    context.bot.send_message(chat_id=user_id, text=msg, parse_mode='HTML')
                )
            return False
        return True
    except Exception:
        return False


def get_user_icon(user_data, context):
    if is_premium(user_data, context):
        return user_data.get("custom_icon", "💓")
    return "👤"


async def is_economy_disabled(chat_id: int) -> bool:
    group_data = await groups_col.find_one({"chat_id": chat_id})
    return bool(group_data and group_data.get("economy_closed") is True)


# ============================================================
#  XP / LEVEL SYSTEM
# ============================================================

def add_xp(user_data, amount):
    user_data["xp"] += amount
    leveled_up = False
    while True:
        need = int(100 * (1.5 ** (user_data["level"] - 1)))
        if user_data["xp"] >= need:
            user_data["xp"] -= need
            user_data["level"] += 1
            leveled_up = True
        else:
            break
    save_user(user_data)
    return leveled_up


RANKS = [
    {"name": "Nᴏᴏʙ", "lvl": 1},
    {"name": "Bᴇɢɪɴɴᴇʀ", "lvl": 5},
    {"name": "Fɪɢʜᴛᴇʀ", "lvl": 10},
    {"name": "Wᴀʀʀɪᴏʀ", "lvl": 20},
    {"name": "Eʟɪᴛᴇ", "lvl": 35},
    {"name": "Mᴀsᴛᴇʀ", "lvl": 55},
    {"name": "Lᴇɢᴇɴᴅ", "lvl": 80},
    {"name": "Mʏᴛʜɪᴄ", "lvl": 110},
    {"name": "Iᴍᴍᴏʀᴛᴀʟ", "lvl": 150},
]


def get_rank_data(level):
    current_rank = RANKS[0]
    next_rank = None
    for i, rank in enumerate(RANKS):
        if level >= rank["lvl"]:
            current_rank = rank
            if i + 1 < len(RANKS):
                next_rank = RANKS[i + 1]
        else:
            break
    return current_rank, next_rank


def create_progress_bar(percent):
    bars = 10
    percent = min(max(percent, 0), 100)
    filled = int(bars * percent / 100)
    empty = bars - filled
    bar = "█" * filled + "░" * empty
    return f"{bar} {percent}%"


# ============================================================
#  SMALL CAPS / FONTS
# ============================================================

SC_MAP = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ', 'h': 'ʜ',
    'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ',
    'q': 'ǫ', 'r': 'ʀ', 's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x',
    'y': 'ʏ', 'z': 'ᴢ',
}


def sc(text: str) -> str:
    """Small-caps helper used by card/heist/roulette game text."""
    return ''.join(SC_MAP.get(c, c) for c in text.lower())


SMALL_CAPS = SC_MAP

BOLD_SERIF = {
    "a": "𝐚", "b": "𝐛", "c": "𝐜", "d": "𝐝", "e": "𝐞", "f": "𝐟", "g": "𝐠", "h": "𝐡",
    "i": "𝐢", "j": "𝐣", "k": "𝐤", "l": "𝐥", "m": "𝐦", "n": "𝐧", "o": "𝐨", "p": "𝐩",
    "q": "𝐪", "r": "𝐫", "s": "𝐬", "t": "𝐭", "u": "𝐮", "v": "𝐯", "w": "𝐰", "x": "𝐱",
    "y": "𝐲", "z": "𝐳",
}


def get_fancy_text(text, font_type):
    """Used by /font command: font_type '1'=all small caps, '2'=title case
    small caps, '3'=bold first letter + small caps rest."""
    words = text.split(" ")
    final_output = []

    for word in words:
        if not word:
            final_output.append("")
            continue
        new_word = ""
        for i, char in enumerate(word):
            low_char = char.lower()
            if font_type == "1":
                new_word += SMALL_CAPS.get(low_char, char)
            elif font_type == "2":
                new_word += char.upper() if i == 0 else SMALL_CAPS.get(low_char, char)
            elif font_type == "3":
                new_word += BOLD_SERIF.get(low_char, char) if i == 0 else SMALL_CAPS.get(low_char, char)
            else:
                new_word += char
        final_output.append(new_word)

    return " ".join(final_output)


def font_text(text: str) -> str:
    """Alternate superscript-style font used by /shop."""
    font_map = {
        "A": "ᴬ", "B": "ᴮ", "C": "ᶜ", "D": "ᴰ", "E": "ᴱ", "F": "ᶠ", "G": "ᴳ", "H": "ᴴ",
        "I": "ᴵ", "J": "ᴶ", "K": "ᴷ", "L": "ᴸ", "M": "ᴹ", "N": "ᴺ", "O": "ᴼ", "P": "ᴾ",
        "Q": "ᵠ", "R": "ᴿ", "S": "ˢ", "T": "ᵀ", "U": "ᵁ", "V": "ⱽ", "W": "ᵂ", "X": "ˣ",
        "Y": "ʸ", "Z": "ᶻ",
        "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ", "g": "ᵍ", "h": "ʰ",
        "i": "ᶦ", "j": "ʲ", "k": "ᵏ", "l": "ˡ", "m": "ᵐ", "n": "ⁿ", "o": "ᵒ", "p": "ᵖ",
        "q": "ᵠ", "r": "ʳ", "s": "ˢ", "t": "ᵗ", "u": "ᵘ", "v": "ᵛ", "w": "ʷ", "x": "ˣ",
        "y": "ʸ", "z": "ᶻ",
        "0": "0", "1": "1", "2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "7",
        "8": "8", "9": "9", " ": " ",
    }
    return "".join(font_map.get(c, c) for c in text)


def get_leaderboard_icon(user_data, context):
    if is_premium(user_data, context):
        return user_data.get("custom_icon", "💓")
    return "👤"
