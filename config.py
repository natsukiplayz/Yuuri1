#!/usr/bin/env python3
"""
Central configuration for Yuuri Bot.

IMPORTANT: OWNER_ID is defined ONCE here. Every other file imports it
from this module (`from bot.config import OWNER_ID`). Never hardcode
the numeric ID anywhere else in the codebase — if you do, changing it
here won't propagate and you'll get the old bug back.
"""

import os
import logging
import dns.resolver
from datetime import datetime, timezone

from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
import cloudinary

# ================= TERMUX +srv DNS FIX =================
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ['8.8.8.8', '1.1.1.1']

# ================= CORE CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_NAME = "yuuri"
MONGO_URI = os.getenv("MONGO_URI")

# 🔒 SINGLE SOURCE OF TRUTH — change your owner id ONLY here.
OWNER_ID = 5773908061

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

RAW_GROQ_KEYS = os.getenv("GROQ_KEYS")
GROQ_KEYS = [k.strip() for k in RAW_GROQ_KEYS.split(",") if k.strip()] if RAW_GROQ_KEYS else []

PRIMARY_MODEL = "llama-3.3-70b-versatile"
FALLBACK_MODEL = "mixtral-8x7b-32768"

BOT_START_TIME = datetime.now(timezone.utc)
BOT_USERNAME = "im_yuuribot"

# ================= CLOUDINARY =================
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "Dbunajbpk")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

# ================= DATABASE =================
sync_client = MongoClient(MONGO_URI)
db = sync_client["yuuri_db"]

async_client = AsyncIOMotorClient(MONGO_URI)
async_db = async_client["yuuri_db"]

# --- SYNC COLLECTIONS ---
users = db["users"]
users_collection = db["users"]
guilds = db["guilds"]
chat = db["chats"]
sticker_packs = db["sticker_packs"]
heists = db["heists"]
redeem_col = db["redeem_codes"]
admins_db = db["admins"]
torture_db = db["torture_registry"]
allowed_collection = db["allowed_users"]
groups_collection = db["saved_groups"]
referrals_db = db["referral_codes"]
feedback_db = db["feedbacks"]

# --- ASYNC COLLECTIONS ---
image_db = async_db["command_images"]
users_col = async_db["users"]
groups_col = async_db["saved_groups"]
users_sync = db["users"]
users_async = async_db["users"]
settings_async = async_db["settings"]

logging.basicConfig(level=logging.INFO)

# ================= SAVED GROUPS CACHE =================
SAVED_GROUPS: dict = {}


def load_groups_from_db():
    global SAVED_GROUPS
    try:
        SAVED_GROUPS.clear()
        cursor = groups_collection.find({})
        for doc in cursor:
            pos_val = doc.get("pos")
            if pos_val is not None:
                pos = int(pos_val)
                SAVED_GROUPS[pos] = {"name": doc.get("name", "Unknown"), "url": doc.get("url", "")}
        logging.info(f"✅ Loaded {len(SAVED_GROUPS)} groups.")
    except Exception as e:
        logging.error(f"❌ DB Load Error: {e}")


load_groups_from_db()
