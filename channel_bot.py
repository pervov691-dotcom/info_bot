import sqlite3
import os
import asyncio
from datetime import datetime, timedelta
from typing import Tuple, Optional, List, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)
from telegram.request import HTTPXRequest

# ===== КОНФИГУРАЦИЯ =====
TOKEN = "8775867504:AAFM9gKgX9xJwd2QRocYXXbts2V1LHrna2E"  # ЗАМЕНИ!
ADMIN_IDS = [1320819190]  # ТВОЙ ID!
CHANNEL_ID = "@vne_sebya_ai"  # основной канал для проверки подписки

DB_NAME = "support_bot.db"

# ===== ФУНКЦИЯ МИГРАЦИИ БД =====
def migrate_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE bot_users ADD COLUMN is_verified BOOLEAN DEFAULT 0")
        print("✅ Добавлена колонка is_verified")
    except:
        pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                updated_at TEXT
            )
        ''')
        print("✅ Таблица announcements создана")
    except:
        pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS about_buttons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                button_key TEXT UNIQUE,
                button_text TEXT,
                button_url TEXT,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        print("✅ Таблица about_buttons создана")
        
        default_buttons = [
            ("channel", "📢 Основной канал", f"https://t.me/{CHANNEL_ID.replace('@', '')}", 1),
            ("support", "🤖 Бот поддержки", "https://t.me/stats_prison_bot", 1),
            ("game", "🎮 Игровой бот Тюряга", "https://t.me/tyryaga_bot", 1),
        ]
        for key, text, url, active in default_buttons:
            cursor.execute('INSERT OR IGNORE INTO about_buttons (button_key, button_text, button_url, is_active) VALUES (?, ?, ?, ?)',
                          (key, text, url, active))
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE bot_users ADD COLUMN username TEXT")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE bot_users ADD COLUMN first_seen TEXT")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE bot_users ADD COLUMN last_active TEXT")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE bot_users ADD COLUMN questions_count INTEGER DEFAULT 0")
    except:
        pass
    
    conn.commit()
    conn.close()

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            question TEXT,
            type TEXT DEFAULT 'question',
            status TEXT DEFAULT 'new',
            created_at TEXT,
            answered_at TEXT,
            answer TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_seen TEXT,
            last_active TEXT,
            questions_count INTEGER DEFAULT 0,
            is_verified BOOLEAN DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faq_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            title TEXT,
            content TEXT,
            updated_at TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS about_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            updated_at TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            updated_at TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS about_buttons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            button_key TEXT UNIQUE,
            button_text TEXT,
            button_url TEXT,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Заполняем "О боте"
    default_about = "ℹ️ О боте\n\nФункции бота:\n• Обратная связь с администратором\n• FAQ по игре Тюряга\n\nНажми на кнопки ниже, чтобы перейти:"
    cursor.execute('INSERT OR IGNORE INTO about_content (id, content, updated_at) VALUES (1, ?, ?)',
                  (default_about, datetime.now().isoformat()))
    
    # Заполняем объявления
    default_announcement = "📢 ОБЪЯВЛЕНИЯ\n\n🔥 Актуальные новости:\n\n• Бот работает в штатном режиме\n• По всем вопросам пишите в обратную связь\n• Скоро добавим новые функции\n\n✨ Следите за обновлениями!"
    cursor.execute('INSERT OR IGNORE INTO announcements (id, content, updated_at) VALUES (1, ?, ?)',
                  (default_announcement, datetime.now().isoformat()))
    
    # Заполняем кнопки "О боте"
    default_buttons = [
        ("channel", "📢 Основной канал", f"https://t.me/{CHANNEL_ID.replace('@', '')}", 1),
        ("support", "🤖 Бот поддержки", "https://t.me/stats_prison_bot", 1),
        ("game", "🎮 Игровой бот Тюряга", "https://t.me/tyryaga_bot", 1),
    ]
    for key, text, url, active in default_buttons:
        cursor.execute('INSERT OR IGNORE INTO about_buttons (button_key, button_text, button_url, is_active) VALUES (?, ?, ?, ?)',
                      (key, text, url, active))
    
    # Заполняем FAQ разделами
    default_faq = {
        "bosses": {"title": "🎮 Боссы", "content": "Как побеждать боссов:\n\n• Боссов 3 уровня: Шнырь, Баклан, Вор в Законе\n• Для победы нужно нанести урон\n• Урон зависит от уровня заточки\n• Есть 3 типа ударов: Заточка, Бутылка, Гаечный ключ\n\nСовет: Бутылка эффективна против Баклана, Ключ — против Вора в Законе"},
        "respect": {"title": "📊 Авторитет", "content": "Как повысить авторитет:\n\n• Побеждай боссов\n• Прокачивай заточку\n• Участвуй в ежедневных событиях\n• Приглашай друзей\n\nАвторитет открывает доступ к более сильным боссам!"},
        "party": {"title": "👥 Совместные бои", "content": "Как создать пати:\n\n• Выбери босса -> Создать пати\n• Отправь ссылку друзьям\n• Когда друзья присоединятся, бейте босса вместе\n• Урон всех участников суммируется\n• При победе награду получают все!\n\nВремя на битву: 3 часа"},
        "zatochka": {"title": "🔪 Заточка", "content": "Как прокачать заточку:\n\n• Заточка — твоё основное оружие\n• Улучшается за чифир\n• Чем выше уровень, тем больше урон\n• Урон: 15 + (уровень-1)*5\n\nСтоимость улучшения: 50 + (уровень-1)*25 чифира"},
        "chifir": {"title": "🍺 Чифир", "content": "Как заработать чифир:\n\n• Побеждай боссов\n• Забирай ежедневную хавку\n• Крысятничай (рискованно, но прибыльно)\n• Работай на шконке\n• Играй в карты\n• Участвуй в драках\n\nЧифир нужен для улучшения заточки и платных ударов!"},
        "krysa": {"title": "🐀 Крысятничество", "content": "Крысятничество:\n\n• Рискованный способ разбогатеть\n• 70 процентов успеха, 30 процентов провала\n• При успехе: +20-50 чифира\n• При провале: -10-30 чифира\n• Доступно раз в час\n\nСовет: Используй, когда нужен срочный чифир!"},
        "referral": {"title": "🤝 Реферальная система", "content": "Как работают рефералы:\n\n• Пригласи друга по своей ссылке\n• За каждого друга кулдауны уменьшаются на 0.5 процентов\n• Максимум -25 процентов (50 друзей)\n• Когда друг убьёт босса, ты получишь +50 процентов чифира!\n\nСсылку можно найти в разделе Пригласить друга"},
        "limits": {"title": "⚔️ Лимиты", "content": "Игровые ограничения:\n\n• Атак на боссов в день: 25\n• Между ударами заточкой: 3 минуты\n• Кулдаун работы: 5-15 минут\n• Кулдаун крысятничества: 1 час\n• Хавка доступна раз в 3 часа\n\nРефералы уменьшают кулдауны!"}
    }
    
    for key, data in default_faq.items():
        cursor.execute('INSERT OR IGNORE INTO faq_sections (key, title, content, updated_at) VALUES (?, ?, ?, ?)',
                      (key, data["title"], data["content"], datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

if os.path.exists(DB_NAME):
    migrate_db()
else:
    init_db()

# ===== ФУНКЦИИ =====
def get_about_content() -> str:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM about_content WHERE id = 1")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "О боте\n\nИнформация пока не добавлена."

def update_about_content(new_content: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE about_content SET content = ?, updated_at = ? WHERE id = 1",
                  (new_content, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_about_buttons():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT button_key, button_text, button_url FROM about_buttons WHERE is_active = 1 ORDER BY id")
    results = cursor.fetchall()
    conn.close()
    return [{"key": r[0], "text": r[1], "url": r[2]} for r in results]

def get_all_about_buttons():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, button_key, button_text, button_url, is_active FROM about_buttons ORDER BY id")
    results = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "key": r[1], "text": r[2], "url": r[3], "is_active": r[4]} for r in results]

def update_about_button(button_id: int, new_text: str = None, new_url: str = None, is_active: bool = None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if new_text:
        cursor.execute("UPDATE about_buttons SET button_text = ? WHERE id = ?", (new_text, button_id))
    if new_url:
        cursor.execute("UPDATE about_buttons SET button_url = ? WHERE id = ?", (new_url, button_id))
    if is_active is not None:
        cursor.execute("UPDATE about_buttons SET is_active = ? WHERE id = ?", (1 if is_active else 0, button_id))
    conn.commit()
    conn.close()

def add_about_button(button_key: str, button_text: str, button_url: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO about_buttons (button_key, button_text, button_url, is_active) VALUES (?, ?, ?, 1)',
                  (button_key, button_text, button_url))
    conn.commit()
    conn.close()

def delete_about_button(button_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM about_buttons WHERE id = ?", (button_id,))
    conn.commit()
    conn.close()

def get_announcement_content() -> str:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM announcements WHERE id = 1")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "Объявления\n\nИнформация пока не добавлена."

def update_announcement_content(new_content: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE announcements SET content = ?, updated_at = ? WHERE id = 1",
                  (new_content, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def mark_user_verified(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE bot_users SET is_verified = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_user_verified(user_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT is_verified FROM bot_users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] == 1 if result else False
    except:
        conn.close()
        return False

async def check_and_update_subscription(user_id: int, context) -> bool:
    subscribed = await is_subscribed(user_id, context)
    if subscribed:
        if not is_user_verified(user_id):
            mark_user_verified(user_id)
        return True
    else:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE bot_users SET is_verified = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return False

async def is_subscribed(user_id: int, context) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'creator', 'administrator']
    except:
        return False

def save_user(user_id: int, username: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bot_users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    if not exists:
        cursor.execute('INSERT INTO bot_users (user_id, username, first_seen, last_active, is_verified) VALUES (?, ?, ?, ?, 0)',
                      (user_id, username, datetime.now().isoformat(), datetime.now().isoformat()))
    else:
        cursor.execute("UPDATE bot_users SET last_active = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def save_question(user_id: int, username: str, question: str, q_type: str = 'question') -> int:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO questions (user_id, username, question, type, created_at, status)
        VALUES (?, ?, ?, ?, ?, 'new')
    ''', (user_id, username, question, q_type, datetime.now().isoformat()))
    q_id = cursor.lastrowid
    cursor.execute("UPDATE bot_users SET questions_count = questions_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return q_id

def get_unread_questions(limit: int = 20):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, username, question, type, created_at 
        FROM questions WHERE status = 'new' ORDER BY created_at DESC LIMIT ?
    ''', (limit,))
    results = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "user_id": r[1], "username": r[2], "question": r[3], "type": r[4], "created_at": r[5]} for r in results]

def get_all_questions(page: int = 0, per_page: int = 10):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM questions")
    total = cursor.fetchone()[0]
    offset = page * per_page
    cursor.execute('''
        SELECT id, user_id, username, question, type, status, created_at, answer
        FROM questions ORDER BY created_at DESC LIMIT ? OFFSET ?
    ''', (per_page, offset))
    results = cursor.fetchall()
    conn.close()
    questions = [{"id": r[0], "user_id": r[1], "username": r[2], "question": r[3], "type": r[4], 
                  "status": r[5], "created_at": r[6], "answer": r[7]} for r in results]
    return questions, total

def get_all_bot_users(page: int = 0, per_page: int = 15):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM bot_users")
    total = cursor.fetchone()[0]
    offset = page * per_page
    cursor.execute('''
        SELECT user_id, username, first_seen, last_active, questions_count, is_verified
        FROM bot_users ORDER BY first_seen DESC LIMIT ? OFFSET ?
    ''', (per_page, offset))
    results = cursor.fetchall()
    conn.close()
    users = []
    for r in results:
        users.append({
            "user_id": r[0], 
            "username": r[1] or "Аноним", 
            "first_seen": r[2][:19] if r[2] else "Неизвестно", 
            "last_active": r[3][:19] if r[3] else "Неизвестно", 
            "questions_count": r[4],
            "is_verified": r[5]
        })
    return users, total

def mark_question_answered(q_id: int, answer: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE questions SET status = 'answered', answered_at = ?, answer = ?
        WHERE id = ?
    ''', (datetime.now().isoformat(), answer, q_id))
    conn.commit()
    conn.close()

