import os
import sqlite3
from datetime import datetime, timedelta
import telebot
from telebot import types

# ----------------- تنظیمات اصلی -----------------
TOKEN = "8902490995:AAHA1ErHgkz2e4e21ERtUmL2rgouJKUgLH4"  # توکن ربات خود را اینجا قرار دهید
ADMIN_ID = 7681725005  # آیدی عددی تلگرام خود را وارد کنید

# تنظیمات کانال‌ها و پشتیبانی
CHANNEL_USERNAME = "@ILY_Config"  # آیدی کانال اصلی شما برای جوین اجباری (با @)
TUTORIAL_CHANNEL_LINK = "https://t.me/ILY_Config"  # لینک کانال آموزش
SUPPORT_USERNAME = "@ILY_Team_Admin"  # آیدی تلگرام پشتیبان (با @)

DB_NAME = "confing_shop.db"
bot = telebot.TeleBot(TOKEN)

# ----------------- توابع کار با دیتابیس -----------------
def execute_db(query, args=()):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(query, args)
    conn.commit()
    conn.close()

def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(query, args)
    r = c.fetchall()
    conn.commit()
    conn.close()
    return (r[0] if r else None) if one else r

def init_db():
    # تنظیمات کلیدی
    execute_db('''CREATE TABLE IF NOT EXISTS settings 
                 (key TEXT PRIMARY KEY, value TEXT)''')
    
    defaults = [
        ('price_per_gb', '4000'),
        ('card_number', '۶۰۳۷-۹۹۱۹-۹۹۹۹-۹۹۹۹'),
        ('card_holder', 'نام صاحب کارت'),
        ('faq', 'پاسخ سوالات متداول شما در اینجا قرار می‌گیرد.')
    ]
    for k, v in defaults:
        execute_db("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        
    # جدول کاربران (همراه با ستون‌های کیف پول، معرف و تایید فعال‌سازی)
    execute_db('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, 
                  last_trial_time TEXT, 
                  personal_discount INTEGER DEFAULT 0, 
                  balance INTEGER DEFAULT 0, 
                  referred_by INTEGER DEFAULT 0, 
                  is_activated INTEGER DEFAULT 0)''')
    
    # همگام‌سازی ستون‌ها برای جلوگیری از تداخل در دیتابیس‌های قدیمی
    for col, col_type in [("balance", "INTEGER DEFAULT 0"), ("referred_by", "INTEGER DEFAULT 0"), ("is_activated", "INTEGER DEFAULT 0")]:
        try:
            execute_db(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass
                 
    # لینک‌های تست رایگان
    execute_db('''CREATE TABLE IF NOT EXISTS test_links 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT UNIQUE, is_used INTEGER DEFAULT 0)''')
                 
    # سفارشات خرید کانفیگ اصلی (تحویل دستی و خودکار)
    execute_db('''CREATE TABLE IF NOT EXISTS orders 
                 (order_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT UNIQUE, 
                  gb_amount INTEGER, total_price INTEGER, status TEXT DEFAULT 'pending', 
                  receipt_file_id TEXT, config_link TEXT)''')
                  
    # سفارشات تمدید و افزایش حجم سرویس
    execute_db('''CREATE TABLE IF NOT EXISTS extensions 
                 (ext_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, 
                  gb_amount INTEGER, total_price INTEGER, status TEXT DEFAULT 'pending', 
                  receipt_file_id TEXT)''')
                  
    # کانفیگ‌های آماده و ذخیره‌شده در ربات بر اساس حجم
    execute_db('''CREATE TABLE IF NOT EXISTS premade_configs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, gb_amount INTEGER, link TEXT UNIQUE, is_used INTEGER DEFAULT 0)''')
                 
    # درخواست‌های شارژ کیف پول
    execute_db('''CREATE TABLE IF NOT EXISTS wallet_requests 
                 (req_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, status TEXT DEFAULT 'pending', receipt_file_id TEXT)''')
                  
    # کدهای تخفیف عمومی
    execute_db('''CREATE TABLE IF NOT EXISTS discount_codes 
                 (code TEXT PRIMARY KEY, percent INTEGER, max_uses INTEGER, used_count INTEGER DEFAULT 0)''')
                 
    # کدهای استفاده شده
    execute_db('''CREATE TABLE IF NOT EXISTS used_discounts 
                 (user_id INTEGER, code TEXT, PRIMARY KEY(user_id, code))''')

init_db()

# ----------------- بررسی جوین اجباری -----------------
def is_user_member(user_id):
    if user_id == ADMIN_ID:
        return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except Exception:
        return True

def send_join_request(chat_id):
    markup = types.InlineKeyboardMarkup()
    btn_link = types.InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")
    btn_check = types.InlineKeyboardButton("🔄 بررسی عضویت", callback_data="check_membership")
    markup.row(btn_link)
    markup.row(btn_check)
    
    bot.send_message(
        chat_id, 
        f"⚠️ برای استفاده از خدمات ربات، ابتدا باید در کانال رسمی ما عضو شوید.\n\nپس از عضویت، دکمه «بررسی عضویت» را لمس کنید:", 
        reply_markup=markup
    )

# دکوراتور بررسی عضویت کانال
def check_join_decorator(func):
    def wrapper(message, *args, **kwargs):
        user_id = message.chat.id
        if is_user_member(user_id):
            return func(message, *args, **kwargs)
        else:
            send_join_request(user_id)
    return wrapper

# ----------------- کیبوردهای ناوبری ربات -----------------
def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_buy = types.KeyboardButton("🛒 خرید سرویس")
    btn_wallet = types.KeyboardButton("➕ شارژ کیف پول")
    btn_ref = types.KeyboardButton("👥 کسب درآمد")
    btn_trial = types.KeyboardButton("🎁 تست رایگان")
    btn_account = types.KeyboardButton("👤 حساب کاربری")
    btn_faq = types.KeyboardButton("❓ سوالات متداول")
    btn_tutorials = types.KeyboardButton("📚 کانال آموزش")
    btn_support = types.KeyboardButton("📞 تماس با پشتیبانی")
    btn_extend = types.KeyboardButton("🔄 تمدید سرویس")
    
    markup.row(btn_buy, btn_wallet)
    markup.row(btn_ref, btn_trial)
    markup.row(btn_account, btn_extend)
    markup.row(btn_tutorials, btn_support, btn_faq)
    
    if user_id == ADMIN_ID:
        btn_admin = types.KeyboardButton("⚙️ پنل مدیریت")
        markup.add(btn_admin)
        
    return markup

def return_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
    return markup

def cancel_order_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ لغو سفارش"))
    return markup

def cancel_extension_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ لغو تمدید"))
    return markup

def cancel_charge_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ لغو شارژ حساب"))
    return markup

# ----------------- هندلر بازگشت به منوی اصلی -----------------
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت به منوی اصلی")
def back_to_main_handler(message):
    bot.send_message(message.chat.id, "شما به منوی اصلی بازگشتید:", reply_markup=main_keyboard(message.chat.id))

# ----------------- پاسخ به بررسی عضویت (بروزرسانی شده با سیستم پورسانت‌دهی دعوت) -----------------
@bot.callback_query_handler(func=lambda call: call.data == "check_membership")
def check_membership_callback(call):
    user_id = call.message.chat.id
    if is_user_member(user_id):
        bot.delete_message(user_id, call.message.message_id)
        
        # ثبت کاربر در سیستم در صورت عدم وجود
        execute_db("INSERT OR IGNORE INTO users (user_id, last_trial_time, balance, referred_by, is_activated) VALUES (?, NULL, 0, 0, 0)", (user_id,))
        
        # بررسی اینکه آیا کاربر قبلاً فعال‌سازی شده است یا خیر
        user_status = query_db("SELECT is_activated, referred_by FROM users WHERE user_id=?", (user_id,), one=True)
        is_activated = user_status[0] if user_status else 0
        referred_by = user_status[1] if user_status else 0
        
        # اعمال پورسانت دعوت به معرف در صورتی که عضویت اول کاربر باشد
        if is_activated == 0:
            execute_db("UPDATE users SET is_activated = 1 WHERE user_id=?", (user_id,))
            if referred_by and referred_by != 0:
                # افزایش ۱,۰۰۰ تومانی موجودی معرف
                execute_db("UPDATE users SET balance = balance + 1000 WHERE user_id=?", (referred_by,))
                try:
                    bot.send_message(
                        referred_by, 
                        f"🔔 **عضویت زیرمجموعه شما با موفقیت تایید شد!**\n\nمبلغ **۱,۰۰۰ تومان** به عنوان هدیه دعوت به کیف پول شما اضافه گردید.", 
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
                    
        bot.send_message(user_id, "✅ عضویت شما تایید شد! به ربات Confing خوش آمدید.", reply_markup=main_keyboard(user_id))
    else:
        bot.answer_callback_query(call.id, "❌ شما هنوز عضو کانال نشده‌اید.", show_alert=True)

# ----------------- دستور /start (پشتیبانی از لینک دعوت) -----------------
@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.chat.id
    referred_by = 0
    
    # استخراج شناسه معرف از لینک دعوت استارت
    if len(message.text.split()) > 1:
        param = message.text.split()[1]
        if param.startswith("ref_"):
            try:
                ref_candidate = int(param.replace("ref_", ""))
                if ref_candidate != user_id:  # کاربر نمی‌تواند خودش را دعوت کند
                    referred_by = ref_candidate
            except ValueError:
                pass
                
    # ثبت نام کاربر با معرف مربوطه (در حالت تعلیق تا زمان تایید عضویت اجباری)
    execute_db("INSERT OR IGNORE INTO users (user_id, last_trial_time, balance, referred_by, is_activated) VALUES (?, NULL, 0, ?, 0)", (user_id, referred_by))
    
    if not is_user_member(user_id):
        send_join_request(user_id)
        return
        
    # اگر کاربر از قبل عضو بود و فعال نشده بود، فعالش می‌کنیم
    user_status = query_db("SELECT is_activated, referred_by FROM users WHERE user_id=?", (user_id,), one=True)
    if user_status and user_status[0] == 0:
        execute_db("UPDATE users SET is_activated = 1 WHERE user_id=?", (user_id,))
        ref = user_status[1]
        if ref and ref != 0:
            execute_db("UPDATE users SET balance = balance + 1000 WHERE user_id=?", (ref,))
            try:
                bot.send_message(
                    ref, 
                    f"🔔 **عضویت زیرمجموعه شما با موفقیت تایید شد!**\n\nمبلغ **۱,۰۰۰ تومان** به عنوان هدیه دعوت به کیف پول شما اضافه گردید.", 
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    welcome_text = "سلام! به ربات فروشگاه **Confing** خوش آمدید. 👋"
    bot.send_message(user_id, welcome_text, parse_mode="Markdown", reply_markup=main_keyboard(user_id))

# ----------------- بخش جذاب سیستم کسب درآمد (زیرمجموعه‌گیری) -----------------
@bot.message_handler(func=lambda msg: msg.text == "👥 کسب درآمد")
@check_join_decorator
def affiliate_system_handler(message):
    user_id = message.chat.id
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    
    # دریافت تعداد کل افراد دعوت شده توسط این کاربر
    invited_count = query_db("SELECT COUNT(*) FROM users WHERE referred_by=? AND is_activated=1", (user_id,), one=True)[0]
    
    affiliate_text = f"👥 **سیستم کسب درآمد و زیرمجموعه‌گیری**\n\n" \
                     f"با دعوت از دوستان خود به ربات، بدون نیاز به سرمایه کیف پول خود را شارژ کنید!\n\n" \
                     f"🎁 **قوانین و هدایای شما:**\n" \
                     f"۱️⃣ به ازای ورود هر کاربر جدید با لینک شما و عضویت او در کانال، **۱,۰۰۰ تومان** به صورت آنی به کیف پول شما افزوده می‌شود.\n" \
                     f"۲️⃣ علاوه بر این، در صورت خرید هر کدام از زیرمجموعه‌های مستقیم شما، **۱۰٪ از کل مبلغ خرید آن‌ها** فوراً به کیف پول شما واریز خواهد شد (برای مثال با خرید ۶۰,۰۰۰ تومانی آن‌ها، ۶,۰۰۰ تومان به حساب شما واریز می‌گردد).\n\n" \
                     f"📊 **آمار دعوت‌های شما:**\n" \
                     f"👥 تعداد زیرمجموعه‌های فعال شما: **{invited_count} نفر**\n\n" \
                     f"🔗 **لینک دعوت اختصاصی شما:**\n" \
                     f"`{ref_link}`\n\n" \
                     f"👇 **متن آماده تبلیغاتی (بنر) برای اشتراک‌گذاری با دوستان:**"
                     
    # بنر آماده جهت کپی ساده کاربران
    banner_text = f"سلام! من از کانفیگ‌های پرسرعت، پرحجم و بدون قطعی فروشگاه **Confing** استفاده می‌کنم. پیشنهاد می‌کنم تو هم وارد این ربات بشی و از تست رایگان آن استفاده کنی:\n\n" \
                  f"👇 همین حالا وارد ربات شو و کانفیگتو تحویل بگیر:\n" \
                  f"{ref_link}"
                  
    bot.send_message(user_id, affiliate_text, parse_mode="Markdown")
    bot.send_message(user_id, banner_text, reply_markup=return_keyboard())

# ----------------- بخش شارژ کیف پول -----------------
@bot.message_handler(func=lambda msg: msg.text == "➕ شارژ کیف پول")
@check_join_decorator
def wallet_charge_start(message):
    msg = bot.send_message(
        message.chat.id, 
        "لطفاً مبلغی که می‌خواهید کیف پول خود را شارژ کنید به **تومان** وارد کنید (به عنوان مثال: 50000):", 
        parse_mode="Markdown",
        reply_markup=cancel_charge_keyboard()
    )
    bot.register_next_step_handler(msg, process_wallet_charge_amount)

def process_wallet_charge_amount(message):
    user_id = message.chat.id
    text = message.text.strip()
    
    if text == "❌ لغو شارژ حساب":
        bot.send_message(user_id, "❌ فرآیند شارژ کیف پول لغو شد.", reply_markup=main_keyboard(user_id))
        return
        
    try:
        amount = int(text)
        if amount < 1000:
            raise ValueError
    except ValueError:
        msg = bot.send_message(user_id, "⚠️ خطا! لطفاً یک مبلغ معتبر عددی و بزرگتر از ۱,۰۰۰ تومان وارد کنید:")
        bot.register_next_step_handler(msg, process_wallet_charge_amount)
        return
        
    card_num = query_db("SELECT value FROM settings WHERE key='card_number'", one=True)[0]
    card_holder = query_db("SELECT value FROM settings WHERE key='card_holder'", one=True)[0]
    
    checkout_text = f"💳 **درخواست شارژ کیف پول:**\n\n" \
                    f"💰 مبلغ درخواستی: {amount:,} تومان\n\n" \
                    f"لطفاً مبلغ فوق را به شماره کارت زیر واریز نمایید:\n" \
                    f"`{card_num}`\n" \
                    f"👤 به نام: {card_holder}\n\n" \
                    f"⚠️ پس از واریز، لطفاً **فقط عکس رسید بانکی خود** را ارسال کنید تا حساب شما شارژ شود:"
                    
    msg = bot.send_message(user_id, checkout_text, parse_mode="Markdown", reply_markup=cancel_charge_keyboard())
    bot.register_next_step_handler(msg, process_wallet_payment_receipt, amount)

def process_wallet_payment_receipt(message, amount):
    user_id = message.chat.id
    text = message.text.strip() if message.text else ""
    
    if text == "❌ لغو شارژ حساب":
        bot.send_message(user_id, "❌ فرآیند شارژ کیف پول لغو شد.", reply_markup=main_keyboard(user_id))
        return
        
    if not message.photo:
        msg = bot.send_message(user_id, "⚠️ خطا! لطفاً تصویر رسید بانکی خود را ارسال کنید:")
        bot.register_next_step_handler(msg, process_wallet_payment_receipt, amount)
        return
        
    photo_id = message.photo[-1].file_id
    
    # ثبت درخواست شارژ در پایگاه داده
    execute_db(
        "INSERT INTO wallet_requests (user_id, amount, receipt_file_id) VALUES (?, ?, ?)",
        (user_id, amount, photo_id)
    )
    
    # دریافت شناسه درخواست
    req_id = query_db("SELECT req_id FROM wallet_requests WHERE user_id=? ORDER BY req_id DESC LIMIT 1", (user_id,), one=True)[0]
    
    bot.send_message(user_id, "✅ رسید پرداخت شما ثبت شد و برای تایید به مدیریت ارسال گردید. به محض تایید، موجودی شما افزایش می‌یابد.", reply_markup=main_keyboard(user_id))
    
    # ارسال برای ادمین
    admin_text = f"💳 **درخواست شارژ حساب جدید**\n\n" \
                 f"🆔 شناسه درخواست: {req_id}\n" \
                 f"👤 کاربر: [{message.from_user.first_name}](tg://user?id={user_id})\n" \
                 f"💰 مبلغ درخواستی: {amount:,} تومان"
                 
    markup = types.InlineKeyboardMarkup()
    btn_approve = types.InlineKeyboardButton("✅ تایید و افزایش اعتبار", callback_data=f"appwal_{req_id}")
    btn_reject = types.InlineKeyboardButton("❌ رد درخواست شارژ", callback_data=f"rejwal_{req_id}")
    markup.row(btn_approve, btn_reject)
    
    bot.send_photo(ADMIN_ID, photo_id, caption=admin_text, parse_mode="Markdown", reply_markup=markup)

# ----------------- عملیات تایید/رد شارژ کیف پول توسط ادمین -----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("appwal_"))
def admin_approve_wallet(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ عدم دسترسی", show_alert=True)
        return
        
    try:
        req_id = int(call.data.split("_")[1])
        req_data = query_db("SELECT status, user_id, amount FROM wallet_requests WHERE req_id=?", (req_id,), one=True)
        
        if not req_data:
            bot.answer_callback_query(call.id, "❌ درخواست پیدا نشد.", show_alert=True)
            return
        if req_data[0] != 'pending':
            bot.answer_callback_query(call.id, f"⚠️ قبلاً رسیدگی شده است ({req_data[0]})", show_alert=True)
            return
            
        bot.answer_callback_query(call.id, "کیف پول کاربر شارژ شد.")
        user_id, amount = req_data[1], req_data[2]
        
        execute_db("UPDATE wallet_requests SET status='approved' WHERE req_id=?", (req_id,))
        execute_db("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        
        try:
            bot.send_message(user_id, f"🎉 خبر خوب! کیف پول شما با موفقیت به مبلغ **{amount:,} تومان** شارژ شد.\nاکنون می‌توانید سریع‌تر خرید کنید.", parse_mode="Markdown")
            bot.send_message(ADMIN_ID, f"✅ درخواست #{req_id} تایید شد و حساب کاربر به میزان {amount:,} تومان افزایش یافت.")
        except Exception as e:
            bot.send_message(ADMIN_ID, f"❌ خطا در ارسال پیام به کاربر: {e}")
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ خطا در اجرای دستور: {e}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("rejwal_"))
def admin_reject_wallet(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ عدم دسترسی", show_alert=True)
        return
        
    try:
        req_id = int(call.data.split("_")[1])
        req_data = query_db("SELECT status, user_id FROM wallet_requests WHERE req_id=?", (req_id,), one=True)
        
        if not req_data:
            bot.answer_callback_query(call.id, "❌ یافت نشد.", show_alert=True)
            return
        if req_data[0] != 'pending':
            bot.answer_callback_query(call.id, "⚠️ قبلاً رسیدگی شده است.", show_alert=True)
            return
            
        bot.answer_callback_query(call.id)
        msg = bot.send_message(ADMIN_ID, f"علت رد درخواست شارژ #{req_id} را بنویسید (یا 'ندارد' بفرستید):")
        bot.register_next_step_handler(msg, process_admin_reject_wallet, req_id, req_data[1])
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ خطا: {e}", show_alert=True)

def process_admin_reject_wallet(message, req_id, user_id):
    reason = message.text.strip()
    execute_db("UPDATE wallet_requests SET status='rejected' WHERE req_id=?", (req_id,))
    
    user_text = f"❌ درخواست شارژ کیف پول شما (شناسه: {req_id}) توسط مدیریت رد شد."
    if reason.lower() != 'ندارد':
        user_text += f"\n💬 علت: {reason}"
        
    try:
        bot.send_message(user_id, user_text)
        bot.send_message(ADMIN_ID, f"❌ درخواست #{req_id} رد شد.")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ خطا: {e}")

# ----------------- بخش خرید سرویس (سیستم ترکیبی و تحویل آنی) -----------------
@bot.message_handler(func=lambda msg: msg.text == "🛒 خرید سرویس")
@check_join_decorator
def buy_service_start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("📦 سرویس ۱۰ گیگ"), types.KeyboardButton("📦 سرویس ۲۰ گیگ"))
    markup.row(types.KeyboardButton("📦 سرویس ۳۰ گیگ"), types.KeyboardButton("📦 سرویس ۴۰ گیگ"))
    markup.row(types.KeyboardButton("📦 سرویس ۵0 گیگ"), types.KeyboardButton("📦 سرویس ۱۰۰ گیگ"))
    markup.row(types.KeyboardButton("❌ لغو سفارش"))
    
    price_per_gb = int(query_db("SELECT value FROM settings WHERE key='price_per_gb'", one=True)[0])
    
    info_text = f"🛒 **یکی از پکیج‌های زیر را جهت خرید انتخاب کنید:**\n\n" \
                f"💵 قیمت هر گیگابایت: {price_per_gb:,} تومان\n\n" \
                f"🔹 پکیج ۱۰ گیگابایت: {10*price_per_gb:,} تومان\n" \
                f"🔹 پکیج ۲۰ گیگابایت: {20*price_per_gb:,} تومان\n" \
                f"🔹 پکیج ۳۰ گیگابایت: {30*price_per_gb:,} تومان\n" \
                f"🔹 پکیج ۴۰ گیگابایت: {40*price_per_gb:,} تومان\n" \
                f"🔹 پکیج ۵۰ گیگابایت: {50*price_per_gb:,} تومان\n" \
                f"🔹 پکیج ۱۰۰ گیگابایت: {100*price_per_gb:,} تومان"
                
    msg = bot.send_message(message.chat.id, info_text, parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(msg, process_package_select)

def process_package_select(message):
    user_id = message.chat.id
    text = message.text.strip() if message.text else ""
    
    if text == "❌ لغو سفارش":
        bot.send_message(user_id, "❌ روند خرید شما لغو شد.", reply_markup=main_keyboard(user_id))
        return
        
    gbs_mapping = {
        "📦 سرویس ۱۰ گیگ": 10,
        "📦 سرویس ۲۰ گیگ": 20,
        "📦 سرویس ۳۰ گیگ": 30,
        "📦 سرویس ۴۰ گیگ": 40,
        "📦 سرویس ۵۰ گیگ": 50,
        "📦 سرویس ۱۰۰ گیگ": 100
    }
    
    if text not in gbs_mapping:
        msg = bot.send_message(user_id, "⚠️ لطفا فقط یکی از دکمه‌های پکیج‌ها را انتخاب کنید:")
        bot.register_next_step_handler(msg, process_package_select)
        return
        
    gb = gbs_mapping[text]
    
    user_db = query_db("SELECT balance, personal_discount FROM users WHERE user_id=?", (user_id,), one=True)
    user_balance = user_db[0] if user_db else 0
    personal_discount = user_db[1] if user_db else 0
    
    price_per_gb = int(query_db("SELECT value FROM settings WHERE key='price_per_gb'", one=True)[0])
    base_price = gb * price_per_gb
    final_price = int(base_price * (1 - (personal_discount / 100)))
    
    # بررسی موجودی کیف پول کاربر برای خرید آنی بدون نیاز به کارت به کارت
    if user_balance >= final_price:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("❌ لغو سفارش"))
        msg = bot.send_message(
            user_id, 
            f"💰 **موجودی حساب شما کافی است!**\n\n"
            f"🛒 فاکتور خرید سریع شما:\n"
            f"📦 حجم: {gb} گیگابایت\n"
            f"💵 قیمت نهایی: {final_price:,} تومان\n"
            f"💳 موجودی فعلی شما: {user_balance:,} تومان\n\n"
            f"لطفاً یک نام کاربری دلخواه و انگلیسی (بدون فاصله - حداقل ۳ کاراکتر) برای کانفیگ خود ارسال کنید تا بلافاصله کانفیگ شما تحویل داده شود:",
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.register_next_step_handler(msg, process_auto_delivery_purchase, gb, final_price)
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("➕ شارژ کیف پول و خرید سریع"), types.KeyboardButton("💳 پرداخت کارت به کارت مستقیم"))
        markup.add(types.KeyboardButton("❌ لغو سفارش"))
        
        msg = bot.send_message(
            user_id,
            f"⚠️ **موجودی کیف پول شما کافی نیست!**\n\n"
            f"💵 مبلغ فاکتور: {final_price:,} تومان\n"
            f"💳 موجودی کیف پول شما: {user_balance:,} تومان\n\n"
            f"می‌توانید همین حالا کیف پول خود را شارژ کنید تا سیستم به طور خودکار به شما کانفیگ بدهد، یا فیش مستقیم بفرستید تا توسط ادمین بررسی شود:",
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.register_next_step_handler(msg, process_insufficient_balance_choice, gb, final_price)

def process_insufficient_balance_choice(message, gb, final_price):
    user_id = message.chat.id
    text = message.text.strip() if message.text else ""
    
    if text == "❌ لغو سفارش":
        bot.send_message(user_id, "❌ فرآیند خرید لغو شد.", reply_markup=main_keyboard(user_id))
        return
    elif text == "➕ شارژ کیف پول و خرید سریع":
        bot.send_message(
            user_id, 
            f"مبلغ مورد نیاز برای خرید این سرویس با احتساب تخفیف شما **{final_price:,} تومان** است.\nلطفاً جهت شروع فرآیند شارژ همین مبلغ را ارسال کنید:",
            parse_mode="Markdown",
            reply_markup=cancel_charge_keyboard()
        )
        bot.register_next_step_handler(message, process_wallet_charge_amount)
    elif text == "💳 پرداخت کارت به کارت مستقیم":
        msg = bot.send_message(
            user_id, 
            "لطفاً یک نام کاربری دلخواه انگلیسی (بدون فاصله - حداقل ۳ کاراکتر) برای کانفیگ خود ارسال کنید:",
            reply_markup=cancel_order_keyboard()
        )
        bot.register_next_step_handler(msg, process_username_step_manual, gb, final_price)
    else:
        msg = bot.send_message(user_id, "⚠️ گزینه نامعتبر است. لطفاً مجدداً انتخاب کنید:")
        bot.register_next_step_handler(msg, process_insufficient_balance_choice, gb, final_price)

# ----------------- خرید آنی و تحویل خودکار از ساب‌لینک‌های آماده -----------------
def process_auto_delivery_purchase(message, gb, final_price):
    user_id = message.chat.id
    username = message.text.strip() if message.text else ""
    
    if username == "❌ لغو سفارش":
        bot.send_message(user_id, "❌ روند خرید شما لغو شد.", reply_markup=main_keyboard(user_id))
        return
        
    if not username.isalnum() or len(username) < 3:
        msg = bot.send_message(user_id, "⚠️ نام کاربری باید حداقل ۳ کاراکتر و شامل حروف انگلیسی و اعداد باشد. مجدداً ارسال کنید:")
        bot.register_next_step_handler(msg, process_auto_delivery_purchase, gb, final_price)
        return
        
    exist_check = query_db("SELECT 1 FROM orders WHERE username=?", (username,), one=True)
    if exist_check:
        msg = bot.send_message(user_id, "⚠️ این نام کاربری قبلاً ثبت شده است. نام کاربری دیگری ارسال کنید:")
        bot.register_next_step_handler(msg, process_auto_delivery_purchase, gb, final_price)
        return
        
    premade = query_db("SELECT id, link FROM premade_configs WHERE gb_amount=? AND is_used=0 LIMIT 1", (gb,), one=True)
    
    if not premade:
        bot.send_message(
            user_id, 
            "😔 متاسفانه در حال حاضر کانفیگ آماده برای این حجم موجود نیست.\n"
            "مدیریت در اسرع وقت موجودی را شارژ خواهد کرد. لطفاً به پشتیبانی پیام دهید تا کانفیگ به صورت دستی برایتان ارسال شود.", 
            reply_markup=main_keyboard(user_id)
        )
        bot.send_message(ADMIN_ID, f"⚠️ **فوری**: موجودی کانفیگ‌های آماده حجم **{gb} گیگابایت** به اتمام رسیده است و یک کاربر مایل به خرید آن با کیف پول بود.")
        return
        
    premade_id, config_link = premade[0], premade[1]
    
    # کسر هزینه از کیف پول و مصرف شدن کانفیگ آماده
    execute_db("UPDATE users SET balance = balance - ? WHERE user_id=?", (final_price, user_id))
    execute_db("UPDATE premade_configs SET is_used=1 WHERE id=?", (premade_id,))
    
    execute_db(
        "INSERT INTO orders (user_id, username, gb_amount, total_price, status, config_link) VALUES (?, ?, ?, ?, 'approved', ?)",
        (user_id, username, gb, final_price, config_link)
    )
    
    user_success_text = f"🎉 **خرید شما با موفقیت و به صورت آنی انجام شد!**\n\n" \
                        f"📦 سرویس: {gb} گیگابایت\n" \
                        f"👤 نام کاربری: `{username}`\n" \
                        f"💵 مبلغ کسر شده: {final_price:,} تومان\n\n" \
                        f"🔗 **لینک کانفیگ (ساب‌لینک) اختصاصی شما:**\n" \
                        f"`{config_link}`\n\n" \
                        f"💡 لینک فوق را کپی کرده و به برنامه متصل شوید. ممنون از خرید شما!"
                        
    bot.send_message(user_id, user_success_text, parse_mode="Markdown", reply_markup=main_keyboard(user_id))
    
    # اعمال سیستم پورسانت‌دهی خرید برای معرف (۱۰ درصد مبلغ خرید)
    apply_purchase_referral_bonus(user_id, final_price)
    
    bot.send_message(
        ADMIN_ID, 
        f"⚡️ **گزارش خرید خودکار**\n\n"
        f"👤 کاربر: {user_id}\n"
        f"📦 پکیج: {gb} گیگابایت\n"
        f"💵 مبلغ کسر شده از موجودی: {final_price:,} تومان\n"
        f"🔑 نام کاربری ثبت شده: `{username}`\n"
        f"✅ کانفیگ به طور آنی و خودکار تحویل داده شد."
    )

# تابع کمکی سیستم پورسانت‌دهی خرید به معرف
def apply_purchase_referral_bonus(user_id, final_price):
    referred_by_data = query_db("SELECT referred_by FROM users WHERE user_id=?", (user_id,), one=True)
    referred_by = referred_by_data[0] if referred_by_data else 0
    if referred_by and referred_by != 0:
        commission = int(final_price * 0.10)  # محاسبه ۱۰ درصد پورسانت
        if commission > 0:
            execute_db("UPDATE users SET balance = balance + ? WHERE user_id=?", (commission, referred_by))
            try:
                bot.send_message(
                    referred_by,
                    f"🎁 **دریافت پورسانت خرید زیرمجموعه!**\n\n"
                    f"یکی از کاربرانی که دعوت کرده‌اید خرید جدیدی انجام داد.\n"
                    f"💰 مبلغ **{commission:,} تومان** (۱۰٪ از مبلغ خرید او) به کیف پول شما اضافه شد!",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

# ----------------- خرید کارت به کارت مستقیم (در صورت موجودی ناکافی) -----------------
def process_username_step_manual(message, gb, final_price):
    user_id = message.chat.id
    username = message.text.strip() if message.text else ""
    
    if username == "❌ لغو سفارش":
        bot.send_message(user_id, "❌ روند خرید شما لغو شد.", reply_markup=main_keyboard(user_id))
        return
        
    if not username.isalnum() or len(username) < 3:
        msg = bot.send_message(user_id, "⚠️ نام کاربری باید حداقل ۳ کاراکتر انگلیسی و عدد باشد. مجدداً ارسال کنید:")
        bot.register_next_step_handler(msg, process_username_step_manual, gb, final_price)
        return
        
    exist_check = query_db("SELECT 1 FROM orders WHERE username=?", (username,), one=True)
    if exist_check:
        msg = bot.send_message(user_id, "⚠️ این نام کاربری ثبت شده است. نام کاربری دیگری ارسال کنید:")
        bot.register_next_step_handler(msg, process_username_step_manual, gb, final_price)
        return
        
    card_num = query_db("SELECT value FROM settings WHERE key='card_number'", one=True)[0]
    card_holder = query_db("SELECT value FROM settings WHERE key='card_holder'", one=True)[0]
    
    text = f"💳 **پرداخت مستقیم فاکتور خرید:**\n\n" \
           f"📦 حجم: {gb} گیگابایت\n" \
           f"👤 نام کاربری: `{username}`\n" \
           f"💵 مبلغ کل: {final_price:,} تومان\n\n" \
           f"جهت واریز مستقیم:\n" \
           f"`{card_num}`\n" \
           f"👤 نام صاحب کارت: {card_holder}\n\n" \
           f"⚠️ پس از واریز، **فقط تصویر فیش واریزی** خود را ارسال کنید:"
           
    msg = bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=cancel_order_keyboard())
    bot.register_next_step_handler(msg, process_payment_step, gb, username, final_price)

def process_payment_step(message, gb, username, total_price):
    if message.text == "❌ لغو سفارش":
        bot.send_message(message.chat.id, "❌ روند لغو شد.", reply_markup=main_keyboard(message.from_user.id))
        return
    if not message.photo:
        msg = bot.send_message(message.chat.id, "⚠️ خطا! فقط تصویر فیش ارسال کنید:")
        bot.register_next_step_handler(msg, process_payment_step, gb, username, total_price)
        return
    photo_id = message.photo[-1].file_id
    
    execute_db("INSERT INTO orders (user_id, username, gb_amount, total_price, receipt_file_id) VALUES (?, ?, ?, ?, ?)", (message.chat.id, username, gb, total_price, photo_id))
    order_id = query_db("SELECT order_id FROM orders WHERE user_id=? AND username=? ORDER BY order_id DESC LIMIT 1", (message.chat.id, username), one=True)[0]
    
    bot.send_message(message.chat.id, "✅ رسید شما دریافت شد. پس از تایید مدیریت، لینک را دریافت خواهید کرد.", reply_markup=main_keyboard(message.from_user.id))
    
    admin_text = f"🔔 **سفارش جدید خرید دستی**\n\n🆔 شناسه سفارش: {order_id}\n👤 کاربر: {message.chat.id}\n🏷 نام کاربری: `{username}`\n📦 حجم: {gb} گیگ\n💰 مبلغ: {total_price:,} تومان"
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ تایید و ارسال لینک", callback_data=f"approve_{order_id}"), 
        types.InlineKeyboardButton("❌ رد سفارش", callback_data=f"reject_{order_id}")
    )
    bot.send_photo(ADMIN_ID, photo_id, caption=admin_text, reply_markup=markup, parse_mode="Markdown")

# ----------------- بخش حساب کاربری -----------------
@bot.message_handler(func=lambda msg: msg.text == "👤 حساب کاربری")
@check_join_decorator
def account_handler(message):
    user_id = message.chat.id
    
    user_data = query_db("SELECT personal_discount, last_trial_time, balance FROM users WHERE user_id=?", (user_id,), one=True)
    if not user_data:
        execute_db("INSERT OR IGNORE INTO users (user_id, last_trial_time, balance) VALUES (?, NULL, 0)", (user_id,))
        user_data = (0, None, 0)
        
    personal_discount = user_data[0]
    last_trial = user_data[1]
    balance = user_data[2]
    
    stats = query_db("SELECT COUNT(*), SUM(total_price), SUM(gb_amount) FROM orders WHERE user_id=? AND status='approved'", (user_id,), one=True)
    active_services = stats[0] if stats[0] else 0
    total_paid = stats[1] if stats[1] else 0
    total_gbs = stats[2] if stats[2] else 0
    
    if not last_trial:
        trial_status = "🟢 آماده دریافت"
    else:
        last_trial_dt = datetime.strptime(last_trial, "%Y-%m-%d %H:%M:%S")
        if datetime.now() - last_trial_dt >= timedelta(days=7):
            trial_status = "🟢 آماده دریافت"
        else:
            trial_status = "🔴 دریافت شده (محدودیت زمانی یک هفته)"
            
    text = f"👤 **داشبورد حساب کاربری شما**\n\n" \
           f"🆔 **شناسه عددی شما:** `{user_id}`\n" \
           f"💳 **موجودی کیف پول:** **{balance:,} تومان**\n" \
           f"💎 **تخفیف شخصی شما:** {personal_discount}%\n\n" \
           f"📊 **آمار خریدها:**\n" \
           f"📦 تعداد سرویس‌های فعال: {active_services} عدد\n" \
           f"📶 مجموع حجم خرید: {total_gbs} گیگابایت\n" \
           f"💰 کل خریدهای تایید شده: {total_paid:,} تومان\n\n" \
           f"🎁 **تست رایگان:** {trial_status}"
           
    bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=return_keyboard())

# ----------------- بخش آموزش، سوالات و پشتیبانی -----------------
@bot.message_handler(func=lambda msg: msg.text == "📚 کانال آموزش")
@check_join_decorator
def tutorials_handler(message):
    markup = types.InlineKeyboardMarkup()
    btn_tutorial = types.InlineKeyboardButton("🔗 ورود به کانال آموزش", url=TUTORIAL_CHANNEL_LINK)
    markup.add(btn_tutorial)
    bot.send_message(message.chat.id, "📚 جهت مشاهده کامل آموزش‌ها دکمه زیر را لمس کنید:", reply_markup=markup)
    bot.send_message(message.chat.id, "با استفاده از دکمه زیر به منوی اصلی بازگردید:", reply_markup=return_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "📞 تماس با پشتیبانی")
@check_join_decorator
def support_handler(message):
    markup = types.InlineKeyboardMarkup()
    btn_supp = types.InlineKeyboardButton("✉️ ارتباط مستقیم با پشتیبان", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}")
    markup.add(btn_supp)
    bot.send_message(message.chat.id, f"📞 سوال یا تمدیدی دارید؟ از دکمه زیر استفاده کنید:\n\n👤 پشتیبان رسمی: {SUPPORT_USERNAME}", reply_markup=markup)
    bot.send_message(message.chat.id, "با دکمه زیر به منوی اصلی بازگردید:", reply_markup=return_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "❓ سوالات متداول")
@check_join_decorator
def faq_handler(message):
    faq = query_db("SELECT value FROM settings WHERE key='faq'", one=True)[0]
    bot.send_message(message.chat.id, f"❓ **سوالات متداول**\n\n{faq}", parse_mode="Markdown", reply_markup=return_keyboard())

# ----------------- تمدید سرویس -----------------
@bot.message_handler(func=lambda msg: msg.text == "🔄 تمدید سرویس")
@check_join_decorator
def extend_service_start(message):
    user_id = message.chat.id
    active_configs = query_db("SELECT username FROM orders WHERE user_id=? AND status='approved'", (user_id,))
    
    if not active_configs:
        bot.send_message(user_id, "⚠️ شما در حال حاضر هیچ سرویس فعالی جهت تمدید ندارید.", reply_markup=main_keyboard(user_id))
        return
        
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for cfg in active_configs:
        markup.add(types.KeyboardButton(f"⚙️ سرویس: {cfg[0]}"))
    markup.add(types.KeyboardButton("🔙 بازگشت به منوی اصلی"))
    
    msg = bot.send_message(user_id, "سرویس مورد نظر جهت تمدید یا افزایش حجم را انتخاب کنید:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_select_config_for_extend)

def process_select_config_for_extend(message):
    user_id = message.chat.id
    text = message.text.strip()
    
    if text == "🔙 بازگشت به منوی اصلی":
        back_to_main_handler(message)
        return
        
    if not text.startswith("⚙️ سرویس: "):
        msg = bot.send_message(user_id, "⚠️ لطفاً از دکمه‌ها برای انتخاب سرویس استفاده کنید:")
        bot.register_next_step_handler(msg, process_select_config_for_extend)
        return
        
    selected_username = text.replace("⚙️ سرویس: ", "").strip()
    
    msg = bot.send_message(
        user_id, 
        f"سرویس `{selected_username}` انتخاب شد.\nلطفاً میزان حجم افزایشی (بین ۱ تا ۱۰۰ گیگ) را وارد کنید:",
        reply_markup=cancel_extension_keyboard()
    )
    bot.register_next_step_handler(msg, process_extend_gb_amount, selected_username)

def process_extend_gb_amount(message, username):
    user_id = message.chat.id
    text = message.text.strip()
    
    if text == "❌ لغو تمدید":
        bot.send_message(user_id, "❌ روند لغو شد.", reply_markup=main_keyboard(user_id))
        return
        
    try:
        gb = int(text)
        if gb < 1 or gb > 100:
            raise ValueError
    except ValueError:
        msg = bot.send_message(user_id, "⚠️ خطا! فقط یک عدد معتبر بین ۱ تا ۱۰۰ وارد کنید:")
        bot.register_next_step_handler(msg, process_extend_gb_amount, username)
        return
        
    price_per_gb = int(query_db("SELECT value FROM settings WHERE key='price_per_gb'", one=True)[0])
    personal_disc_db = query_db("SELECT personal_discount FROM users WHERE user_id=?", (user_id,), one=True)
    personal_discount = personal_disc_db[0] if personal_disc_db else 0
    
    base_price = gb * price_per_gb
    final_price = int(base_price * (1 - (personal_discount / 100)))
    
    user_balance = query_db("SELECT balance FROM users WHERE user_id=?", (user_id,), one=True)[0]
    
    if user_balance >= final_price:
        execute_db("UPDATE users SET balance = balance - ? WHERE user_id=?", (final_price, user_id))
        execute_db("UPDATE orders SET gb_amount = gb_amount + ? WHERE username=?", (gb, username))
        config_link = query_db("SELECT config_link FROM orders WHERE username=?", (username,), one=True)[0]
        
        user_success_text = f"🎉 **سرویس شما با موفقیت تمدید و شارژ شد!**\n\n" \
                            f"🏷 سرویس: `{username}`\n" \
                            f"➕ مقدار **{gb} گیگابایت** از موجودی کیف پول شما کسر و به کانفیگ متصل شد.\n\n" \
                            f"🔗 **ساب‌لینک شما بدون نیاز به تغییر فعال است:**\n" \
                            f"`{config_link}`"
        bot.send_message(user_id, user_success_text, parse_mode="Markdown", reply_markup=main_keyboard(user_id))
        
        # معرف برای تمدید هم پورسانت ۱۰ درصد دریافت می‌کند
        apply_purchase_referral_bonus(user_id, final_price)
        
        bot.send_message(ADMIN_ID, f"⚡️ **تمدید خودکار با کیف پول**:\nکاربر {user_id} حجم سرویس `{username}` را به اندازه {gb} گیگ تمدید کرد و کل هزینه ({final_price:,} تومان) از حسابش کسر شد. لطفاً در پنل خود نیز حجم را دستی اضافه کنید.")
    else:
        card_num = query_db("SELECT value FROM settings WHERE key='card_number'", one=True)[0]
        card_holder = query_db("SELECT value FROM settings WHERE key='card_holder'", one=True)[0]
        
        checkout_text = f"🔄 **جزئیات فاکتور افزایش حجم و تمدید:**\n\n" \
                        f"🏷 نام کاربری سرویس: `{username}`\n" \
                        f"➕ حجم درخواستی: {gb} گیگابایت\n" \
                        f"💵 **مبلغ نهایی پرداخت: {final_price:,} تومان**\n\n" \
                        f"💳 شماره کارت جهت واریز:\n" \
                        f"`{card_num}`\n" \
                        f"👤 به نام: {card_holder}\n\n" \
                        f"⚠️ پس از واریز، عکس رسید خود را ارسال کنید:"
                        
        msg = bot.send_message(user_id, checkout_text, parse_mode="Markdown", reply_markup=cancel_extension_keyboard())
        bot.register_next_step_handler(msg, process_extend_payment, username, gb, final_price)

def process_extend_payment(message, username, gb, total_price):
    user_id = message.chat.id
    if message.text == "❌ لغو تمدید":
        bot.send_message(user_id, "❌ فرآیند لغو شد.", reply_markup=main_keyboard(user_id))
        return
        
    if not message.photo:
        msg = bot.send_message(user_id, "⚠️ خطا! لطفاً رسید پرداخت واریزی را ارسال کنید:")
        bot.register_next_step_handler(msg, process_extend_payment, username, gb, total_price)
        return
        
    photo_id = message.photo[-1].file_id
    execute_db("INSERT INTO extensions (user_id, username, gb_amount, total_price, receipt_file_id) VALUES (?, ?, ?, ?, ?)", (user_id, username, gb, total_price, photo_id))
    ext_id = query_db("SELECT ext_id FROM extensions WHERE user_id=? AND username=? ORDER BY ext_id DESC LIMIT 1", (user_id, username), one=True)[0]
    
    bot.send_message(user_id, "✅ رسید تمدید دستی ارسال شد و منتظر تایید مدیریت است.", reply_markup=main_keyboard(user_id))
    
    admin_text = f"⚡️ **درخواست تمدید دستی**\n\n🆔 شناسه: {ext_id}\n👤 کاربر: {user_id}\n🏷 سرویس: `{username}`\n➕ حجم: {gb} گیگ\n💰 مبلغ: {total_price:,} تومان"
    markup = types.InlineKeyboardMarkup()
    btn_approve = types.InlineKeyboardButton("✅ تایید و شارژ دستی در سیستم", callback_data=f"appext_{ext_id}")
    btn_reject = types.InlineKeyboardButton("❌ رد درخواست", callback_data=f"rejext_{ext_id}")
    markup.row(btn_approve, btn_reject)
    bot.send_photo(ADMIN_ID, photo_id, caption=admin_text, reply_markup=markup)

# ----------------- بخش تست رایگان -----------------
@bot.message_handler(func=lambda msg: msg.text == "🎁 تست رایگان")
@check_join_decorator
def free_trial_handler(message):
    user_id = message.chat.id
    user = query_db("SELECT last_trial_time FROM users WHERE user_id=?", (user_id,), one=True)
    if not user:
        execute_db("INSERT INTO users (user_id, last_trial_time) VALUES (?, NULL)", (user_id,))
        last_trial = None
    else:
        last_trial = user[0]
        
    if last_trial:
        last_trial_dt = datetime.strptime(last_trial, "%Y-%m-%d %H:%M:%S")
        if datetime.now() - last_trial_dt < timedelta(days=7):
            bot.send_message(user_id, "⚠️ شما در ۷ روز گذشته یک تست رایگان گرفته‌اید و هر هفته مجاز به دریافت ۱ عدد هستید.", reply_markup=return_keyboard())
            return
            
    unused_link = query_db("SELECT id, link FROM test_links WHERE is_used = 0 LIMIT 1", one=True)
    if not unused_link:
        bot.send_message(user_id, "😔 متاسفانه ظرفیت تست‌ها تمام شده است.", reply_markup=return_keyboard())
        return
        
    link_id, link_url = unused_link
    execute_db("UPDATE test_links SET is_used = 1 WHERE id = ?", (link_id,))
    execute_db("UPDATE users SET last_trial_time = ? WHERE user_id = ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
    bot.send_message(user_id, f"🎁 اکانت تست شما:\n\n`{link_url}`", parse_mode="Markdown", reply_markup=return_keyboard())

# ----------------- پنل مدیریت ادمین -----------------
@bot.message_handler(func=lambda msg: msg.text == "⚙️ پنل مدیریت" and msg.chat.id == ADMIN_ID)
def admin_panel_handler(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💵 تغییر قیمت هر گیگابایت", callback_data="admin_price"))
    markup.add(types.InlineKeyboardButton("💳 ویرایش اطلاعات کارت", callback_data="admin_card"))
    markup.add(types.InlineKeyboardButton("➕ شارژ مستقیم کیف پول کاربر", callback_data="admin_wallet_direct"))
    markup.add(types.InlineKeyboardButton("📥 افزودن کانفیگ آماده به ربات", callback_data="admin_premade_add"))
    markup.add(types.InlineKeyboardButton("📊 موجودی کانفیگ‌های آماده", callback_data="admin_premade_status"))
    markup.add(types.InlineKeyboardButton("📥 افزودن لینک‌های تست رایگان", callback_data="admin_add_tests"))
    markup.add(types.InlineKeyboardButton("🏷 تخفیف شخصی کاربر", callback_data="admin_personal_disc"))
    
    price_per_gb = query_db("SELECT value FROM settings WHERE key='price_per_gb'", one=True)[0]
    
    bot.send_message(ADMIN_ID, f"⚙️ **پنل مدیریت پیشرفته Confing**\n\n💵 قیمت پایه هر گیگابایت: {price_per_gb} تومان", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_") and call.message.chat.id == ADMIN_ID)
def admin_callbacks(call):
    bot.answer_callback_query(call.id)
    if call.data == "admin_price":
        msg = bot.send_message(ADMIN_ID, "قیمت جدید هر گیگ را وارد کنید:")
        bot.register_next_step_handler(msg, update_admin_price)
    elif call.data == "admin_card":
        msg = bot.send_message(ADMIN_ID, "اطلاعات کارت: `شماره کارت - نام صاحب کارت`")
        bot.register_next_step_handler(msg, update_admin_card)
    elif call.data == "admin_wallet_direct":
        msg = bot.send_message(ADMIN_ID, "شارژ مستقیم: `شناسه کاربر - مبلغ به تومان` (مثال: `123456789 - 50000`)")
        bot.register_next_step_handler(msg, process_admin_wallet_direct)
    elif call.data == "admin_premade_add":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("10", "20", "30", "40", "50", "100")
        msg = bot.send_message(ADMIN_ID, "برای کدام حجم می‌خواهید ساب‌لینک آماده آپلود کنید؟ حجم را انتخاب یا وارد کنید:", reply_markup=markup)
        bot.register_next_step_handler(msg, process_admin_premade_select_gb)
    elif call.data == "admin_premade_status":
        stats_text = "📊 **موجودی کانفیگ‌های آماده در ربات:**\n\n"
        for gb in [10, 20, 30, 40, 50, 100]:
            count = query_db("SELECT COUNT(*) FROM premade_configs WHERE gb_amount=? AND is_used=0", (gb,), one=True)[0]
            stats_text += f"🔹 حجم {gb} گیگابایت: {count} عدد کانفیگ آماده\n"
        bot.send_message(ADMIN_ID, stats_text)
    elif call.data == "admin_add_tests":
        msg = bot.send_message(ADMIN_ID, "لینک‌های تست را ارسال کنید (هر کدام در یک خط):")
        bot.register_next_step_handler(msg, add_test_links)
    elif call.data == "admin_personal_disc":
        msg = bot.send_message(ADMIN_ID, "تخفیف شخصی: `شناسه کاربر - درصد` (مثال: `123456789 - 15`)")
        bot.register_next_step_handler(msg, apply_personal_discount)

def update_admin_price(message):
    try:
        price = int(message.text.strip())
        execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES ('price_per_gb', ?)", (str(price),))
        bot.send_message(ADMIN_ID, f"✅ قیمت هر گیگابایت با موفقیت به {price:,} تومان تغییر یافت.")
    except Exception:
        bot.send_message(ADMIN_ID, "❌ مقدار نامعتبر است.")

def update_admin_card(message):
    parts = message.text.split("-")
    if len(parts) < 2:
        bot.send_message(ADMIN_ID, "❌ خطا! فرمت نادرست.")
        return
    execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES ('card_number', ?)", (parts[0].strip(),))
    execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES ('card_holder', ?)", (parts[1].strip(),))
    bot.send_message(ADMIN_ID, "✅ اطلاعات کارت آپدیت شد.")

def process_admin_wallet_direct(message):
    try:
        parts = message.text.split("-")
        user_id, amount = int(parts[0].strip()), int(parts[1].strip())
        execute_db("INSERT OR IGNORE INTO users (user_id, last_trial_time, balance) VALUES (?, NULL, 0)", (user_id,))
        execute_db("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        bot.send_message(ADMIN_ID, f"✅ حساب کاربری `{user_id}` به مبلغ {amount:,} تومان شارژ شد.")
        bot.send_message(user_id, f"🎉 حساب شما به صورت مستقیم توسط مدیریت به مبلغ **{amount:,} تومان** شارژ شد.")
    except Exception:
        bot.send_message(ADMIN_ID, "❌ خطا در انجام فرآیند شارژ مستقیم.")

def process_admin_premade_select_gb(message):
    try:
        gb = int(message.text.strip())
        msg = bot.send_message(ADMIN_ID, f"لطفاً ساب‌لینک‌های آماده مربوط به پکیج **{gb} گیگ** را ارسال کنید (هر لینک در یک خط جدید قرار بگیرد):", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, process_admin_premade_save, gb)
    except Exception:
        bot.send_message(ADMIN_ID, "❌ مقدار وارد شده اشتباه است.")

def process_admin_premade_save(message, gb):
    links = [line.strip() for line in message.text.split("\n") if line.strip()]
    added = 0
    skipped = 0
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for link in links:
        try:
            c.execute("INSERT INTO premade_configs (gb_amount, link) VALUES (?, ?)", (gb, link))
            added += 1
        except sqlite3.IntegrityError:
            skipped += 1
    conn.commit()
    conn.close()
    bot.send_message(ADMIN_ID, f"✅ فرآیند ذخیره‌سازی ساب‌لینک‌های {gb} گیگ به اتمام رسید.\n📥 ذخیره شد: {added} عدد\n⚠️ تکراری: {skipped}", reply_markup=main_keyboard(ADMIN_ID))

def add_test_links(message):
    links = [line.strip() for line in message.text.split("\n") if line.strip()]
    added = 0
    skipped = 0
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for link in links:
        try:
            c.execute("INSERT INTO test_links (link) VALUES (?)", (link,))
            added += 1
        except sqlite3.IntegrityError:
            skipped += 1
    conn.commit()
    conn.close()
    bot.send_message(ADMIN_ID, f"📊 گزارش ثبت لینک‌های تست:\n📥 موفق: {added}\n⚠️ تکراری: {skipped}")

def apply_personal_discount(message):
    try:
        parts = message.text.split("-")
        user_id, discount = int(parts[0].strip()), int(parts[1].strip())
        execute_db("INSERT OR IGNORE INTO users (user_id, last_trial_time, balance) VALUES (?, NULL, 0)", (user_id,))
        execute_db("UPDATE users SET personal_discount = ? WHERE user_id = ?", (discount, user_id))
        bot.send_message(ADMIN_ID, f"✅ تخفیف {discount}% برای کاربر `{user_id}` ست شد.")
    except Exception:
        bot.send_message(ADMIN_ID, "❌ خطا در انجام اعمال تخفیف شخصی.")

# ----------------- عملیات تایید/رد تمدید دستی توسط ادمین -----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("appext_"))
def admin_approve_extension(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ عدم دسترسی", show_alert=True)
        return
        
    try:
        ext_id = int(call.data.split("_")[1])
        ext_data = query_db("SELECT status, user_id, username, gb_amount FROM extensions WHERE ext_id=?", (ext_id,), one=True)
        
        if not ext_data:
            bot.answer_callback_query(call.id, "❌ خطا: یافت نشد.", show_alert=True)
            return
        if ext_data[0] != 'pending':
            bot.answer_callback_query(call.id, "⚠️ قبلاً تایید یا رد شده است.", show_alert=True)
            return
            
        bot.answer_callback_query(call.id, "شارژ در سیستم ثبت شد.")
        user_id, username, gb = ext_data[1], ext_data[2], ext_data[3]
        
        execute_db("UPDATE extensions SET status='approved' WHERE ext_id=?", (ext_id,))
        execute_db("UPDATE orders SET gb_amount = gb_amount + ? WHERE username=?", (gb, username))
        config_link = query_db("SELECT config_link FROM orders WHERE username=?", (username,), one=True)[0]
        
        user_msg = f"🎉 **تمدید سرویس شما تایید شد!**\n\n" \
                   f"🏷 سرویس: `{username}`\n" \
                   f"➕ مقدار **{gb} گیگابایت** به سرویس شما اضافه شد.\n\n" \
                   f"🔗 **ساب‌لینک شما بدون تغییر فعال است:**\n`{config_link}`"
                   
        try:
            bot.send_message(user_id, user_msg, parse_mode="Markdown")
            
            # معرف بابت تمدید هم پورسانت می‌گیرد (محاسبه پورسانت ۱۰ درصد بر اساس قیمت تراکنش تمدید)
            total_price_data = query_db("SELECT total_price FROM extensions WHERE ext_id=?", (ext_id,), one=True)
            if total_price_data:
                apply_purchase_referral_bonus(user_id, total_price_data[0])
                
            bot.send_message(ADMIN_ID, f"✅ درخواست تمدید #{ext_id} اعمال شد. حالا می‌توانید در پنل اصلی نیز حجم ساب‌لینک را شارژ دستی نمایید.")
        except Exception as e:
            bot.send_message(ADMIN_ID, f"❌ خطا: {e}")
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ خطا: {e}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("rejext_"))
def admin_reject_extension(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ عدم دسترسی", show_alert=True)
        return
        
    try:
        ext_id = int(call.data.split("_")[1])
        ext_data = query_db("SELECT status, user_id FROM extensions WHERE ext_id=?", (ext_id,), one=True)
        
        if not ext_data:
            bot.answer_callback_query(call.id, "❌ یافت نشد.", show_alert=True)
            return
        if ext_data[0] != 'pending':
            bot.answer_callback_query(call.id, "⚠️ رسیدگی شده است.", show_alert=True)
            return
            
        bot.answer_callback_query(call.id)
        msg = bot.send_message(ADMIN_ID, f"علت رد تمدید #{ext_id} را وارد کنید:")
        bot.register_next_step_handler(msg, process_admin_reject_ext, ext_id, ext_data[1])
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ خطا: {e}", show_alert=True)

def process_admin_reject_ext(message, ext_id, user_id):
    reason = message.text.strip()
    execute_db("UPDATE extensions SET status='rejected' WHERE ext_id=?", (ext_id,))
    try:
        bot.send_message(user_id, f"❌ درخواست تمدید دستی شما رد شد.\n💬 علت: {reason}")
        bot.send_message(ADMIN_ID, "❌ رد شد.")
    except Exception:
        pass

# ----------------- عملیات تایید/رد سفارش اولیه خرید دستی -----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_"))
def admin_approve_order(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ عدم دسترسی", show_alert=True)
        return
        
    try:
        order_id = int(call.data.split("_")[1])
        order = query_db("SELECT status, user_id, username, gb_amount, total_price FROM orders WHERE order_id = ?", (order_id,), one=True)
        
        if not order:
            bot.answer_callback_query(call.id, "❌ سفارش در پایگاه داده یافت نشد.", show_alert=True)
            return
        if order[0] != 'pending':
            bot.answer_callback_query(call.id, f"⚠️ سفارش قبلاً بررسی شده است ({order[0]})", show_alert=True)
            return
            
        bot.answer_callback_query(call.id)
        msg = bot.send_message(ADMIN_ID, f"لینک ساب‌کانفیگ را برای سفارش #{order_id} وارد کنید:")
        bot.register_next_step_handler(msg, process_admin_sublink, order_id, order[1], order[4])
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ خطا: {e}", show_alert=True)

def process_admin_sublink(message, order_id, user_id, total_price):
    config_link = message.text.strip()
    execute_db("UPDATE orders SET status = 'approved', config_link = ? WHERE order_id = ?", (config_link, order_id))
    order = query_db("SELECT gb_amount, username FROM orders WHERE order_id = ?", (order_id,), one=True)
    user_text = f"🎉 **سفارش شما تایید شد!**\n\n📦 حجم: {order[0]} گیگ\n👤 نام کاربری: `{order[1]}`\n🔗 لینک:\n`{config_link}`"
    try:
        bot.send_message(user_id, user_text, parse_mode="Markdown")
        bot.send_message(ADMIN_ID, "✅ تحویل داده شد.")
        
        # معرف بابت خرید دستی هم پورسانت ۱۰ درصد می‌گیرد
        apply_purchase_referral_bonus(user_id, total_price)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("reject_"))
def admin_reject_order(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ عدم دسترسی", show_alert=True)
        return
        
    try:
        order_id = int(call.data.split("_")[1])
        order = query_db("SELECT status, user_id FROM orders WHERE order_id = ?", (order_id,), one=True)
        
        if not order:
            bot.answer_callback_query(call.id, "❌ یافت نشد.", show_alert=True)
            return
        if order[0] != 'pending':
            bot.answer_callback_query(call.id, "⚠️ رسیدگی شده است.", show_alert=True)
            return
            
        bot.answer_callback_query(call.id)
        msg = bot.send_message(ADMIN_ID, f"علت رد سفارش #{order_id} را بنویسید:")
        bot.register_next_step_handler(msg, process_admin_reject, order_id, order[1])
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ خطا: {e}", show_alert=True)

def process_admin_reject(message, order_id, user_id):
    reason = message.text.strip()
    execute_db("UPDATE orders SET status = 'rejected' WHERE order_id = ?", (order_id,))
    try:
        bot.send_message(user_id, f"❌ سفارش شما رد شد.\n💬 علت: {reason}")
        bot.send_message(ADMIN_ID, "❌ رد شد.")
    except Exception:
        pass

# ----------------- شروع اجرای ربات -----------------
if __name__ == '__main__':
    # دریافت یوزرنیم ربات به صورت پویا در زمان استارت برای ساخت دقیق لینک‌های دعوت
    try:
        bot_info = bot.get_me()
        BOT_USERNAME = bot_info.username
        print(f"Bot is starting as @{BOT_USERNAME}...")
    except Exception as e:
        print(f"Error getting bot username: {e}")
        
    bot.infinity_polling()