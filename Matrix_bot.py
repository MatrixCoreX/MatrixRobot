import telebot
from telebot import types
from telebot.types import ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
from collections import defaultdict
import sqlite3
import feedparser
import schedule
import time
import threading
import json
import os
import random
import re
import html
from uuid import uuid4
import csv
from io import StringIO, BytesIO
import requests
from pathlib import Path

current_quiz = {}

# ---- rate limits ----
RATE_LIMIT_SECONDS = 2.0  # Minimum 1 second between clicks for same user
last_claim_click = {}     # {telegram_id: last_ts}
recent_claim_key = {}     # { (packet_id, telegram_id): ts } for preventing duplicate clicks
last_click_times = {}
last_chat_points_time = {}  # {telegram_id: last_timestamp} for chat points rate limiting (1 minute)

TEMP_SIGNIN_FILE = 'temp_signin_word.txt'
LOG_FILE = 'admin_actions.log'
MESSAGE_LOG_FILE = 'group_messages.log'

# Load configuration file (supports comments)
def load_json_with_comments(file_path):
    """Load JSON file with support for // and /* */ style comments"""
    import re
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove // comments (but not inside strings)
    lines = []
    in_string = False
    escape_next = False
    for line in content.split('\n'):
        new_line = []
        i = 0
        while i < len(line):
            char = line[i]
            if escape_next:
                new_line.append(char)
                escape_next = False
                i += 1
                continue
            if char == '\\':
                escape_next = True
                new_line.append(char)
                i += 1
                continue
            if char == '"':
                in_string = not in_string
                new_line.append(char)
                i += 1
                continue
            if not in_string and i < len(line) - 1 and line[i:i+2] == '//':
                # Found // comment outside string, skip rest of line
                break
            new_line.append(char)
            i += 1
        lines.append(''.join(new_line))
    
    content = '\n'.join(lines)
    
    # Remove /* */ comments (but not inside strings)
    result = []
    in_string = False
    escape_next = False
    i = 0
    while i < len(content):
        char = content[i]
        if escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue
        if char == '\\':
            escape_next = True
            result.append(char)
            i += 1
            continue
        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue
        if not in_string and i < len(content) - 1 and content[i:i+2] == '/*':
            # Found /* comment, skip until */
            i += 2
            while i < len(content) - 1:
                if content[i:i+2] == '*/':
                    i += 2
                    break
                i += 1
            continue
        result.append(char)
        i += 1
    
    return json.loads(''.join(result))

try:
    config = load_json_with_comments('config.jsonc')
except:
    # Fallback to standard JSON if comment parsing fails
    with open('config.jsonc', 'r', encoding='utf-8') as f:
        config = json.load(f)

BOT_TOKEN = config['BOT_TOKEN']
ADMIN_IDS = config['ADMIN_IDS']
ALLOWED_GROUP_ID = config['ALLOWED_GROUP_ID']
MIN_ACTIVE_POINTS = config.get('MIN_ACTIVE_POINTS', 10)

# Points configuration
SIGNIN_POINTS = config.get('SIGNIN_POINTS', 1)  # Points for daily sign-in
SIGNIN_BONUS_POINTS = config.get('SIGNIN_BONUS_POINTS', 2)  # Bonus points for 7 consecutive days sign-in
QUIZ_CORRECT_POINTS = config.get('QUIZ_CORRECT_POINTS', 1)  # Points for correct quiz answer
CHAT_POINTS = config.get('CHAT_POINTS', 0)  # Points for each chat message (0 to disable, includes admins)
INVITE_REWARD_POINTS = config.get('INVITE_REWARD_POINTS', 3)  # Points for inviter when invitee first joins group

# Price API configuration
PRICE_API_BASE_URL = config.get('PRICE_API_BASE_URL', 'https://api.binance.com/api/v3/ticker/price')  # Base URL for price API

# Scheduled tasks time configuration
NEWS_BROADCAST_TIME = config.get('NEWS_BROADCAST_TIME', '09:00')  # News broadcasting time (HH:MM format)
SIGNIN_WORD_TIME = config.get('SIGNIN_WORD_TIME', '09:05')  # Daily sign-in word selection time (HH:MM format)
PRICE_UPDATE_TIME = config.get('PRICE_UPDATE_TIME', '00:00')  # Daily price update time (HH:MM format)
PRICE_BROADCAST_INTERVAL_HOURS = config.get('PRICE_BROADCAST_INTERVAL_HOURS', 2)  # Price broadcast interval in hours

# Community general configuration
COMMUNITY_NAME = config.get('COMMUNITY_NAME', 'Blockchain Community')
COMMUNITY_GROUP_LINK = config.get('COMMUNITY_GROUP_LINK', 'https://t.me/your_community_group')
COMMUNITY_TWITTER_CN = config.get('COMMUNITY_TWITTER_CN', '')
COMMUNITY_TWITTER_EN = config.get('COMMUNITY_TWITTER_EN', '')
COMMUNITY_INTRO_LINK = config.get('COMMUNITY_INTRO_LINK', '')
COMMUNITY_TUTORIAL_LINK = config.get('COMMUNITY_TUTORIAL_LINK', '')
COMMUNITY_ACCOUNT_NAME = config.get('COMMUNITY_ACCOUNT_NAME', 'Community Account')  # Display name for account binding
COMMUNITY_BOT_NAME = config.get('COMMUNITY_BOT_NAME', f'{COMMUNITY_NAME}_bot')  # Bot name
DEFAULT_LANGUAGE = config.get('DEFAULT_LANGUAGE', 'zh_CN')  # Default language: zh_CN or en_US
NEWS_ENABLED = config.get('NEWS_ENABLED', False)  # Enable news broadcasting feature
SIGNIN_WORD_ENABLED = config.get('SIGNIN_WORD_ENABLED', True)  # Enable daily sign-in word feature
PRICE_BROADCAST_ENABLED = config.get('PRICE_BROADCAST_ENABLED', True)  # Enable price broadcasting feature

# Load multilingual configuration
LOCALES_FILE = 'locales.json'
locales = {}

bot = telebot.TeleBot(BOT_TOKEN)

# Multilingual support function
def get_text(key_path, lang=None, default=None, **kwargs):
    """
    Get translated text
    :param key_path: Text key path, e.g. 'welcome.title' or ['welcome', 'title']
    :param lang: Language code, defaults to DEFAULT_LANGUAGE
    :param default: Default value if translation key not found
    :param kwargs: Formatting parameters
    :return: Translated text
    """
    if lang is None:
        lang = DEFAULT_LANGUAGE
    
    # Fallback to Chinese if language not found
    if lang not in locales:
        lang = 'zh_CN'
    
    if lang not in locales:
        return default if default is not None else key_path
    
    text_dict = locales[lang]
    
    # Support both string path and list path
    if isinstance(key_path, str):
        keys = key_path.split('.')
    else:
        keys = key_path
    
    # Navigate through nested dictionaries
    for key in keys:
        if isinstance(text_dict, dict) and key in text_dict:
            text_dict = text_dict[key]
        else:
            # Fallback to Chinese if not found
            if lang != 'zh_CN' and 'zh_CN' in locales:
                return get_text(key_path, 'zh_CN', default=default, **kwargs)
            return default if default is not None else key_path
    
    # Format text
    if isinstance(text_dict, str) and kwargs:
        try:
            return text_dict.format(**kwargs)
        except:
            return text_dict
    
    return text_dict if isinstance(text_dict, str) else (default if default is not None else key_path)

# Get user language (can be extended based on user preferences, currently uses default language)
def get_user_lang(telegram_id=None):
    """Get user language, currently returns default language"""
    return DEFAULT_LANGUAGE

# Get log text (uses DEFAULT_LANGUAGE from config)
def get_log_text(key_path, lang=None, default=None, **kwargs):
    """
    Get translated log text, uses DEFAULT_LANGUAGE from config
    :param key_path: Text key path, e.g. 'logs.signin_success'
    :param lang: Language code, defaults to DEFAULT_LANGUAGE from config
    :param default: Default value if translation key not found
    :param kwargs: Formatting parameters
    :return: Translated log text
    """
    if lang is None:
        lang = DEFAULT_LANGUAGE
    return get_text(key_path, lang=lang, default=default, **kwargs)

# Load locales after get_text is defined
try:
    with open(LOCALES_FILE, 'r', encoding='utf-8') as f:
        locales = json.load(f)
        print(get_log_text('logs.config_loaded_languages', count=len(locales)))
except Exception as e:
    print(get_log_text('logs.config_failed_load_locales', error=str(e)))
    locales = {}

print(get_log_text('logs.config_bot_token', token=BOT_TOKEN))
print(get_log_text('logs.config_admin_ids', ids=ADMIN_IDS))
print(get_log_text('logs.config_allowed_group_id', group_id=ALLOWED_GROUP_ID))
print(get_log_text('logs.config_community_name', name=COMMUNITY_NAME))
print(get_log_text('logs.config_default_language', lang=DEFAULT_LANGUAGE))
print(get_log_text('logs.config_news_broadcasting', status='Enabled' if NEWS_ENABLED else 'Disabled'))

# Valid sign-in words configuration file path
SIGNIN_WORDS_FILE = 'signin_words.txt'
current_signin_word = ""

# ===== Activity matching configuration =====
ACTIVITIES_FILE = "activities.json"
activities = []

def load_activities():
    global activities
    try:
        with open(ACTIVITIES_FILE, "r", encoding="utf-8") as f:
            activities = json.load(f)
            print(get_log_text('logs.activity_config_loaded', count=len(activities)))
    except Exception as e:
        print(get_log_text('logs.activity_config_failed', error=str(e)))
        activities = []