def get_faq_sections():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT key, title, content FROM faq_sections ORDER BY id")
    results = cursor.fetchall()
    conn.close()
    return [{"key": r[0], "title": r[1], "content": r[2]} for r in results]

def get_faq_section(key: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT key, title, content FROM faq_sections WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"key": result[0], "title": result[1], "content": result[2]}
    return None

def update_faq_section(key: str, content: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE faq_sections SET content = ?, updated_at = ? WHERE key = ?",
                  (content, datetime.now().isoformat(), key))
    conn.commit()
    conn.close()

def get_bot_analytics():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM bot_users")
    total_users = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM bot_users WHERE date(last_active) = date('now')")
    today_active = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM questions")
    total_questions = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM questions WHERE status = 'new'")
    unread_questions = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM questions WHERE date(created_at) = date('now')")
    today_questions = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT type, COUNT(*) FROM questions GROUP BY type")
    type_stats = cursor.fetchall()
    
    cursor.execute("SELECT username, questions_count FROM bot_users ORDER BY questions_count DESC LIMIT 5")
    top_active = cursor.fetchall()
    
    conn.close()
    
    type_names = {"question": "Вопросы", "idea": "Идеи", "bug": "Баги"}
    type_stats_dict = [(type_names.get(t, t), count) for t, count in type_stats]
    
    return {
        "total_users": total_users,
        "today_active": today_active,
        "total_questions": total_questions,
        "unread_questions": unread_questions,
        "today_questions": today_questions,
        "type_stats": type_stats_dict,
        "top_active": top_active
    }