# Initialize database fields
conn = sqlite3.connect('telegram_bot.db')
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    last_signin TEXT,
    points INTEGER DEFAULT 0,
    binance_uid TEXT,
    twitter_handle TEXT,
    a_account TEXT,
    invited_by TEXT,
    joined_group INTEGER DEFAULT 0,
    name TEXT,
    custom_id TEXT,
    last_bonus_date TEXT,
    unlocked_points INTEGER DEFAULT 0
)
''')
conn.commit()

cursor.execute('''CREATE TABLE IF NOT EXISTS quiz_answers (
    quiz_id TEXT,
    telegram_id INTEGER,
    PRIMARY KEY (quiz_id, telegram_id)
)''')
conn.commit()

cursor.execute('''
CREATE TABLE IF NOT EXISTS signin_history (
    telegram_id INTEGER,
    date TEXT
)
''')
conn.commit()

cursor.execute('''
CREATE TABLE IF NOT EXISTS submissions (
    telegram_id INTEGER,
    type TEXT, 
    link TEXT,
    campaign_id TEXT,        
    PRIMARY KEY (telegram_id, campaign_id, type, link)
)
''')

conn.commit()

cursor.execute('''
        CREATE TABLE IF NOT EXISTS transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            recipient_id INTEGER,
            amount INTEGER,
            timestamp TEXT
        )
    ''')
conn.commit()

cursor.execute('''
CREATE TABLE IF NOT EXISTS red_packets (
    id TEXT PRIMARY KEY,
    sender_id INTEGER,
    total_points INTEGER,
    count INTEGER,
    created_at TEXT,
    remaining_points INTEGER,
    claimed_count INTEGER DEFAULT 0,
    expired INTEGER DEFAULT 0
)

    ''')
conn.commit()

cursor.execute('''
CREATE TABLE IF NOT EXISTS red_packet_claims (
    packet_id TEXT,
    telegram_id INTEGER,
    claimed_points INTEGER,
    PRIMARY KEY (packet_id, telegram_id)
)

    ''')
conn.commit()

cursor.execute('''
CREATE TABLE IF NOT EXISTS monthly_snapshot (
    telegram_id INTEGER,
    month TEXT,
    snapshot_points INTEGER,
    PRIMARY KEY (telegram_id, month)
)

    ''')
conn.commit()

cursor.execute('''
CREATE TABLE IF NOT EXISTS monthly_points (
    telegram_id INTEGER,
    month TEXT,                 -- Format: '2025-08'
    earned INTEGER DEFAULT 0,
    PRIMARY KEY (telegram_id, month)
)
''')

conn.commit()

cursor.execute('''
CREATE TABLE IF NOT EXISTS points_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
)
''')
conn.commit()

conn.close()

def clean_name(name: str) -> str:
    if not name:
        return ""
    # Remove control characters and bidirectional formatting characters
    name = re.sub(r"[\u200B-\u200F\u202A-\u202E\u2060-\u206F]", "", name)
    # Remove Arabic and related combining symbols
    name = re.sub(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]", "", name)
    # Remove extra spaces
    return name.strip()

# --------- FAQ Display Module (Display only: Category -> Question -> Answer) ---------

FAQ_JSON_PATH = Path("faq.json")  # Same directory as script, or use absolute path
faq_data = {"categories": []}

def load_faq():
    global faq_data
    try:
        with open(FAQ_JSON_PATH, "r", encoding="utf-8") as f:
            faq_data = json.load(f)
            print(get_log_text('logs.faq_loaded', count=len(faq_data.get('categories', []))))
    except Exception as e:
        print(get_log_text('logs.faq_load_error', error=str(e)))
        faq_data = {"categories": []}

# Load once on program startup
load_faq()

# /faq Display all categories (main title)
@bot.message_handler(commands=['faq'])
def cmd_faq(message):

    if message.chat.type != 'private' and message.chat.id != ALLOWED_GROUP_ID:
        return

    cats = faq_data.get("categories", [])
    lang = get_user_lang(message.from_user.id)
    if not cats:
        bot.reply_to(message, get_text('faq.empty', lang))
        return
    kb = types.InlineKeyboardMarkup(row_width=2)
    for c in cats:
        kb.add(types.InlineKeyboardButton(c["title"], callback_data=f"faq:cat:{c['id']}"))
    bot.send_message(message.chat.id, get_text('faq.select_category', lang), reply_markup=kb)

# Callback handling: Category -> Question list, Question -> Answer, Return operations
@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("faq:"))
def callback_faq(call):
    parts = call.data.split(":")
    try:
        action = parts[1] if len(parts) > 1 else None

        # Click category: faq:cat:<cat_id>
        if action == "cat" and len(parts) == 3:
            cat_id = parts[2]
            cat = next((c for c in faq_data.get("categories", []) if c["id"] == cat_id), None)
            lang = get_user_lang(call.from_user.id)
            if not cat:
                bot.answer_callback_query(call.id, get_text('faq.category_not_found', lang))
                return
            kb = types.InlineKeyboardMarkup(row_width=1)
            for q in cat.get("questions", []):
                label = q.get("q", "")
                if len(label) > 50:
                    label = label[:47] + "..."
                kb.add(types.InlineKeyboardButton(label, callback_data=f"faq:q:{cat_id}:{q['id']}"))
            kb.add(types.InlineKeyboardButton(get_text('faq.back_categories', lang), callback_data="faq:back:cats"))
            try:
                bot.edit_message_text(chat_id=call.message.chat.id,
                                      message_id=call.message.message_id,
                                      text=get_text('faq.category_questions', lang, title=cat['title']),
                                      parse_mode='Markdown',
                                      reply_markup=kb)
            except Exception:
                bot.send_message(call.message.chat.id, get_text('faq.category_questions', lang, title=cat['title']), parse_mode='Markdown', reply_markup=kb)
            bot.answer_callback_query(call.id)
            return

        # Click question: faq:q:<cat_id>:<q_id>
        if action == "q" and len(parts) == 4:
            cat_id, q_id = parts[2], parts[3]
            lang = get_user_lang(call.from_user.id)
            cat = next((c for c in faq_data.get("categories", []) if c["id"] == cat_id), None)
            if not cat:
                bot.answer_callback_query(call.id, get_text('faq.category_not_found', lang))
                return
            qobj = next((qq for qq in cat.get("questions", []) if qq["id"] == q_id), None)
            if not qobj:
                bot.answer_callback_query(call.id, get_text('faq.question_not_found', lang))
                return
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(types.InlineKeyboardButton(get_text('faq.back_questions', lang), callback_data=f"faq:cat:{cat_id}"))
            kb.add(types.InlineKeyboardButton(get_text('faq.back_all_categories', lang), callback_data="faq:back:cats"))
            text = f"*{qobj.get('q','')}*\n\n{qobj.get('a','')}"
            try:
                bot.edit_message_text(chat_id=call.message.chat.id,
                                      message_id=call.message.message_id,
                                      text=text,
                                      parse_mode='Markdown',
                                      reply_markup=kb)
            except Exception:
                bot.send_message(call.message.chat.id, text, parse_mode='Markdown', reply_markup=kb)
            bot.answer_callback_query(call.id)
            return

        # Return to category list: faq:back:cats
        if action == "back" and len(parts) == 3 and parts[2] == "cats":
            lang = get_user_lang(call.from_user.id)
            cats = faq_data.get("categories", [])
            if not cats:
                bot.answer_callback_query(call.id, get_text('faq.no_categories', lang))
                return
            kb = types.InlineKeyboardMarkup(row_width=2)
            for c in cats:
                kb.add(types.InlineKeyboardButton(c["title"], callback_data=f"faq:cat:{c['id']}"))
            try:
                bot.edit_message_text(chat_id=call.message.chat.id,
                                      message_id=call.message.message_id,
                                      text=get_text('faq.select_category', lang),
                                      reply_markup=kb)
            except Exception:
                bot.send_message(call.message.chat.id, get_text('faq.select_category', lang), reply_markup=kb)
            bot.answer_callback_query(call.id)
            return

        lang = get_user_lang(call.from_user.id)
        bot.answer_callback_query(call.id, get_text('faq.unknown_action', lang))
    except Exception as ex:
        print(get_log_text('logs.faq_callback_error', error=str(ex)))
        try:
            lang = get_user_lang(call.from_user.id)
            bot.answer_callback_query(call.id, get_text('faq.internal_error', lang))
        except:
            pass

# Admin command (optional): Reload JSON
@bot.message_handler(commands=['faq_reload'])
def cmd_faq_reload(message):
    if message.chat.type != 'private':
        lang = get_user_lang(message.from_user.id)
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return

    lang = get_user_lang(message.from_user.id)
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, get_text('common.no_permission', lang))
        return
    load_faq()
    bot.reply_to(message, get_text('faq.reload_success', lang, count=len(faq_data.get('categories', []))))
# --------- End of FAQ Display Module ---------

def add_monthly_points(telegram_id: int, delta: int):
    if delta <= 0:
        return  # Don't record negative numbers

    month_str = datetime.now().strftime('%Y-%m')
    conn = sqlite3.connect('telegram_bot.db')
    cur = conn.cursor()

    cur.execute('''
        INSERT INTO monthly_points (telegram_id, month, earned)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id, month)
        DO UPDATE SET earned = earned + excluded.earned
    ''', (telegram_id, month_str, delta))

    conn.commit()
    conn.close()

def log_transfer(sender_id, recipient_id, amount):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO transfers (sender_id, recipient_id, amount, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (sender_id, recipient_id, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


def record_signin_history(telegram_id, date_str):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO signin_history (telegram_id, date) VALUES (?, ?)", (telegram_id, date_str))
    conn.commit()
    conn.close()

def count_signins_last_7_days(telegram_id):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    seven_days_ago = (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d')  # Including today, 7 days total
    cursor.execute('''
        SELECT COUNT(DISTINCT date)
        FROM signin_history
        WHERE telegram_id = ? AND date >= ?
    ''', (telegram_id, seven_days_ago))
    count = cursor.fetchone()[0]
    conn.close()
    return count

# Sensitive word filtering
def load_sensitive_words(file_path='sensitive_words.txt'):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip().lower() for line in f if line.strip()]

# Database operation functions
def get_user(telegram_id):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user(telegram_id, field, value):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute(f'UPDATE users SET {field} = ? WHERE telegram_id = ?', (value, telegram_id))
    conn.commit()
    conn.close()

def update_user_name_and_custom_id(telegram_id, name, custom_id=None):
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET name = ?, custom_id = ? WHERE telegram_id = ?', (name, custom_id, telegram_id))
    conn.commit()
    conn.close()

def create_user_if_not_exist(telegram_id, invited_by=None, name=None):
    user = get_user(telegram_id)
    if not user:
        conn = sqlite3.connect('telegram_bot.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (telegram_id, points, invited_by, name, custom_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (telegram_id, 0, invited_by, name, None))
        conn.commit()
        conn.close()

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_members(message):
    if message.chat.id != ALLOWED_GROUP_ID:
        return  # Only send welcome message in specified group

    for new_member in message.new_chat_members:
        name = new_member.first_name or ""
        if new_member.last_name:
            name += " " + new_member.last_name

        # Use multilingual system
        lang = DEFAULT_LANGUAGE  # Can be adjusted based on user preference
        
        welcome_text = get_text('welcome.title', lang, name=name) + "\n"
        welcome_text += get_text('welcome.community_group', lang, name=COMMUNITY_NAME) + "\n"

        if COMMUNITY_TWITTER_CN:
            welcome_text += get_text('welcome.twitter_cn', lang, link=COMMUNITY_TWITTER_CN) + "\n"
        if COMMUNITY_TWITTER_EN:
            welcome_text += get_text('welcome.twitter_en', lang, link=COMMUNITY_TWITTER_EN) + "\n"
        if COMMUNITY_INTRO_LINK:
            welcome_text += get_text('welcome.intro_link', lang, link=COMMUNITY_INTRO_LINK) + "\n"

        welcome_text += f"\n{get_text('welcome.greeting', lang, name=COMMUNITY_NAME)}\n\n"
        welcome_text += get_text('welcome.bot_welcome', lang, bot_name=COMMUNITY_BOT_NAME) + "\n"
        welcome_text += get_text('welcome.points_system', lang, bot_name=COMMUNITY_BOT_NAME) + "\n\n"
        welcome_text += get_text('welcome.points_usage', lang) + "\n"
        welcome_text += get_text('welcome.points_usage_1', lang) + "\n"
        welcome_text += get_text('welcome.points_usage_2', lang) + "\n"
        welcome_text += get_text('welcome.points_usage_3', lang) + "\n\n"
        welcome_text += get_text('welcome.bot_guide', lang, bot_name=COMMUNITY_BOT_NAME) + "\n"

        welcome_text += get_text('welcome.guide_1', lang) + "\n"
        welcome_text += get_text('welcome.guide_2', lang) + "\n"
        welcome_text += get_text('welcome.guide_3', lang) + "\n"
        welcome_text += get_text('welcome.guide_4', lang) + "\n"
        welcome_text += get_text('welcome.guide_5', lang) + "\n"
        welcome_text += get_text('welcome.guide_6', lang) + "\n"
        welcome_text += get_text('welcome.guide_7', lang) + "\n"
        welcome_text += get_text('welcome.guide_8', lang) + "\n"

        if COMMUNITY_TUTORIAL_LINK:
            welcome_text += f"\n{get_text('welcome.tutorial_link', lang)}\n{COMMUNITY_TUTORIAL_LINK}\n"

        welcome_text += get_text('welcome.auto_delete', lang)
        try:
            sent_msg = bot.send_message(message.chat.id, welcome_text)
            # Delete welcome message after 60 seconds
            threading.Timer(60, lambda: safe_delete(message.chat.id, sent_msg.message_id, "Welcome message")).start()
        except Exception as e:
            print(get_log_text('logs.error_send_welcome', error=str(e)))

# Send red packet command
@bot.message_handler(commands=['hongbao','redpack'])
def send_red_packet(message):
    if message.chat.type not in ['group', 'supergroup']:
        return

    try:
        lang = get_user_lang(message.from_user.id)
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(message, get_text('redpacket.format_error', lang))
            return

        total_points = int(parts[1])
        count = int(parts[2])
        if total_points <= 0 or count <= 0:
            bot.reply_to(message, get_text('redpacket.positive_number', lang))
            return

        telegram_id = message.from_user.id
        conn = sqlite3.connect('telegram_bot.db')
        cursor = conn.cursor()

        cursor.execute("SELECT unlocked_points FROM users WHERE telegram_id = ?", (telegram_id,))
        result = cursor.fetchone()
        if not result or result[0] < total_points:
            bot.reply_to(message, get_text('redpacket.insufficient_points', lang))
            conn.close()
            return

        # Deduct unlocked points
        cursor.execute('''
            UPDATE users
            SET unlocked_points = unlocked_points - ?
            WHERE telegram_id = ?
        ''', (total_points, telegram_id))

        packet_id = str(uuid4())
        cursor.execute('''
            INSERT INTO red_packets (id, sender_id, total_points, count, created_at, remaining_points)
            VALUES (?, ?, ?, ?, datetime('now'), ?)
        ''', (packet_id, telegram_id, total_points, count, total_points))

        conn.commit()
        conn.close()

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(get_text('redpacket.claim_button', lang), callback_data=f"claim_{packet_id}"))

        name = message.from_user.first_name or ""
        if message.from_user.last_name:
          name += " " + message.from_user.last_name

        short_id = packet_id[:8]  # Use first 8 characters as red packet ID
        username = message.from_user.username or ""
        redpacket_msg = get_text('redpacket.sent', lang, name=name, username=username, id=telegram_id, count=count, points=total_points, short_id=short_id)
        bot.send_message(
             message.chat.id,
             redpacket_msg,
             reply_markup=markup
        )
        
        #bot.send_message(message.chat.id, f"🎉 {name} @{message.from_user.username} (ID:{telegram_id} ) 发了一个 {count} 份红包，共 {total_points} 积分！", reply_markup=markup)

    except Exception as e:
        print(get_log_text('logs.error_occurred', error=str(e)))


# Claim red packet
@bot.callback_query_handler(func=lambda call: call.data.startswith("claim_"))
def claim_red_packet(call):
    telegram_id = call.from_user.id
    packet_id = call.data.replace("claim_", "")

    now = time.time()

    # --- Rate limiting (once per second for same user) ---
    lang = get_user_lang(telegram_id)
    last_ts = last_claim_click.get(telegram_id, 0)
    if now - last_ts < RATE_LIMIT_SECONDS:
        bot.answer_callback_query(call.id, get_text('redpacket.click_too_fast', lang))
        return
    last_claim_click[telegram_id] = now

    conn = sqlite3.connect("telegram_bot.db")
    cursor = conn.cursor()

    # Check if already claimed
    cursor.execute("SELECT * FROM red_packet_claims WHERE packet_id = ? AND telegram_id = ?", (packet_id, telegram_id))
    if cursor.fetchone():
        bot.answer_callback_query(call.id, get_text('redpacket.already_claimed', lang))
        conn.close()
        return

    # Check red packet info
    cursor.execute("SELECT created_at, remaining_points, count, claimed_count, sender_id, expired FROM red_packets WHERE id = ?", (packet_id,))
    row = cursor.fetchone()
    if not row:
        bot.answer_callback_query(call.id, get_text('redpacket.not_found', lang))
        conn.close()
        return

    created_at_str, remaining_points, total_count, claimed_count, sender_id, expired = row
    created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")

    # Check expiration
    if expired or (datetime.now() - created_at > timedelta(hours=24)):
        bot.answer_callback_query(call.id, get_text('redpacket.expired', lang))
        conn.close()
        return

    if claimed_count >= total_count or remaining_points <= 0:
        bot.answer_callback_query(call.id, get_text('redpacket.empty', lang))
        conn.close()
        return

    remaining_count = total_count - claimed_count

    if remaining_count == 1:
        claim_amount = remaining_points
    else:
        avg = remaining_points / remaining_count
        max_possible = int(avg * 2)
        claim_amount = random.randint(1, min(max_possible, remaining_points - (remaining_count - 1)))


    # Update red packet table
    cursor.execute("UPDATE red_packets SET claimed_count = claimed_count + 1, remaining_points = remaining_points - ? WHERE id = ?", (claim_amount, packet_id))
    # Record claimer
    cursor.execute("INSERT INTO red_packet_claims (packet_id, telegram_id, claimed_points) VALUES (?, ?, ?)", (packet_id, telegram_id, claim_amount))
    # Increase unlocked points
    cursor.execute("UPDATE users SET unlocked_points = unlocked_points + ? WHERE telegram_id = ?", (claim_amount, telegram_id))

    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id)

    name = call.from_user.first_name or ""
    if call.from_user.last_name:
          name += " " + call.from_user.last_name

    username = call.from_user.username or "No username"

    short_id = packet_id[:8]
    bot.send_message(call.message.chat.id, get_text('redpacket.claimed', lang, name=name, username=username, id=telegram_id, short_id=short_id, amount=claim_amount))


    #bot.send_message(call.message.chat.id, f"🎉 {name}（@{username} | ID:{telegram_id}）抢到了 {claim_amount} 积分！")


@bot.message_handler(commands=['search_user'])
def handle_search_user(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, get_text('commands.no_permission', lang))
        return

    args = message.text.strip().split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, get_text('admin.search.format', lang))
        return

    keyword = args[1].strip().lower()

    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT telegram_id, name, custom_id, points, unlocked_points
        FROM users
        WHERE LOWER(name) LIKE ? OR LOWER(custom_id) LIKE ?
        ORDER BY points DESC
        LIMIT 20
    ''', (f'%{keyword}%', f'%{keyword}%'))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        bot.reply_to(message, get_text('admin.search.not_found', lang, keyword=keyword))
        return

    msg = get_text('admin.search.title', lang, keyword=keyword)
    for tid, name, cid, pts, unlocked in rows:
        name = name or get_text('common.unknown', lang)
        cid_display = f"@{cid}" if cid else get_text('common.not_found', lang)
        msg += get_text('admin.search.item', lang, name=name, cid=cid_display, id=tid, points=pts, unlocked=unlocked)

    bot.reply_to(message, msg, parse_mode="Markdown")


@bot.message_handler(commands=['help'])
def handle_help(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return  # Private chat only

    is_admin = message.from_user.id in ADMIN_IDS

    # Build help text using multilingual strings
    help_text = get_text('help.title', lang, name=COMMUNITY_NAME) + "\n\n"
    help_text += get_text('help.user_commands', lang) + "\n"
    help_text += f"- `/start`：{get_text('help.cmd_start', lang)}\n"
    help_text += f"- `/me`：{get_text('help.cmd_me', lang)}\n"
    help_text += f"- `/bind`：{get_text('help.cmd_bind', lang, name=COMMUNITY_ACCOUNT_NAME)}\n"
    help_text += f"- `/bind_binance <UID>`：{get_text('help.cmd_bind_binance', lang)}\n"
    help_text += f"- `/bind_twitter @handle`：{get_text('help.cmd_bind_twitter', lang)}\n"

    if COMMUNITY_ACCOUNT_NAME:
        address_label = get_text('common.address', lang)
        help_text += f"- `/bind_address <{address_label}>`：{get_text('help.cmd_bind_address', lang, name=COMMUNITY_ACCOUNT_NAME)}\n"

    help_text += f"- `/invites`：{get_text('help.cmd_invites', lang)}\n"
    help_text += f"- `/submit`：{get_text('help.cmd_submit', lang)}\n"
    help_text += f"- `/my_submissions`：{get_text('help.cmd_my_submissions', lang)}\n"
    symbol_label = get_text('common.symbol', lang)
    help_text += f"- `/price <{symbol_label}>`：{get_text('help.cmd_price', lang)}\n"
    content_label = get_text('common.content', lang)
    help_text += f"- `/feedback <{content_label}>`：{get_text('help.cmd_feedback', lang)}\n"
    amount_label = get_text('common.amount', lang)
    help_text += f"- `/unlock_points <{amount_label}>`：{get_text('help.cmd_unlock_points', lang)}\n"
    help_text += f"- `/transfer_points <ID> <{amount_label}>`：{get_text('help.cmd_transfer_points', lang)}\n"
    help_text += f"- `/recent_points`：{get_text('help.cmd_recent_points', lang)}\n"
    help_text += f"- `/transfer`：{get_text('help.cmd_transfer', lang)}\n"
    help_text += f"- `/faq`: {get_text('help.cmd_faq', lang)}\n\n"

    help_text += get_text('help.group_commands', lang) + "\n"
    help_text += f"- `/signinword`：{get_text('help.cmd_signinword', lang)}\n"
    help_text += f"- `/ranking`：{get_text('help.cmd_ranking', lang)}\n"
    help_text += f"- `/active`：{get_text('help.cmd_active', lang)}\n"
    help_text += f"- `/price` <{symbol_label}>：{get_text('help.cmd_price_group', lang)}\n"
    send_signin_label = get_text('common.send_signin', lang)
    help_text += f"- *{send_signin_label}*：{get_text('help.cmd_send_signin', lang)}\n"

    if is_admin:
        help_text += "\n" + get_text('help.admin_commands', lang) + "\n"
        help_text += f"- `/add_points <ID> <{amount_label}>`：{get_text('help.cmd_add_points', lang)}\n"
        help_text += f"- `/add_unlock_points <ID> <{amount_label}>`：{get_text('help.cmd_add_unlock_points', lang)}\n"
        upload_label = get_text('common.upload', lang, default='Upload')
        help_text += f"- {upload_label} `batch_points.csv`：{get_text('help.cmd_batch_points', lang)}\n"
        help_text += f"- {upload_label} `campaigns.json` : {get_text('help.cmd_upload_campaigns', lang)}\n"
        help_text += f"- {upload_label} `faq.json` : {get_text('help.cmd_upload_faq', lang)}\n"
        help_text += f"- {upload_label} `quiz_bank.json` : {get_text('help.cmd_upload_quiz', lang)}\n"
        help_text += f"- `/quiz_send {{json}}`：{get_text('help.cmd_quiz_send', lang)}\n"
        word_label = get_text('common.word', lang)
        help_text += f"- `/add_sensitive <{word_label}>`：{get_text('help.cmd_add_sensitive', lang)}\n"
        help_text += f"- `/export_users`：{get_text('help.cmd_export_users', lang)}\n"
        help_text += f"- `/export_submissions`：{get_text('help.cmd_export_submissions', lang)}\n"
        campaign_id_label = get_text('common.campaign_id', lang)
        help_text += f"- `/export_submissions_by_campaign <{campaign_id_label}>` ：{get_text('help.cmd_export_submissions_by_campaign', lang)}\n"
        help_text += f"- `/get_group_id`：{get_text('help.cmd_get_group_id', lang)}\n"
        help_text += f"- `/export_feedback`：{get_text('help.cmd_export_feedback', lang)}\n"
        help_text += f"- `/search_user`：{get_text('help.cmd_search_user', lang)}\n"
        amount_label = get_text('common.amount', lang)
        help_text += f"- `/draw <{amount_label}> 1001,1002,1003,1004` ：{get_text('help.cmd_draw', lang)}\n"
        help_text += f"- `/export_month_rank <YYYY-MM>`：{get_text('help.cmd_export_month_rank', lang)}\n"

    help_text += "\n" + get_text('help.feedback', lang)
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['export_feedback'])
def export_feedback_csv(message):
    if message.chat.type != 'private':
        lang = get_user_lang(message.from_user.id)
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return
    if message.from_user.id not in ADMIN_IDS:
        lang = get_user_lang(message.from_user.id)
        bot.reply_to(message, get_text('commands.admin_only', lang))
        return

    file_path = "feedback.csv"
    lang = get_user_lang(message.from_user.id)
    if not os.path.exists(file_path):
        bot.reply_to(message, get_text('feedback.empty_records', lang))
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Add UTF-8 BOM header to avoid Excel encoding issues
        byte_content = '\ufeff' + content
        byte_io = BytesIO(byte_content.encode("utf-8"))
        byte_io.seek(0)

        file_name = f"feedback_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        bot.send_document(message.chat.id, byte_io, visible_file_name=file_name, caption=get_text('feedback.export_success', lang))
        byte_io.close()

    except Exception as e:
        lang = get_user_lang(message.from_user.id)
        bot.reply_to(message, get_text('admin.export.error', lang, error=str(e)))



@bot.message_handler(commands=['feedback'])
def handle_feedback(message):
    lang = get_user_lang(message.from_user.id)
    text = message.text.strip()
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        bot.reply_to(message, get_text('feedback.format', lang))
        return

    content = parts[1].strip()
    if not content:
        bot.reply_to(message, get_text('feedback.empty', lang))
        return

    telegram_id = message.from_user.id
    name = message.from_user.first_name or ""
    if message.from_user.last_name:
        name += " " + message.from_user.last_name
    name = name.strip()

    custom_id = ""
    user = get_user(telegram_id)
    if user and len(user) >= 10 and user[9]:  # custom_id field
        custom_id = user[9]

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        with open("feedback.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if f.tell() == 0:
                writer.writerow(["Telegram ID", "Custom ID", "Name", "Content", "Time"])
            writer.writerow([telegram_id, custom_id, name, content, timestamp])

        bot.reply_to(message, get_text('feedback.success', lang))
    except Exception as e:
        bot.reply_to(message, get_text('feedback.error', lang, error=str(e)))


@bot.message_handler(commands=['add_points'])
def handle_add_points(message):
    lang = get_user_lang(message.from_user.id)
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, get_text('admin.add_points.no_permission', lang))
        return

    try:
        args = message.text.strip().split()
        if len(args) != 3:
            bot.reply_to(message, get_text('admin.add_points.format_error', lang, error=get_text('common.invalid_argument_count', lang)))
            return

        target_id = int(args[1])
        points_to_add = int(args[2])

        user = get_user(target_id)
        if not user:
            bot.reply_to(message, get_text('admin.add_points.user_not_found', lang, id=target_id))
            return

        new_points = user[2] + points_to_add
        update_user(target_id, 'points', new_points)
        add_monthly_points(target_id, points_to_add)

        with open(LOG_FILE, 'a', encoding='utf-8') as log_file:
            log_file.write(f"[{datetime.now()}] Admin {message.from_user.id} added {points_to_add} points for user {target_id}\n")

        # Notify user via private message
        try:
            bot.send_message(target_id, get_text('admin.add_points.reward_message', lang, points=points_to_add, total=new_points))
        except Exception as e:
            bot.reply_to(message, get_text('admin.add_points.success', lang, id=target_id, points=points_to_add, total=new_points) + " " + get_text('common.notification_failed', lang, error=str(e)))
            return

        bot.reply_to(message, get_text('admin.add_points.success', lang, id=target_id, points=points_to_add, total=new_points))

    except Exception as e:
        bot.reply_to(message, get_text('admin.add_points.format_error', lang, error=str(e)))

@bot.message_handler(commands=['add_unlock_points'])
def handle_add_unlock_points(message):
    lang = get_user_lang(message.from_user.id)
    telegram_id = message.from_user.id
    if telegram_id not in ADMIN_IDS:
        bot.reply_to(message, get_text('commands.admin_only', lang))
        return

    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(message, get_text('admin.add_unlock_points.format_error', lang))
            return

        target_id = int(parts[1])
        points = int(parts[2])
        if points <= 0:
            bot.reply_to(message, get_text('admin.add_unlock_points.positive', lang))
            return

        user = get_user(target_id)
        if not user:
            bot.reply_to(message, get_text('admin.add_unlock_points.user_not_found', lang))
            return

        new_points = (user[11] or 0) + points
        update_user(target_id, 'unlocked_points', new_points)

        # Notify via private message
        try:
            bot.send_message(
                target_id,
                get_text('admin.add_unlock_points.notification', lang, points=points, unlocked=new_points)
            )
        except Exception as e:
            bot.reply_to(message, get_text('admin.add_unlock_points.success', lang, id=target_id, points=points) + " " + get_text('common.notification_failed', lang, error=str(e)))

        bot.reply_to(message, get_text('admin.add_unlock_points.success', lang, id=target_id, points=points))

        # Log operation
        print(get_log_text('logs.admin_add_unlock_points', admin_id=telegram_id, points=points, target_id=target_id))

    except Exception as e:
        bot.reply_to(message, get_text('common.error', lang, default='❌ Error occurred') + f": {e}")

@bot.message_handler(content_types=['document'])
def handle_uploaded_documents(message):
    # Private chat & admin only
    if message.chat.type != 'private':
        return
    lang = get_user_lang(message.from_user.id)
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, get_text('commands.admin_only', lang))
        return

    file_name = (message.document.file_name or "").strip()
    print(get_log_text('logs.file_upload_received', file_name=file_name))

    if file_name == "batch_points.csv":
        return handle_batch_points_csv(message)      # Original batch points processing function
    elif file_name == "campaigns.json":
        return handle_campaigns_json(message)        # Campaign configuration processing function (with ID deduplication validation)
    elif file_name == "faq.json":
        return handle_faq_json(message)              # FAQ configuration file
    elif file_name == "quiz_bank.json":
        return handle_quiz_bank_json(message)        # Quiz bank processing
    else:
        bot.reply_to(message, get_text('admin.upload.unsupported', lang, file=file_name))

def handle_quiz_bank_json(message):
    lang = get_user_lang(message.from_user.id)
    try:
        file_info = bot.get_file(message.document.file_id)
        file_bytes = bot.download_file(file_info.file_path)

        with open("quiz_bank.json", "wb") as f:
            f.write(file_bytes)

        # Try to parse and validate
        try:
            quiz_list = json.loads(file_bytes.decode("utf-8"))
            if not isinstance(quiz_list, list):
                bot.reply_to(message, get_text('admin.upload.quiz_format_array', lang))
                return
            if not all("question" in q and "options" in q and "answer" in q for q in quiz_list):
                bot.reply_to(message, get_text('admin.upload.quiz_format_fields', lang))
                return
            preview = get_text('admin.upload.quiz_success', lang, count=len(quiz_list))
            if len(quiz_list) > 0:
                sample = quiz_list[0]
                preview += f"\nSample: {sample['question']} ({len(sample['options'])} options)"
            bot.reply_to(message, preview)
        except Exception as e:
            bot.reply_to(message, get_text('admin.upload.quiz_parse_error', lang, error=str(e)))
    except Exception as e:
        bot.reply_to(message, get_text('admin.upload.upload_error', lang, error=str(e)))


def handle_faq_json(message):
    lang = get_user_lang(message.from_user.id)
    try:
        file_info = bot.get_file(message.document.file_id)
        file_bytes = bot.download_file(file_info.file_path)

        with open("faq.json", "wb") as f:
            f.write(file_bytes)

        load_faq()
        bot.reply_to(message, get_text('faq.upload_success', lang, count=len(faq_data.get('categories', []))))
    except Exception as e:
        bot.reply_to(message, get_text('admin.upload.upload_error', lang, error=str(e)))