# ===== КЛАВИАТУРЫ =====
def get_main_keyboard(user_id: int = None):
    keyboard = [
        [InlineKeyboardButton("📢 Объявления", callback_data="announcements")],
        [InlineKeyboardButton("📝 Задать вопрос", callback_data="ask_question")],
        [InlineKeyboardButton("📖 FAQ по игре", callback_data="faq_menu")],
        [InlineKeyboardButton("ℹ️ О боте", callback_data="about")]
    ]
    if user_id and user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("💬 Вопросы", callback_data="admin_questions")],
        [InlineKeyboardButton("👥 Пользователи бота", callback_data="admin_users")],
        [InlineKeyboardButton("🤖 Статистика бота", callback_data="admin_bot_stats")],
        [InlineKeyboardButton("📝 Редактировать FAQ", callback_data="admin_edit_faq")],
        [InlineKeyboardButton("✏️ Редактировать О боте", callback_data="admin_edit_about")],
        [InlineKeyboardButton("🔘 Редактировать кнопки О боте", callback_data="admin_edit_about_buttons")],
        [InlineKeyboardButton("📢 Редактировать Объявления", callback_data="admin_edit_announcements")],
        [InlineKeyboardButton("📤 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_users_list_keyboard(page: int = 0, total_pages: int = 0):
    keyboard = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Назад", callback_data=f"admin_users_page_{page-1}"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton("Вперед ▶️", callback_data=f"admin_users_page_{page+1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_faq_menu_keyboard():
    sections = get_faq_sections()
    keyboard = []
    for s in sections:
        keyboard.append([InlineKeyboardButton(s["title"], callback_data=f"faq_{s['key']}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_question_type_keyboard():
    keyboard = [
        [InlineKeyboardButton("❓ Вопрос", callback_data="qtype_question")],
        [InlineKeyboardButton("💡 Идея / Предложение", callback_data="qtype_idea")],
        [InlineKeyboardButton("🐛 Сообщить о баге", callback_data="qtype_bug")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_edit_faq_keyboard():
    sections = get_faq_sections()
    keyboard = []
    for s in sections:
        keyboard.append([InlineKeyboardButton(f"✏️ {s['title']}", callback_data=f"edit_faq_{s['key']}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_edit_about_buttons_keyboard():
    buttons = get_all_about_buttons()
    keyboard = []
    for btn in buttons:
        status = "✅" if btn['is_active'] else "❌"
        keyboard.append([InlineKeyboardButton(f"{status} {btn['text']}", callback_data=f"edit_about_btn_{btn['id']}")])
    keyboard.append([InlineKeyboardButton("➕ Добавить кнопку", callback_data="add_about_button")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_about_button_edit_keyboard(button_id: int):
    keyboard = [
        [InlineKeyboardButton("✏️ Изменить текст", callback_data=f"edit_btn_text_{button_id}")],
        [InlineKeyboardButton("🔗 Изменить ссылку", callback_data=f"edit_btn_url_{button_id}")],
        [InlineKeyboardButton("🔄 Вкл/Выкл", callback_data=f"toggle_btn_{button_id}")],
        [InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_btn_{button_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_edit_about_buttons")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_questions_list_keyboard(page: int = 0, total_pages: int = 0):
    keyboard = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"admin_questions_page_{page-1}"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"admin_questions_page_{page+1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("🔄 Только новые", callback_data="admin_questions_unread")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_question_detail_keyboard(q_id: int):
    keyboard = [
        [InlineKeyboardButton("✏️ Ответить", callback_data=f"answer_question_{q_id}")],
        [InlineKeyboardButton("✅ Отметить прочитанным", callback_data=f"mark_read_{q_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_questions")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard(target: str):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=target)]])

def get_verification_keyboard():
    keyboard = [
        [InlineKeyboardButton("🌟 ПЕРЕЙТИ В КАНАЛ 🌟", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")],
        [InlineKeyboardButton("✅ Я ПОДПИСАЛСЯ", callback_data="check_sub")],
        [InlineKeyboardButton("🔄 ПРОВЕРИТЬ СНОВА", callback_data="check_sub")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_about_keyboard():
    buttons = get_about_buttons()
    keyboard = []
    for btn in buttons:
        keyboard.append([InlineKeyboardButton(btn['text'], url=btn['url'])])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)

# ===== ОБРАБОТЧИКИ =====
async def start(update: Update, context):
    if not update.effective_user:
        return
    user_id = update.effective_user.id
    username = update.effective_user.username or f"user_{user_id}"
    
    save_user(user_id, username)
    subscribed = await check_and_update_subscription(user_id, context)
    
    if not subscribed:
        await update.message.reply_text(
            f"🔐 Доступ к боту закрыт\n\nЭтот бот создан для подписчиков канала {CHANNEL_ID}\n\nЧтобы получить доступ:\n1️⃣ Нажми на кнопку ПЕРЕЙТИ В КАНАЛ\n2️⃣ Подпишись на канал\n3️⃣ Вернись сюда и нажми Я ПОДПИСАЛСЯ\n\nПосле проверки подписки тебе откроется полный функционал бота.",
            reply_markup=get_verification_keyboard()
        )
        return
    
    await update.message.reply_text(
        f"👋 С возвращением, {username}!\n\nЯ помогу тебе:\n• Узнать актуальные объявления\n• Задать вопрос администратору\n• Получить справку по игре Тюряга\n\nВыбери действие в меню:",
        reply_markup=get_main_keyboard(user_id)
    )

async def handle_callback(update: Update, context):
    query = update.callback_query
    if not query:
        return
    user_id = query.from_user.id if query.from_user else None
    if not user_id:
        return
    
    username = query.from_user.username or f"user_{user_id}"
    data = query.data
    
    await query.answer()
    
    # Проверка подписки
    if data != "check_sub":
        subscribed = await check_and_update_subscription(user_id, context)
        if not subscribed and user_id not in ADMIN_IDS:
            await query.edit_message_text(
                f"🔐 Доступ запрещён\n\nТы отписался от канала {CHANNEL_ID}.\nПодпишись снова, чтобы продолжить пользоваться ботом.",
                reply_markup=get_verification_keyboard()
            )
            return
    
    if data == "check_sub":
        subscribed = await check_and_update_subscription(user_id, context)
        if subscribed:
            await query.edit_message_text(
                f"✅ Подписка подтверждена!\n\nДоступ к боту открыт. Добро пожаловать!\n\n👇 Выбери действие в меню:",
                reply_markup=get_main_keyboard(user_id)
            )
        else:
            await query.edit_message_text(
                f"❌ Подписка не найдена\n\nТы ещё не подписался на канал {CHANNEL_ID}\n\nЧтобы получить доступ:\n1️⃣ Нажми на кнопку ПЕРЕЙТИ В КАНАЛ\n2️⃣ Подпишись на канал\n3️⃣ Нажми Я ПОДПИСАЛСЯ снова",
                reply_markup=get_verification_keyboard()
            )
        return
    
    if data == "announcements":
        content = get_announcement_content()
        await query.edit_message_text(content, reply_markup=get_back_keyboard("back_to_menu"))
        return
    
    if data == "about":
        content = get_about_content()
        await query.edit_message_text(content, reply_markup=get_about_keyboard(), disable_web_page_preview=True)
        return
    
    if data == "ask_question":
        await query.edit_message_text("📝 Выбери тип вопроса:", reply_markup=get_question_type_keyboard())
        return
    
    if data.startswith("qtype_"):
        qtype = data.split("_")[1]
        type_names = {"question": "Вопрос", "idea": "Идея", "bug": "Баг"}
        context.user_data['question_type'] = qtype
        context.user_data['awaiting_question'] = True
        await query.edit_message_text(
            f"{type_names.get(qtype, 'Вопрос')}\n\n✍️ Напиши своё сообщение:\n\n(до 1000 символов)",
            reply_markup=get_back_keyboard("ask_question")
        )
        return
    
    if data == "faq_menu":
        await query.edit_message_text("📖 Выбери раздел:", reply_markup=get_faq_menu_keyboard())
        return
    
    if data.startswith("faq_"):
        key = data.replace("faq_", "")
        section = get_faq_section(key)
        if section:
            await query.edit_message_text(section["content"], reply_markup=get_back_keyboard("faq_menu"))
        return
    
    if data == "admin_panel" and user_id in ADMIN_IDS:
        await query.edit_message_text("👑 Админ-панель", reply_markup=get_admin_keyboard())
        return
    
    if data == "admin_users" and user_id in ADMIN_IDS:
        context.user_data['admin_users_page'] = 0
        users, total = get_all_bot_users(0, 15)
        pages = (total + 14) // 15
        if not users:
            await query.edit_message_text("👥 Нет пользователей!", reply_markup=get_back_keyboard("admin_panel"))
            return
        text = f"👥 Пользователи бота (стр.1/{pages})\n\n"
        for i, u in enumerate(users, 1):
            verified = "✅" if u['is_verified'] else "❌"
            text += f"{i}. {u['username']} (ID: {u['user_id']})\n"
            text += f"   Зарегистрирован: {u['first_seen']}\n"
            text += f"   Вопросов: {u['questions_count']} | Статус: {verified}\n\n"
        await query.edit_message_text(text, reply_markup=get_users_list_keyboard(0, pages))
        return
    
    if data.startswith("admin_users_page_") and user_id in ADMIN_IDS:
        page = int(data.split("_")[3])
        context.user_data['admin_users_page'] = page
        users, total = get_all_bot_users(page, 15)
        pages = (total + 14) // 15
        text = f"👥 Пользователи бота (стр.{page+1}/{pages})\n\n"
        for i, u in enumerate(users, page*15+1):
            verified = "✅" if u['is_verified'] else "❌"
            text += f"{i}. {u['username']} (ID: {u['user_id']})\n"
            text += f"   Зарегистрирован: {u['first_seen']}\n"
            text += f"   Вопросов: {u['questions_count']} | Статус: {verified}\n\n"
        await query.edit_message_text(text, reply_markup=get_users_list_keyboard(page, pages))
        return
    
    if data == "admin_bot_stats" and user_id in ADMIN_IDS:
        stats = get_bot_analytics()
        text = f"🤖 СТАТИСТИКА БОТА\n\n"
        text += f"👥 Всего пользователей: {stats['total_users']}\n"
        text += f"🟢 Активны сегодня: {stats['today_active']}\n"
        text += f"📊 Конверсия: {int(stats['today_active']/stats['total_users']*100) if stats['total_users'] > 0 else 0}%\n\n"
        text += f"💬 Вопросы:\n"
        text += f"• Всего: {stats['total_questions']}\n"
        text += f"• Сегодня: {stats['today_questions']}\n"
        text += f"• Непрочитанных: {stats['unread_questions']}\n\n"
        
        if stats['type_stats']:
            text += f"📊 По типам:\n"
            for t, count in stats['type_stats']:
                text += f"• {t}: {count}\n"
        
        if stats['top_active']:
            text += f"\n🏆 Топ активных:\n"
            for i, (name, count) in enumerate(stats['top_active'], 1):
                text += f"{i}. {name or 'Аноним'} — {count} вопросов\n"
        
        await query.edit_message_text(text, reply_markup=get_back_keyboard("admin_panel"))
        return
    
    if data == "admin_edit_about" and user_id in ADMIN_IDS:
        current_content = get_about_content()
        context.user_data['editing_about'] = True
        await query.edit_message_text(
            f"✏️ Редактирование раздела О боте\n\nТекущий текст:\n{current_content[:400]}...\n\nВведи новый текст:",
            reply_markup=get_back_keyboard("admin_panel")
        )
        return
    
    if data == "admin_edit_about_buttons" and user_id in ADMIN_IDS:
        await query.edit_message_text("🔘 Редактирование кнопок О боте\n\nВыбери кнопку для редактирования:", reply_markup=get_edit_about_buttons_keyboard())
        return
    
    if data.startswith("edit_about_btn_") and user_id in ADMIN_IDS:
        button_id = int(data.split("_")[3])
        context.user_data['editing_button_id'] = button_id
        await query.edit_message_text(f"🔘 Редактирование кнопки\n\nВыбери действие:", reply_markup=get_about_button_edit_keyboard(button_id))
        return
    
    if data.startswith("edit_btn_text_") and user_id in ADMIN_IDS:
        button_id = int(data.split("_")[3])
        context.user_data['editing_button_text_id'] = button_id
        await query.edit_message_text(f"✏️ Введи новый текст для кнопки:", reply_markup=get_back_keyboard("admin_edit_about_buttons"))
        return
    
    if data.startswith("edit_btn_url_") and user_id in ADMIN_IDS:
        button_id = int(data.split("_")[3])
        context.user_data['editing_button_url_id'] = button_id
        await query.edit_message_text(f"🔗 Введи новый URL для кнопки:\n\n(например: https://t.me/username или https://example.com)", reply_markup=get_back_keyboard("admin_edit_about_buttons"))
        return
    
    if data.startswith("toggle_btn_") and user_id in ADMIN_IDS:
        button_id = int(data.split("_")[2])
        buttons = get_all_about_buttons()
        for btn in buttons:
            if btn['id'] == button_id:
                update_about_button(button_id, is_active=not btn['is_active'])
                break
        await query.edit_message_text(f"✅ Статус кнопки изменён!", reply_markup=get_edit_about_buttons_keyboard())
        return
    
    if data.startswith("delete_btn_") and user_id in ADMIN_IDS:
        button_id = int(data.split("_")[2])
        delete_about_button(button_id)
        await query.edit_message_text(f"✅ Кнопка удалена!", reply_markup=get_edit_about_buttons_keyboard())
        return
    
    if data == "add_about_button" and user_id in ADMIN_IDS:
        context.user_data['adding_about_button'] = True
        await query.edit_message_text(f"➕ Добавление новой кнопки\n\nШаг 1/2: Введи текст для кнопки:", reply_markup=get_back_keyboard("admin_edit_about_buttons"))
        return
    
    if data == "admin_edit_announcements" and user_id in ADMIN_IDS:
        current_content = get_announcement_content()
        context.user_data['editing_announcements'] = True
        await query.edit_message_text(
            f"📢 Редактирование раздела Объявления\n\nТекущий текст:\n{current_content[:400]}...\n\nВведи новый текст:",
            reply_markup=get_back_keyboard("admin_panel")
        )
        return
    
    if data == "admin_questions" and user_id in ADMIN_IDS:
        context.user_data['admin_page'] = 0
        questions, total = get_all_questions(0, 10)
        pages = (total + 9) // 10
        if not questions:
            await query.edit_message_text("💬 Нет вопросов!", reply_markup=get_back_keyboard("admin_panel"))
            return
        text = f"💬 Вопросы (стр.1/{pages})\n\n"
        for i, q in enumerate(questions[:10], 1):
            status = "🆕" if q['status'] == 'new' else "✅"
            text += f"{status} {i}. {q['username']} [{q['type']}]\n   💭 {q['question'][:50]}...\n   🆔 {q['id']}\n\n"
        await query.edit_message_text(text, reply_markup=get_questions_list_keyboard(0, pages))
        return
    
    if data == "admin_questions_unread" and user_id in ADMIN_IDS:
        questions = get_unread_questions(20)
        if not questions:
            await query.edit_message_text("💬 Нет новых вопросов!", reply_markup=get_back_keyboard("admin_panel"))
            return
        text = f"💬 Новые вопросы ({len(questions)}):\n\n"
        for i, q in enumerate(questions[:10], 1):
            text += f"{i}. {q['username']} [{q['type']}]\n   💭 {q['question'][:60]}...\n   🆔 {q['id']}\n\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_questions")]]))
        return
    
    if data.startswith("admin_questions_page_") and user_id in ADMIN_IDS:
        page = int(data.split("_")[3])
        questions, total = get_all_questions(page, 10)
        pages = (total + 9) // 10
        text = f"💬 Вопросы (стр.{page+1}/{pages})\n\n"
        for i, q in enumerate(questions, page*10+1):
            status = "🆕" if q['status'] == 'new' else "✅"
            text += f"{status} {i}. {q['username']} [{q['type']}]\n   💭 {q['question'][:50]}...\n   🆔 {q['id']}\n\n"
        await query.edit_message_text(text, reply_markup=get_questions_list_keyboard(page, pages))
        return
    
    if data.startswith("question_detail_") and user_id in ADMIN_IDS:
        q_id = int(data.split("_")[2])
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, question, type, created_at, status, answer FROM questions WHERE id = ?", (q_id,))
        result = cursor.fetchone()
        conn.close()
        if result:
            user_id_q, username_q, question, qtype, created, status, answer = result
            text = f"📝 Вопрос #{q_id}\n\n"
            text += f"👤 От: {username_q} (ID: {user_id_q})\n"
            text += f"📋 Тип: {qtype}\n"
            text += f"📅 Дата: {created[:19]}\n"
            text += f"📊 Статус: {'🆕 Новый' if status == 'new' else '✅ Отвечен'}\n\n"
            text += f"💭 Вопрос:\n{question}\n"
            if answer:
                text += f"\n✏️ Ответ:\n{answer}"
            await query.edit_message_text(text, reply_markup=get_question_detail_keyboard(q_id))
        return
    
    if data.startswith("answer_question_") and user_id in ADMIN_IDS:
        q_id = int(data.split("_")[2])
        context.user_data['answering_question'] = q_id
        await query.edit_message_text(f"✏️ Введи ответ на вопрос #{q_id}:\n\n(можно использовать Markdown)", reply_markup=get_back_keyboard("admin_questions"))
        return
    
    if data.startswith("mark_read_") and user_id in ADMIN_IDS:
        q_id = int(data.split("_")[2])
        mark_question_answered(q_id, "")
        await query.edit_message_text(f"✅ Вопрос #{q_id} отмечен прочитанным!", reply_markup=get_back_keyboard("admin_questions"))
        return
    
    if data == "admin_edit_faq" and user_id in ADMIN_IDS:
        await query.edit_message_text("✏️ Выбери раздел для редактирования:", reply_markup=get_edit_faq_keyboard())
        return
    
    if data.startswith("edit_faq_") and user_id in ADMIN_IDS:
        key = data.replace("edit_faq_", "")
        section = get_faq_section(key)
        if section:
            context.user_data['editing_faq'] = key
            await query.edit_message_text(
                f"✏️ Редактирование: {section['title']}\n\nТекущий текст:\n{section['content'][:300]}...\n\nВведи новый текст:",
                reply_markup=get_back_keyboard("admin_edit_faq")
            )
            context.user_data['awaiting_faq_edit'] = True
        return
    
    if data == "admin_broadcast" and user_id in ADMIN_IDS:
        context.user_data['admin_action'] = 'broadcast'
        await query.edit_message_text("📤 Рассылка\n\nВведи текст сообщения для всех пользователей:", reply_markup=get_back_keyboard("admin_panel"))
        return
    
    if data == "back_to_menu":
        await query.edit_message_text("📌 Главное меню", reply_markup=get_main_keyboard(user_id))
        return

async def handle_message(update: Update, context):
    if not update.effective_user:
        return
    user_id = update.effective_user.id
    username = update.effective_user.username or f"user_{user_id}"
    text = update.message.text
    
    subscribed = await check_and_update_subscription(user_id, context)
    if not subscribed and user_id not in ADMIN_IDS:
        await update.message.reply_text(
            f"🔐 Доступ запрещён\n\nПодпишись на канал {CHANNEL_ID}, чтобы пользоваться ботом.",
            reply_markup=get_verification_keyboard()
        )
        return
    
    # Добавление новой кнопки (админ)
    if context.user_data.get('adding_about_button'):
        if 'button_text' not in context.user_data:
            context.user_data['button_text'] = text
            context.user_data['adding_about_button'] = False
            context.user_data['adding_about_button_url'] = True
            await update.message.reply_text(
                f"➕ Шаг 2/2: Введи URL для кнопки\n\nТекст кнопки: {text}\n\nВведи ссылку (например: https://t.me/username):",
                reply_markup=get_back_keyboard("admin_edit_about_buttons")
            )
        else:
            button_text = context.user_data.pop('button_text')
            button_key = f"custom_{int(datetime.now().timestamp())}"
            add_about_button(button_key, button_text, text)
            context.user_data['adding_about_button_url'] = False
            await update.message.reply_text(f"✅ Кнопка добавлена!", reply_markup=get_back_keyboard("admin_edit_about_buttons"))
        return
    
    if context.user_data.get('adding_about_button_url'):
        button_text = context.user_data.pop('button_text')
        button_key = f"custom_{int(datetime.now().timestamp())}"
        add_about_button(button_key, button_text, text)
        context.user_data['adding_about_button_url'] = False
        await update.message.reply_text(f"✅ Кнопка добавлена!", reply_markup=get_back_keyboard("admin_edit_about_buttons"))
        return
    
    if context.user_data.get('editing_button_text_id'):
        button_id = context.user_data.pop('editing_button_text_id')
        update_about_button(button_id, new_text=text)
        await update.message.reply_text(f"✅ Текст кнопки обновлён!", reply_markup=get_back_keyboard("admin_edit_about_buttons"))
        return
    
    if context.user_data.get('editing_button_url_id'):
        button_id = context.user_data.pop('editing_button_url_id')
        update_about_button(button_id, new_url=text)
        await update.message.reply_text(f"✅ URL кнопки обновлён!", reply_markup=get_back_keyboard("admin_edit_about_buttons"))
        return
    
    # Ожидание вопроса от пользователя
    if context.user_data.get('awaiting_question'):
        if len(text) > 1000:
            await update.message.reply_text("❌ Сообщение слишком длинное! Максимум 1000 символов.")
            return
        
        qtype = context.user_data.get('question_type', 'question')
        q_id = save_question(user_id, username, text, qtype)
        type_names = {"question": "Вопрос", "idea": "Идея", "bug": "Баг"}
        
        await update.message.reply_text(
            f"✅ {type_names.get(qtype, 'Сообщение')} отправлен!\n\nСпасибо за обратную связь! Администратор ответит в ближайшее время.\n\n🆔 ID обращения: {q_id}",
            reply_markup=get_back_keyboard("back_to_menu")
        )
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"📬 Новый вопрос!\n\n👤 От: {username} (ID: {user_id})\n📋 Тип: {type_names.get(qtype, 'Сообщение')}\n💭 {text[:300]}\n🆔 ID: {q_id}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 Ответить", callback_data=f"answer_question_{q_id}")]])
                )
            except:
                pass
        
        context.user_data['awaiting_question'] = False
        context.user_data['question_type'] = None
        return
    
    if context.user_data.get('editing_about'):
        update_about_content(text)
        await update.message.reply_text(f"✅ Раздел О боте обновлён!", reply_markup=get_back_keyboard("admin_panel"))
        context.user_data['editing_about'] = False
        return
    
    if context.user_data.get('editing_announcements'):
        update_announcement_content(text)
        await update.message.reply_text(f"✅ Раздел Объявления обновлён!", reply_markup=get_back_keyboard("admin_panel"))
        context.user_data['editing_announcements'] = False
        return
    
    if context.user_data.get('awaiting_faq_edit'):
        faq_key = context.user_data.get('editing_faq')
        if faq_key:
            update_faq_section(faq_key, text)
            await update.message.reply_text(f"✅ Раздел FAQ обновлён!", reply_markup=get_back_keyboard("admin_edit_faq"))
        context.user_data['awaiting_faq_edit'] = False
        context.user_data['editing_faq'] = None
        return
    
    if context.user_data.get('answering_question'):
        q_id = context.user_data.get('answering_question')
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, question FROM questions WHERE id = ?", (q_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            target_user_id, target_username, question = result
            mark_question_answered(q_id, text)
            
            try:
                await context.bot.send_message(
                    target_user_id,
                    f"📬 Ответ на ваш вопрос #{q_id}\n\n💭 Ваш вопрос:\n{question[:200]}\n\n✏️ Ответ администратора:\n{text}\n\nСпасибо за обратную связь!"
                )
            except:
                pass
            
            await update.message.reply_text(f"✅ Ответ на вопрос #{q_id} отправлен пользователю {target_username}!", reply_markup=get_back_keyboard("admin_questions"))
        
        context.user_data['answering_question'] = None
        return
    
    action = context.user_data.get('admin_action')
    if action and user_id in ADMIN_IDS:
        if action == 'broadcast':
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM bot_users WHERE is_verified = 1")
            users = cursor.fetchall()
            conn.close()
            
            count = 0
            for u in users:
                try:
                    await context.bot.send_message(u[0], f"📢 Рассылка от администратора\n\n{text}")
                    count += 1
                except:
                    pass
            await update.message.reply_text(f"✅ Рассылка отправлена {count} пользователям!")
            context.user_data['admin_action'] = None
        return
    
    await update.message.reply_text("❓ Я не понял команду.\n\nИспользуй кнопки меню для навигации.", reply_markup=get_back_keyboard("back_to_menu"))

def main():
    request = HTTPXRequest(
        connection_pool_size=10,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )
    
    app = Application.builder().token(TOKEN).request(request).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("📢 Бот запущен!")
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"📢 Канал для проверки: {CHANNEL_ID}")
    app.run_polling()

if __name__ == "__main__":
    main()