def handle_campaigns_json(message):
    lang = get_user_lang(message.from_user.id)
    try:
        # Get campaign_id used in database
        conn = sqlite3.connect('telegram_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT campaign_id FROM submissions WHERE campaign_id IS NOT NULL")
        used_ids = {str(row[0]) for row in cursor.fetchall()}
        conn.close()

        # Download uploaded file
        file_info = bot.get_file(message.document.file_id)
        file_bytes = bot.download_file(file_info.file_path)

        # Parse uploaded content
        try:
            new_list = json.loads(file_bytes.decode("utf-8"))
        except Exception as e:
            bot.reply_to(message, get_text('admin.upload.campaign_parse_error', lang, error=str(e)))
            return

        if not isinstance(new_list, list):
            bot.reply_to(message, get_text('admin.upload.campaign_format', lang))
            return

        # Collect new IDs and check field completeness
        new_ids = []
        for i, item in enumerate(new_list):
            cid = str(item.get("id", "")).strip()
            if not cid or not item.get("title") or not item.get("desc"):
                bot.reply_to(message, get_text('admin.upload.campaign_missing', lang, num=i+1))
                return
            new_ids.append(cid)

        # Check if there are duplicate IDs within new file
        dup_in_new = {x for x in new_ids if new_ids.count(x) > 1}
        if dup_in_new:
            ids_list = "\n".join(f"- {x}" for x in sorted(dup_in_new))
            bot.reply_to(message, get_text('admin.upload.campaign_duplicate', lang, ids=ids_list))
            return

        # Check if conflicts with IDs already used in database
        conflicts = used_ids.intersection(set(new_ids))
        if conflicts:
            ids_list = "\n".join(f"- {x}" for x in sorted(conflicts))
            bot.reply_to(message, get_text('admin.upload.campaign_conflict', lang, ids=ids_list))
            return

        # Write to campaigns.json
        with open("campaigns.json", "w", encoding="utf-8") as f:
            json.dump(new_list, f, ensure_ascii=False, indent=2)

        # Reply with preview content
        msg = get_text('admin.upload.campaign_success', lang)
        not_set = get_text('common.not_set', lang, default='Not set')
        for c in new_list:
            msg += f"📌 *{c.get('title')}* (`{c.get('id')}`)\n📝 {c.get('desc')}\n⏳ Deadline: {c.get('deadline', not_set)}\n\n"

        bot.reply_to(message, msg.strip(), parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, get_text('admin.upload.upload_error', lang, error=str(e)))

def handle_batch_points_csv(message):
    try:
        # Download file
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Save local file
        with open('batch_points.csv', 'wb') as f:
            f.write(downloaded_file)

        # Execute batch points addition
        success = 0
        failed = 0
        log_lines = []

        decoded = downloaded_file.decode('utf-8')
        reader = csv.reader(StringIO(decoded))
        for row in reader:
            try:
                telegram_id = int(row[0])
                points = int(row[1])
                user = get_user(telegram_id)
                if user:
                    new_points = user[2] + points

                    update_user(telegram_id, 'points', new_points)
                    add_monthly_points(telegram_id, points)

                    lang_user = DEFAULT_LANGUAGE  # Use default language for notification
                    bot.send_message(telegram_id, get_text('admin.batch.reward_message', lang_user, points=points, total=new_points))
                    time.sleep(2)
                    log_lines.append(f"[{datetime.now()}] Admin {message.from_user.id} added {points} points for user {telegram_id}")
                    success += 1
                else:
                    log_lines.append(f"[{datetime.now()}] ❌ User {telegram_id} does not exist")
                    failed += 1
            except Exception as e:
                failed += 1
                log_lines.append(f"[{datetime.now()}] ❌ Error processing row: {row}, Error: {e}")

        with open('add_points_log.txt', 'a', encoding='utf-8') as log_file:
            log_file.write("\n".join(log_lines) + "\n")

        lang = get_user_lang(message.from_user.id)
        bot.reply_to(message, get_text('admin.batch.success', lang, success=success, failed=failed))

    except Exception as e:
        lang = get_user_lang(message.from_user.id)
        bot.reply_to(message, get_text('admin.batch.error', lang, error=str(e)))


@bot.message_handler(commands=['price'])
def handle_price(message):
    lang = get_user_lang(message.from_user.id)
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            bot.reply_to(message, get_text('price.format', lang))
            return

        symbol = parts[1].upper()
        url = f"{PRICE_API_BASE_URL}?symbol={symbol}USDT"

        response = requests.get(url, timeout=5)
        data = response.json()
        print (data)
        if 'price' in data:
            price = float(data['price'])
            bot.reply_to(message, get_text('price.price_message', lang, symbol=symbol, price=price), parse_mode='Markdown')
        else:
            bot.reply_to(message, get_text('price.invalid', lang, symbol=symbol), parse_mode='Markdown')

    except Exception as e:
        bot.reply_to(message, get_text('price.error', lang, error=str(e)))

@bot.message_handler(commands=['export_submissions_by_campaign'])
def export_submissions_by_campaign(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(message, get_text('commands.private_only', lang))
        return
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, get_text('commands.admin_only', lang))
        return

    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            bot.reply_to(message, get_text('admin.export.format_error', lang))
            return

        campaign_id = parts[1]

        conn = sqlite3.connect('telegram_bot.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT telegram_id, type, link 
            FROM submissions
            WHERE campaign_id = ?
        ''', (campaign_id,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            bot.reply_to(message, get_text('admin.export.empty_submissions', lang, id=campaign_id), parse_mode="Markdown")
            return

        # Write CSV
        string_io = StringIO()
        writer = csv.writer(string_io)
        writer.writerow(["Telegram ID", "Type", "Link"])
        for row in rows:
            writer.writerow(row)

        byte_io = BytesIO(string_io.getvalue().encode('utf-8'))
        byte_io.seek(0)
        file_name = f"submissions_{campaign_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        bot.send_document(message.chat.id, byte_io, visible_file_name=file_name, caption=get_text('admin.export.export_success_submissions', lang, id=campaign_id))
        byte_io.close()

    except Exception as e:
        bot.reply_to(message, get_text('admin.export.error', lang, error=str(e)))



@bot.message_handler(commands=['export_submissions'])
def export_submissions_csv(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, get_text('commands.admin_only', lang))
        return

    try:
        conn = sqlite3.connect('telegram_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id, type, link FROM submissions")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            bot.reply_to(message, get_text('admin.export.empty_submissions_all', lang))
            return

        # Use StringIO to write text content, then encode to bytes
        string_io = StringIO()
        writer = csv.writer(string_io)
        writer.writerow(["Telegram ID", "Type", "Link"])
        for row in rows:
            writer.writerow(row)

        byte_io = BytesIO(string_io.getvalue().encode('utf-8'))
        byte_io.seek(0)

        file_name = f"submissions_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        bot.send_document(message.chat.id, byte_io, visible_file_name=file_name, caption=get_text('admin.export.export_success_all', lang))
        byte_io.close()

    except Exception as e:
        bot.reply_to(message, get_text('admin.export.error', lang, error=str(e)))

@bot.message_handler(commands=['export_users'])
def export_users_csv(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, get_text('commands.admin_only', lang))
        return

    try:
        conn = sqlite3.connect('telegram_bot.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                telegram_id, last_signin, points, binance_uid, twitter_handle, 
                a_account, invited_by, joined_group, name, custom_id, last_bonus_date, unlocked_points
            FROM users
        ''')
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            bot.reply_to(message, get_text('admin.export.empty_users', lang))
            return

        # Write CSV format
        string_io = StringIO()
        writer = csv.writer(string_io)
        writer.writerow([
            "Telegram ID", "Last Sign-in", "Points", "Binance UID", "X Account", 
            "A Account", "Inviter ID", "Joined Group", "Name", "Custom ID", "Last Bonus Date", "Unlocked Points"
        ])
        for row in rows:
            writer.writerow(row)

        byte_io = BytesIO(string_io.getvalue().encode("utf-8"))
        byte_io.seek(0)
        filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        bot.send_document(message.chat.id, byte_io, visible_file_name=filename, caption=get_text('admin.export.export_success_users', lang))
        byte_io.close()

    except Exception as e:
        bot.reply_to(message, get_text('admin.export.error', lang, error=str(e)))


@bot.message_handler(commands=['quiz_send'])
def send_quiz(message):
    lang = DEFAULT_LANGUAGE  # Admin commands use default language
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, get_text('quiz.no_permission', lang))
        return

    try:
        if message.text.strip() == "/quiz_send":
            # Read from quiz bank file
            with open('quiz_bank.json', 'r', encoding='utf-8') as f:
                quiz_list = json.load(f)
            if not quiz_list:
                bot.reply_to(message, get_text('quiz.empty', lang))
                return
            quiz_data = random.choice(quiz_list)

            # Print selected quiz (for debugging)
            print(get_log_text('logs.debug_selected_quiz', quiz_data=json.dumps(quiz_data, ensure_ascii=False)))

        else:
            quiz_data = json.loads(message.text.replace('/quiz_send', '').strip())

        question = quiz_data['question']
        options = quiz_data['options']
        correct_index = quiz_data['answer']

        quiz_id = str(uuid4())
        current_quiz.clear()
        current_quiz.update({
            "id": quiz_id,
            "question": question,
            "options": options,
            "answer": correct_index,
            "answered": set()
        })

        markup = types.InlineKeyboardMarkup()
        for idx, option in enumerate(options):
            markup.add(types.InlineKeyboardButton(option, callback_data=f"quiz_{quiz_id}_{idx}"))

        sent_msg = bot.send_message(ALLOWED_GROUP_ID, get_text('quiz.quiz_message', lang, question=question), reply_markup=markup)

        threading.Timer(1800, lambda: disable_quiz(quiz_id)).start()

    except Exception as e:
        bot.reply_to(message, get_text('quiz.format_error', lang, error=str(e)))

def disable_quiz(qid):
    lang = DEFAULT_LANGUAGE
    if current_quiz.get("id") == qid:
        current_quiz.clear()
        print(get_log_text('logs.quiz_ended'))
        bot.send_message(ALLOWED_GROUP_ID, get_text('quiz.ended', lang))


# ===== /submit Submission entry (private chat) =====
@bot.message_handler(commands=['submit'])
def handle_submit(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(message, get_text('commands.private_only', lang))
        return

    try:
        bot.clear_step_handler_by_chat_id(message.chat.id)
    except Exception:
        pass

    try:
        with open("campaigns.json", "r", encoding="utf-8") as f:
            campaigns = json.load(f)
    except Exception as e:
        bot.reply_to(message, get_text('submit.no_config', lang, error=str(e)))
        return

    if not isinstance(campaigns, list) or not campaigns:
        bot.reply_to(message, get_text('submit.no_activities', lang))
        return

    markup = types.InlineKeyboardMarkup()
    for camp in campaigns:
        lang = get_user_lang(message.from_user.id)
        title = camp.get("title", get_text('submit.untitled_activity', lang))
        camp_id = str(camp.get("id"))
        markup.add(types.InlineKeyboardButton(title, callback_data=f"select_campaign_{camp_id}"))
    bot.send_message(message.chat.id, get_text('submit.select_activity', lang), reply_markup=markup)


# ===== Campaign selection callback =====
@bot.callback_query_handler(func=lambda call: call.data.startswith("select_campaign_") or call.data == "back_to_submit")
def handle_campaign_selection(call):
    # Return to campaign list
    if call.data == "back_to_submit":
        # Reuse /submit logic
        fake = call.message  # Use existing message object to call
        fake.chat = call.message.chat
        handle_submit(fake)
        bot.answer_callback_query(call.id)
        return

    campaign_id = call.data.replace("select_campaign_", "").strip()

    lang = get_user_lang(call.from_user.id)
    # Load campaign configuration file
    try:
        with open("campaigns.json", "r", encoding="utf-8") as f:
            campaigns = json.load(f)
    except Exception as e:
        bot.send_message(call.message.chat.id, get_text('submit.no_config', lang, error=str(e)))
        return

    selected = next((c for c in campaigns if str(c.get("id")) == campaign_id), None)
    if not selected:
        bot.send_message(call.message.chat.id, get_text('submit.activity_not_found', lang, campaign_id=campaign_id))
        return

    # Deadline check (optional)
    deadline_str = selected.get("deadline")
    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
            now = datetime.now()
            if now > deadline:
                safe_title = html.escape(selected.get('title', get_text('submit.untitled_activity', lang)) or '')
                bot.send_message(
                    call.message.chat.id,
                    get_text('submit.activity_expired', lang, title=safe_title, deadline=deadline_str),
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                bot.answer_callback_query(call.id)
                return
        except Exception as e:
            print(get_log_text('logs.error_parse_deadline', error=str(e)))

    # Campaign description
    title = selected.get("title", get_text('submit.untitled_activity', lang)) or ""
    desc  = selected.get("desc", get_text('submit.no_description', lang)) or ""
    safe_title = html.escape(title)
    safe_desc  = html.escape(desc)
    deadline_display = deadline_str or get_text('common.not_set', lang, default='Not set')
    bot.send_message(
        call.message.chat.id,
        get_text('submit.activity_selected', lang, title=safe_title, desc=safe_desc, deadline=deadline_display),
        parse_mode="HTML",
        disable_web_page_preview=True
    )


    # Select submission type (including CMC)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(get_text('submit.binance_link', lang), callback_data=f"submit_binance_{campaign_id}"))
    markup.add(types.InlineKeyboardButton(get_text('submit.twitter_link', lang), callback_data=f"submit_twitter_{campaign_id}"))
    markup.add(types.InlineKeyboardButton(get_text('submit.cmc_link', lang), callback_data=f"submit_cmc_{campaign_id}"))
    markup.add(types.InlineKeyboardButton(get_text('submit.back_activities', lang), callback_data="back_to_submit"))
    bot.send_message(call.message.chat.id, get_text('submit.select_type', lang), reply_markup=markup)
    bot.answer_callback_query(call.id)


# ===== Handle callback for three submission types (binance/twitter/cmc) =====
@bot.callback_query_handler(func=lambda call: call.data.startswith("submit_"))
def handle_submit_callback(call):
    lang = get_user_lang(call.from_user.id)
    parts = call.data.split("_", 2)  # ["submit", "<type>", "<campaignId>"]
    if len(parts) != 3:
        bot.answer_callback_query(call.id, get_text('submit.invalid_submit', lang))
        return

    submit_type_raw, campaign_id = parts[1], parts[2]

    type_map = {
        "binance": "binance",
        "twitter": "twitter",
        "cmc": "cmc"
    }
    submit_type = type_map.get(submit_type_raw)
    if not submit_type:
        bot.answer_callback_query(call.id, get_text('submit.invalid_type', lang))
        return

    typ_name = get_text(f'submit.type_names.{submit_type}', lang)
    bot.send_message(call.message.chat.id, get_text('submit.link_prompt', lang, type=typ_name))

    # Note: Use next_step_handler to capture "next message"
    # If user enters a new command (e.g. /submit) at this time, it will be recognized in the next step handler and return to campaign list
    bot.register_next_step_handler(
        call.message,
        process_submission_with_campaign,
        submit_type,
        call.from_user.id,
        campaign_id
    )
    bot.answer_callback_query(call.id)


# ===== Handle final link input (including "command interruption" and "duplicate submission" handling) =====
def process_submission_with_campaign(message, submit_type, telegram_id, campaign_id):
    text = (message.text or "").strip()

    lang = get_user_lang(telegram_id)
    # If user enters a new command (e.g. /submit), cancel current input flow and re-show campaign selection
    if text.startswith("/"):
        bot.reply_to(message, get_text('submit.cancel', lang))
        handle_submit(message)  # Return directly to campaign selection
        return

    # Link validation
    if not text.lower().startswith("https"):
        bot.reply_to(message, get_text('submit.invalid_link', lang))
        # Continue waiting for next input (still in the same flow)
        bot.register_next_step_handler(message, process_submission_with_campaign, submit_type, telegram_id, campaign_id)
        return

    link = text

    # Additional CMC domain validation (optional, comment out to relax)
    if submit_type == "cmc" and "coinmarketcap.com" not in link.lower():
        bot.reply_to(message, get_text('submit.invalid_cmc', lang))
        bot.register_next_step_handler(message, process_submission_with_campaign, submit_type, telegram_id, campaign_id)
        return

    # Write to database (avoid duplicates)
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM submissions WHERE telegram_id = ? AND type = ? AND link = ?", (telegram_id, submit_type, link))
    exists = cursor.fetchone()

    if exists:
        bot.reply_to(message, get_text('submit.duplicate', lang))
        # Provide option to continue operation
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(get_text('submit.continue_activity', lang), callback_data=f"select_campaign_{campaign_id}"))
        markup.add(types.InlineKeyboardButton(get_text('submit.back_activities', lang), callback_data="back_to_submit"))
        bot.send_message(message.chat.id, get_text('submit.continue_prompt', lang), reply_markup=markup)
        conn.close()
        return

    try:
        cursor.execute(
            "INSERT INTO submissions (telegram_id, type, link, campaign_id) VALUES (?, ?, ?, ?)",
            (telegram_id, submit_type, link, campaign_id)
        )
        conn.commit()
        bot.reply_to(message, get_text('submit.success', lang, campaign_id=campaign_id))
    except Exception as e:
        bot.reply_to(message, get_text('submit.save_error', lang, error=str(e)))
    finally:
        conn.close()

    # After submission, provide next step options
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(get_text('submit.continue_activity', lang), callback_data=f"select_campaign_{campaign_id}"))
    markup.add(types.InlineKeyboardButton(get_text('submit.back_activities', lang), callback_data="back_to_submit"))
    bot.send_message(message.chat.id, get_text('submit.continue', lang), reply_markup=markup)


@bot.message_handler(commands=['add_sensitive'])
def handle_add_sensitive(message):
    lang = get_user_lang(message.from_user.id)
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, get_text('admin.sensitive.no_permission', lang))
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, get_text('admin.sensitive.format', lang))
        return

    new_word = args[1].strip().lower()
    if not new_word:
        bot.reply_to(message, get_text('admin.sensitive.empty', lang))
        return

    try:
        with open('sensitive_words.txt', 'a+', encoding='utf-8') as f:
            f.seek(0)
            existing_words = [line.strip().lower() for line in f.readlines()]
            if new_word in existing_words:
                bot.reply_to(message, get_text('admin.sensitive.exists', lang, word=new_word))
                return
            f.write(new_word + '\n')
        bot.reply_to(message, get_text('admin.sensitive.success', lang, word=new_word))
    except Exception as e:
        bot.reply_to(message, get_text('admin.sensitive.error', lang, error=str(e)))


@bot.callback_query_handler(func=lambda call: call.data.startswith("quiz_"))
def handle_quiz_answer(call):
    global last_click_times
    telegram_id = call.from_user.id
    now = time.time()

    # Rate limiting: no clicking again within 2 seconds
    if telegram_id in last_click_times and now - last_click_times[telegram_id] < RATE_LIMIT_SECONDS:
        lang = get_user_lang(telegram_id)
        bot.answer_callback_query(call.id, get_text('quiz.click_too_fast', lang))
        return
    last_click_times[telegram_id] = now

    parts = call.data.split("_")
    quiz_id, choice = parts[1], int(parts[2])
    telegram_id = call.from_user.id

    lang = get_user_lang(telegram_id)
    # No active quiz or mismatch
    if current_quiz.get("id") != quiz_id:
      try:
        bot.answer_callback_query(call.id, get_text('quiz.invalid', lang))
        return
      except:
        pass  # Prevent callback_query timeout exception

    # Check if already answered in database
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM quiz_answers WHERE quiz_id = ? AND telegram_id = ?", (quiz_id, telegram_id))
    if cursor.fetchone():
        conn.close()
        name = call.from_user.first_name or ""
        bot.send_message(call.message.chat.id, get_text('quiz.already_answered', lang, name=name))
        return

    # Insert quiz answer record
    cursor.execute("INSERT INTO quiz_answers (quiz_id, telegram_id) VALUES (?, ?)", (quiz_id, telegram_id))
    conn.commit()

    # Check if answer is correct
    name = call.from_user.first_name or ""
    if choice == current_quiz.get("answer"):
        user = get_user(telegram_id)

        update_user(telegram_id, 'points', user[2] + QUIZ_CORRECT_POINTS)
        add_monthly_points(telegram_id, QUIZ_CORRECT_POINTS)

       # bot.answer_callback_query(call.id, "✅ 回答正确！积分 +1")
        bot.send_message(call.message.chat.id, get_text('quiz.correct', lang, name=name))
    else:
        # bot.answer_callback_query(call.id, "❌ 回答错误")
        bot.send_message(call.message.chat.id, get_text('quiz.wrong', lang, name=name))
    conn.close()

@bot.message_handler(commands=['active'])
def handle_active_ranking(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type == 'private':
        # When using in private chat, require user to have joined group
        user = get_user(message.from_user.id)
        if not user or user[7] != 1:
            bot.reply_to(message, get_text('active.not_in_group', lang))
            return
    else:
        # In group chat, only allow specified group
        if message.chat.id != ALLOWED_GROUP_ID:
            return

    target_month = datetime.now().strftime('%Y-%m')

    # Get users with current points ≥ configured value
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id, name, custom_id FROM users WHERE points >= ?", (MIN_ACTIVE_POINTS,))
    user_info = {}
    for row in cursor.fetchall():
     tid = str(row[0])
     if int(tid) in ADMIN_IDS:
        continue  # Exclude admins
     user_info[tid] = {
        'name': row[1] or '',
        'custom_id': row[2] or ''
    }

    conn.close()

    log_path = "group_messages.log"
    pattern = re.compile(r'\[(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2}\] .*?\[User: (.*?) \((\d+)\)\]')
    activity = defaultdict(int)

    lang = get_user_lang(message.from_user.id)
    if not os.path.exists(log_path):
        bot.reply_to(message, get_text('active.no_log', lang))
        return

    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            match = pattern.search(line)
            if not match:
                continue
            date_str, _, tid = match.groups()
            if not date_str.startswith(target_month):
                continue
            if tid not in user_info:
                continue
            activity[tid] += 1

    sorted_activity = sorted(activity.items(), key=lambda x: x[1], reverse=True)[:20]

    if not sorted_activity:
        bot.reply_to(message, get_text('active.empty', lang, min=MIN_ACTIVE_POINTS))
        return

    msg = get_text('active.title', lang, month=target_month, min=MIN_ACTIVE_POINTS)
    for idx, (tid, count) in enumerate(sorted_activity, 1):
        info = user_info.get(tid, {})
        msg += get_text('active.item', lang, rank=idx, name=info['name'], id=tid, count=count)

    bot.reply_to(message, msg)

@bot.message_handler(commands=['ranking'])
def handle_ranking(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type == 'private':
        # When using in private chat, require user to have joined group
        user = get_user(message.from_user.id)
        if not user or user[7] != 1:
            bot.reply_to(message, get_text('active.not_in_group', lang))
            return
    else:
        # In group chat, only allow specified group
        if message.chat.id != ALLOWED_GROUP_ID:
            return

    month_str = datetime.now().strftime('%Y-%m')

    conn = sqlite3.connect('telegram_bot.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT u.telegram_id, u.name, COALESCE(m.earned, 0) AS earned
        FROM users u
        LEFT JOIN monthly_points m
          ON m.telegram_id = u.telegram_id AND m.month = ?
        WHERE COALESCE(m.earned, 0) > 0
        ORDER BY earned DESC
        LIMIT 20
    ''', (month_str,))
    rows = cur.fetchall()
    conn.close()

    lang = get_user_lang(message.from_user.id)
    msg = get_text('ranking.title', lang)
    rank = 1
    for tid, name, earned in rows:
        if int(tid) in ADMIN_IDS:
            continue  # Exclude admins
        clean_name_str = clean_name(name) or get_text('common.unknown', lang)
        msg += get_text('ranking.item', lang, rank=rank, name=clean_name_str, id=tid, points=earned)
        rank += 1
        if rank > 20:  # Limit to top 20
            break
    bot.reply_to(message, msg)


# /start command (private chat only)
@bot.message_handler(commands=['start'])
def handle_start(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return

    telegram_id = message.from_user.id
    args = message.text.split()
    invited_by = None
    if len(args) > 1:
        try:
            inviter_id = int(args[1])
            if inviter_id != telegram_id:
                invited_by = str(inviter_id)
        except:
            pass

    create_user_if_not_exist(telegram_id, invited_by)
    
    name = message.from_user.first_name or ""
    if message.from_user.last_name:
       name += " " + message.from_user.last_name

    custom_id = message.from_user.username or None  # Username may not exist
    update_user_name_and_custom_id(telegram_id, name.strip(), custom_id)


    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add('/start', '/bind', '/me', '/invites','/submit')

    lang = get_user_lang(telegram_id)
    invite_link = f"https://t.me/{bot.get_me().username}?start={telegram_id}"
    group_link_text = f"{get_text('start.join_group', lang)}\n{COMMUNITY_GROUP_LINK}\n" if COMMUNITY_GROUP_LINK else ""
    start_msg = get_text('start.start_message', lang, 
                        group_link=group_link_text,
                        invite_link=invite_link)
    bot.send_message(message.chat.id, start_msg, reply_markup=ReplyKeyboardRemove())

@bot.message_handler(commands=['signinword'])
def handle_sign_in_word(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.id != ALLOWED_GROUP_ID:
        bot.reply_to(message, get_text('signinword.group_only', lang))
        return
    if current_signin_word:
        msg = f"{get_text('signin.word_today', lang)}\n\n`{current_signin_word}`\n\n{get_text('signin.ranking_info', lang)}\n\n{get_text('signin.bonus_info', lang)}"
        bot.reply_to(message, msg, parse_mode="Markdown")
    else:
        bot.reply_to(message, get_text('signin.word_not_set', lang))

# /invites View invite count (private chat only)
@bot.message_handler(commands=['invites'])
def handle_invites(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return
    telegram_id = str(message.from_user.id)
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE invited_by = ? AND joined_group = 1", (telegram_id,))
    count = cursor.fetchone()[0]
    conn.close()
    invite_link = f"https://t.me/{bot.get_me().username}?start={telegram_id}"

    bot.reply_to(message, get_text('invites.count', lang, count=count, link=invite_link))
 

# /bind_binance UID (private chat only)
@bot.message_handler(commands=['bind_binance'])
def handle_bind_binance(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return
    telegram_id = message.from_user.id
    create_user_if_not_exist(telegram_id)
    try:
        uid = message.text.split()[1]
        if not uid.isdigit():
            raise ValueError
        update_user(telegram_id, 'binance_uid', uid)
        bot.reply_to(message, get_text('bind.binance_success', lang, uid=uid))
    except:
        bot.reply_to(message, get_text('bind.binance_error', lang))

# /bind_twitter handle (private chat only)
@bot.message_handler(commands=['bind_twitter'])
def handle_bind_twitter(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return
    telegram_id = message.from_user.id
    create_user_if_not_exist(telegram_id)
    try:
        handle = message.text.split()[1]
        if not handle.startswith('@'):
            raise ValueError
        update_user(telegram_id, 'twitter_handle', handle)
        bot.reply_to(message, get_text('bind.twitter_success', lang, handle=handle))
    except:
        bot.reply_to(message, get_text('bind.twitter_error', lang))

# /bind_address address (private chat only)
@bot.message_handler(commands=['bind_address', 'bind_community_account',])
def handle_bind_address(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return
    telegram_id = message.from_user.id
    create_user_if_not_exist(telegram_id)
    account_display_name = COMMUNITY_ACCOUNT_NAME or get_text('bind.address_name', lang)
    try:
        account = message.text.split()[1]
        update_user(telegram_id, 'a_account', account)
        bot.reply_to(message, get_text('bind.address_success', lang, name=account_display_name, address=account))
    except:
        bot.reply_to(message, get_text('bind.address_error', lang, name=account_display_name))

# /me View current info (private chat only)
@bot.message_handler(commands=['me'])
def handle_me(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(message, get_text('commands.private_only', lang))
        return

    telegram_id = message.from_user.id
    user = get_user(telegram_id)
    if not user:
        bot.reply_to(message, get_text('me.not_found', lang))
        return

    conn = sqlite3.connect('telegram_bot.db')
    cur = conn.cursor()
    # Invite count
    cur.execute("SELECT COUNT(*) FROM users WHERE invited_by = ? AND joined_group = 1", (str(telegram_id),))
    invite_count = cur.fetchone()[0]

    # Monthly earned
    month_str = datetime.now().strftime('%Y-%m')
    cur.execute("SELECT COALESCE(earned,0) FROM monthly_points WHERE telegram_id = ? AND month = ?", (telegram_id, month_str))
    row = cur.fetchone()
    month_points = row[0] if row else 0
    conn.close()

    current_points = user[2]
    unlocked_points = user[11] or 0

    account_display_name = COMMUNITY_ACCOUNT_NAME or get_text('bind.address_name', lang)
    binance = user[3] or get_text('common.not_bound', lang)
    twitter = user[4] or get_text('common.not_bound', lang)
    address_value = user[5] or get_text('common.not_bound', lang) if COMMUNITY_ACCOUNT_NAME else ""
    
    # Build message
    msg = f"{get_text('me.telegram_id', lang)}{telegram_id}\n"
    msg += f"{get_text('me.current_points', lang)}{current_points}\n"
    msg += f"{get_text('me.unlocked_points', lang)}{unlocked_points}\n"
    msg += f"{get_text('me.monthly_points', lang)}{month_points}\n"
    msg += f"{get_text('me.binance_uid', lang)}{binance}\n"
    msg += f"{get_text('me.twitter_account', lang)}{twitter}\n"
    if COMMUNITY_ACCOUNT_NAME:
        msg += f"{get_text('me.address', lang, name=account_display_name)}{address_value}\n"
    invite_link = f"https://t.me/{bot.get_me().username}?start={telegram_id}"
    msg += f"{get_text('me.invited_count', lang)}{invite_count}\n"
    msg += f"{get_text('me.invite_link_label', lang)}{invite_link}"
    bot.reply_to(message, msg)

@bot.message_handler(commands=['my_submissions'])
def handle_my_submissions(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return

    telegram_id = message.from_user.id
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT type, link FROM submissions WHERE telegram_id = ?", (telegram_id,))
    results = cursor.fetchall()
    conn.close()

    if not results:
        bot.reply_to(message, get_text('my_submissions.empty', lang))
        return

    binance_links = [link for typ, link in results if typ == "binance"]
    twitter_links = [link for typ, link in results if typ == "twitter"]
    cmc_links = [link for typ, link in results if typ == "cmc"]

    msg = get_text('my_submissions.title', lang)

    if binance_links:
        msg += get_text('my_submissions.binance', lang) + "\n".join(f"• {l}" for l in binance_links) + "\n\n"
    else:
        msg += get_text('my_submissions.binance', lang) + get_text('my_submissions.none', lang) + "\n\n"

    if twitter_links:
        msg += get_text('my_submissions.twitter', lang) + "\n".join(f"• {l}" for l in twitter_links) + "\n\n"
    else:
        msg += get_text('my_submissions.twitter', lang) + get_text('my_submissions.none', lang) + "\n"

    if cmc_links:
        msg += get_text('my_submissions.cmc', lang) + "\n".join(f"• {l}" for l in cmc_links)
    else:
        msg += get_text('my_submissions.cmc', lang) + get_text('my_submissions.none', lang)

    bot.reply_to(message, msg, parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=['bind'])
def handle_bind(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(get_text('bind.binance_uid', lang), callback_data="bind_binance"))
    markup.add(types.InlineKeyboardButton(get_text('bind.twitter', lang), callback_data="bind_x"))
    if COMMUNITY_ACCOUNT_NAME:
        account_display_name = COMMUNITY_ACCOUNT_NAME
        markup.add(types.InlineKeyboardButton(get_text('bind.address', lang, name=account_display_name), callback_data="bind_community"))
    bot.send_message(message.chat.id, get_text('bind.select_type', lang), reply_markup=markup)

@bot.message_handler(commands=['transfer_points'])
def handle_transfer_points(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return

    args = message.text.split()

    if len(args) != 3:
        bot.reply_to(message, get_text('transfer.format_error', lang))
        return

    try:
        sender_id = message.from_user.id
        recipient_id = int(args[1])
        amount = int(args[2])

        if sender_id == recipient_id:
            bot.reply_to(message, get_text('transfer.self', lang))
            return
        if amount <= 0:
            bot.reply_to(message, get_text('transfer.positive', lang))
            return

        sender = get_user(sender_id)
        recipient = get_user(recipient_id)

        if not sender:
            bot.reply_to(message, get_text('transfer.not_registered', lang))
            return
        if not recipient:
            bot.reply_to(message, get_text('transfer.target_not_found', lang))
            return
        if sender[11] < amount:
            bot.reply_to(message, get_text('transfer.insufficient', lang, points=sender[11]))
            return

        # Update database
        update_user(sender_id, 'unlocked_points', sender[11] - amount)
        update_user(recipient_id, 'unlocked_points', recipient[11] + amount)

        log_transfer(sender_id, recipient_id, amount)

        bot.reply_to(message, get_text('transfer.success', lang, amount=amount, id=recipient_id, remaining=sender[11] - amount))
    except ValueError:
        bot.reply_to(message, get_text('transfer.invalid_id', lang))
    except Exception as e:
        bot.reply_to(message, get_text('transfer.error', lang, error=str(e)))

@bot.message_handler(commands=['unlock_points'])
def handle_unlock_points(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return

    telegram_id = message.from_user.id
    user = get_user(telegram_id)
    if not user:
        bot.reply_to(message, get_text('unlock.not_registered', lang))
        return

    try:
        amount = int(message.text.split()[1])
        if amount <= 0:
            raise ValueError
    except:
        bot.reply_to(message, get_text('unlock.format_error', lang))
        return

    total_points = user[2]
    unlocked = user[11]  # unlocked_points is the 12th column in users table (index starts from 0)

    if total_points < amount:
        bot.reply_to(message, get_text('unlock.insufficient', lang, total=total_points, amount=amount))
        return

    # Update database
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users
        SET points = points - ?, unlocked_points = unlocked_points + ?
        WHERE telegram_id = ?
    ''', (amount, amount, telegram_id))
    conn.commit()
    conn.close()

    bot.reply_to(message, get_text('unlock.success', lang, amount=amount, unlocked=unlocked + amount))

@bot.message_handler(commands=['transfers'])
def handle_all_transfers(message):
    if message.chat.type != 'private':
        lang = get_user_lang(message.from_user.id)
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return

    telegram_id = message.from_user.id
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT sender_id, recipient_id, amount, timestamp
        FROM transfers
        WHERE sender_id = ? OR recipient_id = ?
        ORDER BY timestamp DESC
    ''', (telegram_id, telegram_id))

    records = cursor.fetchall()

    lang = get_user_lang(telegram_id)
    if not records:
        bot.reply_to(message, get_text('transfers.empty', lang))
        conn.close()
        return

    # Query all related users' name and custom_id (avoid duplicate queries)
    user_ids = set()
    for sid, rid, _, _ in records:
        user_ids.add(sid)
        user_ids.add(rid)

    placeholders = ",".join("?" for _ in user_ids)
    cursor.execute(f'''
        SELECT telegram_id, name, custom_id FROM users
        WHERE telegram_id IN ({placeholders})
    ''', tuple(user_ids))
    lang = get_user_lang(telegram_id)
    user_info = {row[0]: (row[1] or get_text('common.unknown', lang), row[2] or "") for row in cursor.fetchall()}

    conn.close()

    def format_user(uid):
        name, cid = user_info.get(uid, (get_text('common.unknown', lang), ""))
        return f"{name}（@{cid}）" if cid else f"{name}"

    msg = get_text('transfers.title', lang)
    for sid, rid, amt, ts in records:
        if sid == telegram_id:
            msg += get_text('transfers.sent', lang, amount=amt, id=rid, name=format_user(rid), time=ts)
        else:
            msg += get_text('transfers.received', lang, amount=amt, id=sid, name=format_user(sid), time=ts)

    bot.reply_to(message, msg, parse_mode="Markdown")


@bot.message_handler(commands=['transfer'])
def handle_transfer_button(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return
    bot.send_message(message.chat.id, get_text('transfer.recipient_prompt', lang))
    bot.register_next_step_handler(message, get_recipient_id)

def get_recipient_id(message):
    lang = get_user_lang(message.from_user.id)
    try:
        recipient_id = int(message.text.strip())
        if recipient_id == message.from_user.id:
            bot.reply_to(message, get_text('transfer.self', lang))
            return
        bot.send_message(message.chat.id, get_text('transfer.amount_prompt', lang))
        bot.register_next_step_handler(message, process_transfer_amount, recipient_id)
    except:
        bot.reply_to(message, get_text('transfer.invalid_recipient', lang))

def process_transfer_amount(message, recipient_id):
    lang = get_user_lang(message.from_user.id)
    try:
        amount = int(message.text.strip())
        sender_id = message.from_user.id

        if amount <= 0:
            bot.reply_to(message, get_text('transfer.positive', lang))
            return

        sender = get_user(sender_id)
        recipient = get_user(recipient_id)

        if not sender:
            bot.reply_to(message, get_text('transfer.not_registered_sender', lang))
            return
        if not recipient:
            bot.reply_to(message, get_text('transfer.target_not_found_sender', lang))
            return
        if sender[11] < amount:
            bot.reply_to(message, get_text('transfer.insufficient_sender', lang, points=sender[11]))
            return

        # Execute transfer
        update_user(sender_id, 'unlocked_points', sender[11] - amount)
        update_user(recipient_id, 'unlocked_points', recipient[11] + amount)

        log_transfer(sender_id, recipient_id, amount)

        bot.reply_to(message, get_text('transfer.success_sender', lang, amount=amount, id=recipient_id))
    except:
        bot.reply_to(message, get_text('common.invalid_input', lang, default='❌ Invalid input, please start over.'))


@bot.callback_query_handler(func=lambda call: call.data.startswith("bind_"))
def handle_bind_callback(call):
    lang = get_user_lang(call.from_user.id)
    if call.data == "bind_binance":
        bot.send_message(call.message.chat.id, get_text('bind.binance_prompt', lang))
    elif call.data == "bind_x":
        bot.send_message(call.message.chat.id, get_text('bind.twitter_prompt', lang))
    elif call.data == "bind_community":
        account_display_name = COMMUNITY_ACCOUNT_NAME or get_text('bind.address_name', lang)
        bot.send_message(call.message.chat.id, get_text('bind.address_prompt', lang, name=account_display_name))
    bot.answer_callback_query(call.id)

# ===== Admin custom news sending =====
URL_PATTERN = re.compile(r'https?://\S+')

@bot.message_handler(commands=['news'])  # If alias needed, can change to commands=['news', 'xinwen']
def handle_admin_news_zh(message):
    lang = DEFAULT_LANGUAGE  # Admin command uses default language
    # Admin only
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, get_text('commands.admin_only', lang))
        return

    # Recommend private chat only to avoid accidental sending in group
    if message.chat.type != 'private':
        bot.reply_to(message, get_text('commands.private_only', lang))
        return

    # Support "title + multi-line links" or "text containing multiple links"
    payload = message.text.replace('/news', '', 1).strip()
    if not payload:
        bot.reply_to(
            message,
            get_text('admin.news.usage', lang)
        )
        return

    lines = [ln.strip() for ln in payload.splitlines() if ln.strip()]
    title = ""
    urls = []

    # First line is title if not a link
    if lines and not lines[0].lower().startswith('http'):
        title = lines[0]
        lines = lines[1:]

    # Extract links from remaining lines; fallback to extract from entire payload
    for ln in lines:
        urls.extend(URL_PATTERN.findall(ln))
    if not urls:
        urls = URL_PATTERN.findall(payload)

    # Remove duplicates while preserving order
    urls = list(dict.fromkeys(urls))

    if not urls:
        bot.reply_to(message, get_text('admin.news.no_links', lang))
        return

    # Assemble content to send to group
    header = f"📰 *{title}*" if title else get_text('admin.news.default_title', lang)
    bullet_lines = [f"• {u}" for u in urls]
    full_msg = header + "\n" + "\n".join(bullet_lines)

    # Generate button for each link
    kb = types.InlineKeyboardMarkup()
    for idx, u in enumerate(urls, start=1):
        kb.add(types.InlineKeyboardButton(f"Open Link {idx}", url=u))

    try:
        bot.send_message(
            ALLOWED_GROUP_ID,
            full_msg,
            reply_markup=kb,
            disable_web_page_preview=True,
            parse_mode="Markdown"
        )
        bot.reply_to(message, get_text('admin.news.success', lang))
    except Exception as e:
        bot.reply_to(message, get_text('admin.news.error', lang, error=str(e)))


@bot.message_handler(commands=['get_group_id'])
def handle_get_group_id(message):
    lang = DEFAULT_LANGUAGE  # Admin command uses default language
    print(get_log_text('logs.received_group_message', title=message.chat.title, group_id=message.chat.id))
    if message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, get_text('group_id.printed', lang))
    else:
        bot.reply_to(message, get_text('group_id.group_only', lang))


# Select daily valid sign-in word and post it in group

def select_daily_signin_word():
    global current_signin_word
    print(get_log_text('logs.signin_task_executing', datetime=datetime.now()))
    if not os.path.exists(SIGNIN_WORDS_FILE):
        print(get_log_text('logs.signin_error_file_not_found', file=SIGNIN_WORDS_FILE))
        return

    with open(SIGNIN_WORDS_FILE, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        print(get_log_text('logs.signin_error_file_empty', file=SIGNIN_WORDS_FILE))
        return

    current_signin_word = random.choice(lines)
    print(get_log_text('logs.signin_task_word_selected', word=current_signin_word))
    
    # Write to temporary file
    with open(TEMP_SIGNIN_FILE, 'w', encoding='utf-8') as f:
        f.write(current_signin_word)
    print(get_log_text('logs.signin_task_saved', file=TEMP_SIGNIN_FILE))

    try:
        lang = DEFAULT_LANGUAGE
        signin_msg = f"{get_text('signin.word_today', lang)}\n\n`{current_signin_word}`\n\n{get_text('signin.word_prompt', lang)}"
        sent = bot.send_message(ALLOWED_GROUP_ID, signin_msg, parse_mode="Markdown")
        bot.pin_chat_message(ALLOWED_GROUP_ID, sent.message_id, disable_notification=False)
        threading.Timer(300, lambda: bot.unpin_chat_message(ALLOWED_GROUP_ID, message_id=sent.message_id)).start()
        print(get_log_text('logs.signin_task_sent', group_id=ALLOWED_GROUP_ID))
    except Exception as e:
        print(get_log_text('logs.signin_error_send_failed', error=str(e)))

@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'])
def handle_custom_signin_word(message):
    content = message.text if message.text else get_log_text('logs.non_text_message')
    print(get_log_text('logs.message_received', group_id=message.chat.id, user_id=message.from_user.id, content=content))
    
    try:
        with open(MESSAGE_LOG_FILE, 'a', encoding='utf-8') as log_file:
            log_file.write(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                f"[Group: {message.chat.title} | Group ID: {message.chat.id}] "
                f"[User: {message.from_user.first_name} ({message.from_user.id})] "
                f"{message.text.strip() if message.text else '[Non-text message]'}\n"
            )
    except Exception as e:
        print(get_log_text('logs.error_write_log', error=str(e)))
    
    load_activities()

    # Check sensitive words first
    sensitive_words = load_sensitive_words()
    text = message.text.lower() if message.text else ""

    for act in activities:
        for kw in act.get("match", []):
            if kw.lower() in text:
                lang = get_user_lang(message.from_user.id)
                bot.reply_to(message, get_text('activity.welcome', lang, title=act['title'], default=f"Welcome to join {act['title']}"))

    for word in sensitive_words:
        if word in text:
            try:
                bot.delete_message(message.chat.id, message.message_id)
                name_tmp = message.from_user.first_name or ""
                if message.from_user.last_name:
                    name_tmp += " " + message.from_user.last_name
                lang = DEFAULT_LANGUAGE  # Use default language for sensitive word warning
                warn = bot.send_message(
                    message.chat.id,
                    get_text('admin.sensitive.triggered', lang, username=message.from_user.username or '', name=name_tmp, id=message.from_user.id)
                )
                threading.Timer(15, lambda: bot.delete_message(message.chat.id, warn.message_id)).start()
                print(get_log_text('logs.sensitive_word_triggered', word=word, username=message.from_user.username or '', name=name_tmp, id=message.from_user.id))
            except Exception as e:
                print(get_log_text('logs.error_delete_sensitive', error=str(e)))
            return  # Return directly after hitting sensitive word

    telegram_id = message.from_user.id
    create_user_if_not_exist(telegram_id)

    # Sync username/custom ID
    name = message.from_user.first_name or ""
    if message.from_user.last_name:
        name += " " + message.from_user.last_name
    custom_id = message.from_user.username or None  # Username may not exist
    update_user_name_and_custom_id(telegram_id, name.strip(), custom_id)

    # Only allow specified group
    global current_signin_word, last_chat_points_time
    print(get_log_text('logs.signin_debug_check_group', msg_group_id=message.chat.id, allowed_group_id=ALLOWED_GROUP_ID))
    if message.chat.id != ALLOWED_GROUP_ID:
        print(get_log_text('logs.signin_debug_group_mismatch'))
        return
    
    # Award chat points (if enabled and rate limit allows, includes admins)
    if CHAT_POINTS > 0 and message.text:  # Only for text messages
        try:
            now_ts = time.time()
            last_time = last_chat_points_time.get(telegram_id, 0)
            # Rate limit: 1 minute between chat points
            if now_ts - last_time >= 60:
                user = get_user(telegram_id)
                if user:
                    current_points = user[2]
                    new_points = current_points + CHAT_POINTS
                    update_user(telegram_id, 'points', new_points)
                    add_monthly_points(telegram_id, CHAT_POINTS)
                    last_chat_points_time[telegram_id] = now_ts
        except Exception as e:
            print(get_log_text('logs.error_chat_points', error=str(e), default=f"[Error] Failed to award chat points: {e}"))
    
    print(get_log_text('logs.signin_debug_current_word', word=current_signin_word))
    if not current_signin_word:
        print(get_log_text('logs.signin_debug_word_empty', group_id=message.chat.id, user_id=message.from_user.id))
        return

    # Only enter when message matches sign-in word (improved matching: strip whitespace and compare case-insensitively)
    if not message.text:
        print(get_log_text('logs.signin_debug_not_text'))
        return
        
    msg_text_clean = message.text.strip().lower()
    signin_word_clean = current_signin_word.strip().lower()
    print(get_log_text('logs.signin_debug_received', message=message.text, cleaned=msg_text_clean, word=current_signin_word, word_cleaned=signin_word_clean))
    
    if msg_text_clean == signin_word_clean:
        print(get_log_text('logs.signin_debug_match_success'))
        try:
            user = get_user(telegram_id)  # Get current user first, to get joined_group / invited_by etc.
            now = datetime.now()
            today_str = now.strftime('%Y-%m-%d')
            last_signin = user[1]           # last_signin
            current_points = user[2]        # points
            invited_by = user[6]            # invited_by (string or None)
            joined_group_old = (user[7] or 0)  # joined_group old value (0/1)
            last_bonus_date = user[10]      # last_bonus_date

            # Check if already signed in (today)
            if last_signin:
                try:
                    last_signin_date = datetime.strptime(last_signin, '%Y-%m-%d %H:%M:%S').date()
                    if last_signin_date == now.date():
                        lang = get_user_lang(telegram_id)
                        msg = bot.reply_to(message, get_text('signin.already_signed', lang))
                        threading.Timer(30, lambda: bot.delete_message(message.chat.id, msg.message_id)).start()
                        return
                except Exception as e:
                    print(get_log_text('logs.error_parse_date', error=str(e)))

            # Record this sign-in
            update_user(telegram_id, 'last_signin', now.strftime('%Y-%m-%d %H:%M:%S'))
            new_points = current_points + SIGNIN_POINTS
            monthly_points_add = SIGNIN_POINTS

            # Record sign-in history (by date)
            record_signin_history(telegram_id, today_str)

            # Reward for 7 consecutive days within 7 days
            bonus_text = ""
            try:
                if count_signins_last_7_days(telegram_id) >= 7:
                    if (not last_bonus_date) or (datetime.strptime(last_bonus_date, "%Y-%m-%d") <= now - timedelta(days=7)):
                        new_points += SIGNIN_BONUS_POINTS
                        monthly_points_add += SIGNIN_BONUS_POINTS
                        lang = get_user_lang(telegram_id)
                        bonus_text = get_text('signin.bonus_reward', lang)
                        update_user(telegram_id, 'last_bonus_date', today_str)
            except Exception as e:
                print(get_log_text('logs.error_calculate_bonus', error=str(e)))

            # Update points
            update_user(telegram_id, 'points', new_points)
            add_monthly_points(telegram_id, monthly_points_add)

            # —— Key logic: First "valid group join" (first group sign-in completion) sets flag and rewards inviter ——
            # Only triggered when joined_group changes from 0 -> 1, ensuring reward is given only once
            if joined_group_old == 0:
                try:
                    update_user(telegram_id, 'joined_group', 1)
                    if invited_by:
                        inviter_id = int(invited_by)
                        inviter = get_user(inviter_id)
                        if inviter:
                            inviter_points = inviter[2] + INVITE_REWARD_POINTS
                            update_user(inviter_id, 'points', inviter_points)
                            add_monthly_points(inviter_id, INVITE_REWARD_POINTS)
                            print(get_log_text('logs.invite_reward_success', inviter_id=inviter_id, invitee_id=telegram_id, points=INVITE_REWARD_POINTS))
                except Exception as e:
                    print(get_log_text('logs.invite_reward_failed', invitee_id=telegram_id, error=str(e)))

            # Feedback message (auto cleanup)
            lang = get_user_lang(telegram_id)
            try:
                msg = bot.reply_to(
                    message,
                    get_text('signin.success', lang, points=new_points) + (f"\n{bonus_text}" if bonus_text else "")
                )
                threading.Timer(30, lambda: bot.delete_message(message.chat.id, msg.message_id)).start()
                print(get_log_text('logs.signin_success', user_id=message.from_user.id, points=monthly_points_add, total=new_points))
            except Exception as e:
                print(get_log_text('logs.signin_error_send_failed', error=str(e)))
                import traceback
                traceback.print_exc()
        except Exception as e:
            print(get_log_text('logs.signin_error_processing', error=str(e)))
            import traceback
            traceback.print_exc()
            try:
                lang = get_user_lang(telegram_id)
                bot.reply_to(message, get_text('signin.error', lang, default="签到处理失败，请稍后重试"))
            except:
                pass
        else:
            # Debug: Log when message doesn't match
            print(get_log_text('logs.signin_debug_no_match', input=message.text, word=current_signin_word))


def safe_delete(chat_id, msg_id, label=""):
    try:
        bot.delete_message(chat_id, msg_id)
    except Exception as e:
        print(get_log_text('logs.error_delete_message', label=label, msg_id=msg_id, error=str(e)))



def load_rss_sources(file_path='rss_sources.json', lang=None):
    """
    Load RSS sources from configuration file
    Supports both old format (list) and new format (dict with language keys)
    :param file_path: Path to RSS sources configuration file
    :param lang: Language code (e.g., 'zh_CN', 'en_US'), defaults to DEFAULT_LANGUAGE
    :return: List of RSS feed URLs
    """
    if lang is None:
        lang = DEFAULT_LANGUAGE
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
            # Support old format: list of URLs (backward compatibility)
            if isinstance(config, list):
                return config
            
            # New format: dict with language keys
            if isinstance(config, dict):
                # Try to get sources for specified language
                if lang in config and isinstance(config[lang], list):
                    return config[lang]
                
                # Fallback to default language if current language not found
                if DEFAULT_LANGUAGE in config and isinstance(config[DEFAULT_LANGUAGE], list):
                    print(get_log_text('logs.rss_language_not_found', lang=lang, default_lang=DEFAULT_LANGUAGE))
                    return config[DEFAULT_LANGUAGE]
                
                # Fallback to any available language
                for key, value in config.items():
                    if isinstance(value, list):
                        print(get_log_text('logs.rss_using_available', key=key))
                        return value
                
                raise ValueError("No valid RSS sources found in configuration file")
            
            raise ValueError("Configuration file format error, should be a list or dict.")
    except Exception as e:
        print(get_log_text('logs.rss_failed_load_config', error=str(e)))
        return []

def fetch_rss_news():
    if not NEWS_ENABLED:
        print(get_log_text('logs.scheduled_task_news_disabled'))
        return
    print(get_log_text('logs.scheduled_task_executing_news', datetime=datetime.now()))
    
    # Use default language to load RSS sources
    feeds = load_rss_sources(lang=DEFAULT_LANGUAGE)
    if not feeds:
        print(get_log_text('logs.scheduled_task_rss_empty'))
        return
    news_items = []

    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)

            if not feed.entries or not all(hasattr(entry, 'title') and hasattr(entry, 'link') for entry in feed.entries):
                print(get_log_text('logs.rss_source_invalid', url=feed_url))
                continue

            for entry in feed.entries[:5]:
                title = entry.title
                link = entry.link
                # Use title directly without translation
                news_items.append(f"• [{title}]({link})")

        except Exception as e:
            print(get_log_text('logs.rss_fetch_failed', url=feed_url, error=str(e)))
            continue

    news_items = news_items[:8]

    if news_items:
        # Use multilingual text for news title
        news_title = get_text('rss_news.daily_title', DEFAULT_LANGUAGE, default='📰 *Daily Crypto News Selection:*')
        message = f"{news_title}\n\n" + "\n".join(news_items)
        try:
            bot.send_message(ALLOWED_GROUP_ID, message, parse_mode='Markdown', disable_web_page_preview=True)
        except Exception as e:
            print(get_log_text('logs.rss_send_failed', error=str(e)))
    else:
        print(get_log_text('logs.rss_unable_fetch'))

price_cache = {}  # Store daily 00:00 price

def load_watchlist():
    try:
        with open('watchlist.json', 'r') as f:
            return json.load(f)
    except:
        return ["BTCUSDT"]

def fetch_price(symbol):
    url = f"{PRICE_API_BASE_URL}?symbol={symbol}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        return float(data['price']) if 'price' in data else None
    except Exception as e:
        print(get_log_text('logs.error_get_price', symbol=symbol, error=str(e)))
        return None

def update_daily_open_prices():
    global price_cache
    watchlist = load_watchlist()
    print(get_log_text('logs.scheduled_task_update_prices', datetime=datetime.now()))
    for symbol in watchlist:
        price = fetch_price(symbol)
        if price:
            price_cache[symbol] = price
            print(get_log_text('logs.price_open_price', symbol=symbol, price=price))
        else:
            print(get_log_text('logs.price_unable_get', symbol=symbol))

    # Write to file for persistence
    try:
        with open("open_prices.json", "w", encoding="utf-8") as f:
            json.dump(price_cache, f)
            print(get_log_text('logs.price_write_completed'))
    except Exception as e:
        print(get_log_text('logs.price_save_failed', error=str(e)))


def broadcast_price_changes():
    lang = DEFAULT_LANGUAGE  # Use default language for price broadcast
    watchlist = load_watchlist()
    messages = []
    print(get_log_text('logs.scheduled_task_broadcast_prices', datetime=datetime.now()))
    for symbol in watchlist:
        current_price = fetch_price(symbol)
        if not current_price:
            continue
        open_price = price_cache.get(symbol)
        if open_price:
            diff = current_price - open_price
            percent = (diff / open_price) * 100
            arrow = "📈" if percent > 0 else "📉"
            change_str = f"{arrow} {percent:.4f}%"
        else:
            change_str = get_text('price.no_open_price', lang)

        display_symbol = f"{symbol[:-4]}/USDT" if symbol.endswith("USDT") else symbol
        current_price_text = get_text('price.broadcast_current', lang, price=f"{current_price:.4f}")
        change_text = get_text('price.broadcast_change', lang, change=change_str)
        messages.append(f"🔥 {display_symbol}: \n{current_price_text} \n{change_text}\n")

    if messages:
        full_msg = "\n".join(messages)
        full_msg += "\n\n" + get_text('price.broadcast_hint', lang)
        try:
            bot.send_message(ALLOWED_GROUP_ID, full_msg)
        except Exception as e:
            print(get_log_text('logs.price_broadcast_failed', error=str(e)))


# ===== /draw command: Animated drawing from provided ID list, extract specified quantity, and announce name + custom_id + ID =====
# Usage example (admin only):
#   /draw 2 1001,1002,1003,1004
#   /draw 1 1001 1002 1003
# Note: Results will be announced in the session where command was sent (group/private chat), with animation demo and finally display name/@custom_id | ID (if database has record)

def _parse_id_list(ids_raw):
    tokens = re.split(r'[,\s]+', ids_raw.strip())
    parsed = []
    for t in tokens:
        if not t:
            continue
        if t.lstrip('-').isdigit():
            parsed.append(int(t))
    # Remove duplicates while preserving order
    seen = set()
    uniq = []
    for x in parsed:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq

def _window_display(candidates, current_index, window_size=9):
    """
    Display window_size elements around current highlighted item to avoid message being too long.
    Highlighted item is displayed as "➡️ *ID*" (Markdown bold).
    """
    n = len(candidates)
    if n <= window_size:
        start = 0
        end = n
    else:
        half = window_size // 2
        start = max(0, current_index - half)
        end = start + window_size
        if end > n:
            end = n
            start = end - window_size
    lines = []
    for i in range(start, end):
        x = candidates[i]
        if i == current_index:
            lines.append(f"➡️ *{x}*")
        else:
            lines.append(f"   {x}")
    return "\n".join(lines)

def _format_user_display(tid):
    """
    Read name and custom_id from users table (via get_user), return display string.
    - Has record: <name> (@custom_id | ID:<tid>) or <name> (ID:<tid>)
    - No record: ID:<tid>
    """
    try:
        user = get_user(int(tid))
    except Exception:
        user = None

    lang = DEFAULT_LANGUAGE  # Use default language for user display
    if user:
        name = user[8] or get_text('common.unknown', lang)
        custom = user[9] or ""
        if custom:
            return f"{name} (@{custom} | ID:{tid})"
        else:
            return f"{name} (ID:{tid})"
    else:
        return f"ID:{tid}"

def _animate_and_pick(chat_id, orig_msg_id, candidates, winner, rounds=30, speed_base=0.05):
    """
    Highlight items in candidates list one by one, finally stop at winner.
    rounds: base steps (larger = longer animation); speed_base: minimum delay (seconds).
    Finally replace the stop position with user info display (if DB has record).
    """
    lang = DEFAULT_LANGUAGE  # Use default language for draw animation
    try:
        n = len(candidates)
        if n == 0 or winner not in candidates:
            return

        start_idx = random.randint(0, n - 1)
        total_steps = rounds
        target_index = candidates.index(winner)
        extra = (target_index - (start_idx + total_steps) % n) % n
        total_steps = total_steps + extra

        for step in range(total_steps + 1):
            cur_idx = (start_idx + step) % n
            display = _window_display(candidates, cur_idx, window_size=9)
            footer = "\n\n" + get_text('admin.draw.in_progress', lang)
            try:
                bot.edit_message_text(chat_id=chat_id,
                                      message_id=orig_msg_id,
                                      text=display + footer,
                                      parse_mode='Markdown')
            except Exception:
                # Edit may fail due to rate limit or message deleted, ignore and continue
                pass

            # Delay gradually increases -> simulate deceleration
            t = speed_base * (1 + (step / (total_steps if total_steps else 1)) * 5.0)
            time.sleep(t)

        # Final stop: format winner display with database info
        final_display = _window_display(candidates, candidates.index(winner), window_size=9)
        winner_label = _format_user_display(winner)
        final_text = final_display + "\n\n" + get_text('admin.draw.selected', lang, winner=winner_label)
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=orig_msg_id, text=final_text, parse_mode='Markdown')
        except Exception:
            pass

    except Exception as e:
        print(get_log_text('logs.animate_error', error=str(e)))

@bot.message_handler(commands=['export_month_rank'])
def export_month_rank_csv(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(message, get_text('commands.private_only', lang))
        return
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, get_text('commands.admin_only', lang))
        return

    args = message.text.strip().split()
    if len(args) != 2:
        bot.reply_to(message, get_text('admin.month_rank.format', lang))
        return

    month_str = args[1]
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.telegram_id, u.name, u.custom_id, m.earned
        FROM monthly_points m
        JOIN users u ON u.telegram_id = m.telegram_id
        WHERE m.month = ?
        ORDER BY m.earned DESC
    ''', (month_str,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        bot.reply_to(message, get_text('admin.export.empty_month', lang, month=month_str))
        return

    # Write CSV
    string_io = StringIO()
    writer = csv.writer(string_io)
    writer.writerow([f"{month_str} Ranking"])
    writer.writerow(["Rank", "Telegram ID", "Name", "Custom ID", "Points"])
    for idx, (tid, name, custom_id, earned) in enumerate(rows, 1):
        writer.writerow([idx, tid, name or get_text('common.unknown', lang), custom_id or "", earned])

    byte_io = BytesIO(string_io.getvalue().encode('utf-8-sig'))
    byte_io.seek(0)
    file_name = f"monthly_rank_{month_str}.csv"
    bot.send_document(
        message.chat.id,
        byte_io,
        visible_file_name=file_name,
        caption=get_text('admin.export.export_success_month', lang, month=month_str)
    )
    byte_io.close()


@bot.message_handler(commands=['draw'])
def cmd_draw(message):
    """
    /draw <count> <id1,id2,... or id1 id2 ...>
    Admin only: Only ADMIN_IDS can use
    """
    lang = DEFAULT_LANGUAGE  # Admin command uses default language
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, get_text('admin.draw.no_permission', lang))
        return

    parts = message.text.strip().split(None, 2)
    if len(parts) < 3:
        bot.reply_to(message, get_text('admin.draw.format', lang))
        return

    # Parse count
    try:
        count = int(parts[1])
        if count <= 0:
            raise ValueError
    except Exception:
        bot.reply_to(message, get_text('admin.draw.positive', lang))
        return

    ids_raw = parts[2]
    uniq_ids = _parse_id_list(ids_raw)
    if not uniq_ids:
        bot.reply_to(message, get_text('admin.draw.no_ids', lang))
        return

    # Determine actual draw count (without replacement)
    draw_count = min(count, len(uniq_ids))
    winners = random.sample(uniq_ids, draw_count)

    # Send placeholder message first, then use thread to play animation and announce final summary
    try:
        sent = bot.send_message(message.chat.id, get_text('admin.draw.start', lang))
    except Exception as e:
        bot.reply_to(message, get_text('admin.draw.error', lang, error=str(e)))
        return

    def worker():
        candidates = uniq_ids[:]  # Copy candidate list
        selected = []
        for w in winners:
            _animate_and_pick(message.chat.id, sent.message_id, candidates, w, rounds=28, speed_base=0.04)
            selected.append(w)
            time.sleep(0.8)
            # Remove from candidates after selection to avoid duplicate selection (comment next line if you want to allow duplicates)
            try:
                candidates.remove(w)
            except Exception:
                pass

        # Final summary and send in current session: print name + custom_id from DB
        summary = get_text('admin.draw.end', lang)
        for i, s in enumerate(selected, 1):
            summary += f"{i}. {_format_user_display(s)}\n"

        if count > len(uniq_ids):
            summary += get_text('admin.draw.note', lang, requested=count, available=len(uniq_ids))

        try:
            bot.send_message(message.chat.id, summary)
        except Exception:
            # Fallback: if sending fails, send simple ID list
            fallback = "Draw ended, selected IDs:\n" + "\n".join(str(x) for x in selected)
            bot.send_message(message.chat.id, fallback)

    threading.Thread(target=worker, daemon=True).start()

# ===== /recent_points View recent points records (private chat) =====
@bot.message_handler(commands=['recent_points'])
def handle_recent_points(message):
    lang = get_user_lang(message.from_user.id)
    if message.chat.type != 'private':
        bot.reply_to(
            message,
            get_text('commands.private_only', lang)
        )
        return

    telegram_id = message.from_user.id

    # Optional parameter: /recent_points 20  -> Show recent 20 records (default 10)
    parts = message.text.strip().split()
    try:
        limit = int(parts[1]) if len(parts) > 1 else 10
        limit = max(1, min(limit, 50))   # Limit range 1~50
    except:
        limit = 10

    try:
        conn = sqlite3.connect('telegram_bot.db')
        cur = conn.cursor()

        # Recent records (sorted by time descending)
        cur.execute('''
            SELECT amount, COALESCE(reason, ''), created_at
            FROM points_log
            WHERE telegram_id = ?
            ORDER BY id DESC
            LIMIT ?
        ''', (telegram_id, limit))
        rows = cur.fetchall()

        # Statistics for last 7/30 days total
        cur.execute('''
            SELECT COALESCE(SUM(amount),0)
            FROM points_log
            WHERE telegram_id = ?
              AND datetime(created_at) >= datetime('now','-7 days')
        ''', (telegram_id,))
        last7 = cur.fetchone()[0] or 0

        cur.execute('''
            SELECT COALESCE(SUM(amount),0)
            FROM points_log
            WHERE telegram_id = ?
              AND datetime(created_at) >= datetime('now','-30 days')
        ''', (telegram_id,))
        last30 = cur.fetchone()[0] or 0

        conn.close()

        if not rows:
            bot.reply_to(message, get_text('recent_points.empty', lang))
            return

        # Assemble message
        msg_lines = []
        msg_lines.append(get_text('recent_points.title', lang))
        msg_lines.append(get_text('recent_points.stats', lang, last7=last7, last30=last30))
        msg_lines.append(get_text('recent_points.recent', lang, count=len(rows)))

        no_reason = get_text('common.no_reason', lang, default='(No reason)')
        for amt, reason, ts in rows:
            reason = reason.strip() or no_reason
            msg_lines.append(get_text('recent_points.item', lang, time=ts, amount=amt, reason=reason))

        bot.reply_to(message, "\n".join(msg_lines), parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, get_text('recent_points.error', lang, error=str(e)))


# Enable news broadcasting scheduled task based on configuration
if NEWS_ENABLED:
    schedule.every().day.at(NEWS_BROADCAST_TIME).do(fetch_rss_news)

# Enable sign-in word scheduled task based on configuration
if SIGNIN_WORD_ENABLED:
    schedule.every().day.at(SIGNIN_WORD_TIME).do(select_daily_signin_word)

# Enable price update scheduled task (always enabled for price cache)
schedule.every().day.at(PRICE_UPDATE_TIME).do(update_daily_open_prices)

# Broadcast price at configured interval based on configuration
if PRICE_BROADCAST_ENABLED:
    schedule.every(PRICE_BROADCAST_INTERVAL_HOURS).hours.do(broadcast_price_changes)

# Initialize opening price once at startup
# Load price cache at startup
try:
    with open("open_prices.json", "r", encoding="utf-8") as f:
        price_cache = json.load(f)
        print(get_log_text('logs.startup_loaded_price_cache', cache=price_cache))
except Exception as e:
    print(get_log_text('logs.startup_failed_load_price_cache', error=str(e)))
    update_daily_open_prices()


#broadcast_price_changes()

# Execute once on startup
if not os.path.exists(TEMP_SIGNIN_FILE):
    print(get_log_text('logs.startup_no_temp_file'))
    if NEWS_ENABLED:
        fetch_rss_news()
    if SIGNIN_WORD_ENABLED:
        select_daily_signin_word()
else:
    with open(TEMP_SIGNIN_FILE, 'r', encoding='utf-8') as f:
        current_signin_word = f.read().strip()
        print(get_log_text('logs.startup_load_word', word=current_signin_word))
        if not current_signin_word and SIGNIN_WORD_ENABLED:
            print(get_log_text('logs.startup_word_empty'))
            select_daily_signin_word()


# New: Run scheduled tasks in separate thread
def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(5)

# Start scheduler thread
threading.Thread(target=run_schedule, daemon=True).start()

# Set bot commands with multilingual descriptions
commands = [
    telebot.types.BotCommand("start", get_text('commands.bot_commands.start', DEFAULT_LANGUAGE)),
    telebot.types.BotCommand("me", get_text('commands.bot_commands.me', DEFAULT_LANGUAGE)),
    telebot.types.BotCommand("bind", get_text('commands.bot_commands.bind', DEFAULT_LANGUAGE)),
    telebot.types.BotCommand("invites", get_text('commands.bot_commands.invites', DEFAULT_LANGUAGE)),
    telebot.types.BotCommand("submit", get_text('commands.bot_commands.submit', DEFAULT_LANGUAGE)),
    telebot.types.BotCommand("price", get_text('commands.bot_commands.price', DEFAULT_LANGUAGE)),
    telebot.types.BotCommand("feedback", get_text('commands.bot_commands.feedback', DEFAULT_LANGUAGE)),
    telebot.types.BotCommand("unlock_points", get_text('commands.bot_commands.unlock_points', DEFAULT_LANGUAGE)),  
    telebot.types.BotCommand("transfer", get_text('commands.bot_commands.transfer', DEFAULT_LANGUAGE)),
    telebot.types.BotCommand("transfers", get_text('commands.bot_commands.transfers', DEFAULT_LANGUAGE)),
    telebot.types.BotCommand("signinword", get_text('commands.bot_commands.signinword', DEFAULT_LANGUAGE)),
    telebot.types.BotCommand("ranking", get_text('commands.bot_commands.ranking', DEFAULT_LANGUAGE)),
    telebot.types.BotCommand("active", get_text('commands.bot_commands.active', DEFAULT_LANGUAGE)),
    telebot.types.BotCommand("recent_points", get_text('commands.bot_commands.recent_points', DEFAULT_LANGUAGE)),
    telebot.types.BotCommand("help", get_text('commands.bot_commands.help', DEFAULT_LANGUAGE)),
    telebot.types.BotCommand("faq", get_text('commands.bot_commands.faq', DEFAULT_LANGUAGE))
]
bot.set_my_commands(commands)


# Start Telegram Bot (main thread)
print(get_log_text('logs.bot_running'))

try:
    while True:
        try:
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
        except KeyboardInterrupt:
            print(get_log_text('logs.info_interrupt_received'))
            bot.stop_polling()
            break
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 502:
                print(get_log_text('logs.warning_telegram_502'))
                time.sleep(5)
                continue  # Continue loop directly, don't exit
            else:
                print(get_log_text('logs.error_telegram_api', error=str(e)))
                time.sleep(5)
        except Exception as e:
            print(get_log_text('logs.error_unknown_exception', error=str(e)))
            time.sleep(5)
except KeyboardInterrupt:
    print(get_log_text('logs.info_interrupt_received'))
    try:
        bot.stop_polling()
    except:
        pass
    print(get_log_text('logs.info_bot_stopped'))
