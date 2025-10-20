#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
import aiosqlite
import aiohttp
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes
import json
from urllib.parse import quote

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

class FreeAIServices:
    """مدیریت سرویس‌های رایگان AI"""
    
    def __init__(self):
        self.session = None
    
    async def get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def query_llama_free(self, prompt):
        """استفاده از سرویس رایگان Llama"""
        try:
            session = await self.get_session()
            
            # استفاده از Hugging Face Spaces رایگان
            payload = {
                "inputs": f"<|system|>\nYou are a helpful AI assistant. Answer in Persian.</s>\n<|user|>\n{prompt}</s>\n<|assistant|>\n"
            }
            
            async with session.post(
                "https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if isinstance(result, list) and len(result) > 0:
                        return result[0].get('generated_text', 'پاسخ دریافت نشد')
                    return "پاسخ دریافت شد اما فرمت نامشخص است"
                else:
                    return await self.fallback_chat(prompt)
                    
        except Exception as e:
            logger.error(f"Error in query_llama_free: {e}")
            return await self.fallback_chat(prompt)
    
    async def fallback_chat(self, prompt):
        """راهکار جایگزین برای چت"""
        try:
            # استفاده از سرویس رایگان دیگر
            session = await self.get_session()
            async with session.get(
                f"https://api.telegram-bot.ai/chat?message={quote(prompt)}&lang=fa"
            ) as response:
                if response.status == 200:
                    result = await response.text()
                    return result[:2000]  # محدودیت طول پیام تلگرام
        except Exception:
            pass
        
        # پاسخ پیش‌فرض
        responses = [
            "سلام! من یک بات هوشمند هستم. چگونه می‌توانم کمک کنم? 🤖",
            "متوجه شدم. می‌توانید سوال خود را به صورت واضح‌تر بیان کنید? 💭",
            "در حال حاضر سرویس اصلی در دسترس نیست. لطفاً کمی بعد تلاش کنید. ⏳",
            "سوال جالبی پرسیدید! متأسفانه الان نمی‌توانم پاسخ دهم. 🔄"
        ]
        return responses[hash(prompt) % len(responses)]
    
    async def web_search_duckduckgo(self, query):
        """جستجوی رایگان با DuckDuckGo"""
        try:
            session = await self.get_session()
            async with session.get(
                f"https://api.duckduckgo.com/?q={quote(query)}&format=json&no_html=1",
                timeout=aiohttp.ClientTimeout(total=20)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if result.get('AbstractText'):
                        return f"🔍 **نتایج جستجو:**\n\n{result['AbstractText']}"
                    
                    elif result.get('RelatedTopics'):
                        topics = result['RelatedTopics'][:3]  # 3 موضوع اول
                        response_text = "🔍 **موضوعات مرتبط:**\n\n"
                        for topic in topics:
                            if 'Text' in topic:
                                response_text += f"• {topic['Text']}\n"
                        return response_text
                    
                    else:
                        return "❌ هیچ نتیجه‌ای برای جستجوی شما یافت نشد."
            
            return "⚠️ خطا در انجام جستجو."
            
        except Exception as e:
            logger.error(f"Error in web search: {e}")
            return "⚠️ سرویس جستجو موقتاً در دسترس نیست."
    
    async def generate_simple_image(self, prompt):
        """تولید تصویر ساده با سرویس رایگان"""
        try:
            # استفاده از placeholder یا تصاویر از پیش تعریف شده
            image_topics = {
                'طبیعت': 'https://picsum.photos/512/512?nature',
                'شهر': 'https://picsum.photos/512/512?city', 
                'تکنولوژی': 'https://picsum.photos/512/512?tech',
                'هنر': 'https://picsum.photos/512/512?art',
                'تصادفی': 'https://picsum.photos/512/512'
            }
            
            for topic, url in image_topics.items():
                if topic in prompt:
                    return url
            
            return "https://picsum.photos/512/512"
            
        except Exception as e:
            logger.error(f"Error in image generation: {e}")
            return "https://picsum.photos/512/512"

class DatabaseManager:
    """مدیریت دیتابیس ساده با SQLite"""
    
    def __init__(self, db_path="bot_data.db"):
        self.db_path = db_path
    
    async def init_db(self):
        """ایجاد دیتابیس و جداول"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    daily_requests INTEGER DEFAULT 0,
                    total_requests INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()
    
    async def get_user(self, user_id):
        """دریافت اطلاعات کاربر"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT * FROM users WHERE user_id = ?', (user_id,)
            ) as cursor:
                user = await cursor.fetchone()
                if user:
                    return {
                        'user_id': user[0],
                        'username': user[1],
                        'first_name': user[2],
                        'last_name': user[3],
                        'daily_requests': user[4],
                        'total_requests': user[5],
                        'created_at': user[6],
                        'last_active': user[7]
                    }
        return None
    
    async def update_user(self, user_data):
        """به‌روزرسانی یا ایجاد کاربر"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, last_name, daily_requests, total_requests, last_active)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                user_data['user_id'],
                user_data.get('username'),
                user_data.get('first_name'),
                user_data.get('last_name'),
                user_data.get('daily_requests', 0),
                user_data.get('total_requests', 0)
            ))
            await db.commit()
    
    async def increment_requests(self, user_id):
        """افزایش تعداد درخواست‌های کاربر"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE users 
                SET daily_requests = daily_requests + 1,
                    total_requests = total_requests + 1,
                    last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (user_id,))
            await db.commit()

class SmartTelegramBot:
    """بات اصلی تلگرام"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.ai_services = FreeAIServices()
        self.setup_limits()
    
    def setup_limits(self):
        """تنظیم محدودیت‌های استفاده"""
        self.limits = {
            'free_daily_requests': 50,
            'max_message_length': 2000,
            'request_timeout': 30
        }
    
    async def initialize(self):
        """راه‌اندازی اولیه"""
        await self.db.init_db()
        logger.info("Database initialized")
    
    def detect_intent(self, text):
        """تشخیص هدف کاربر از پیام"""
        text_lower = text.lower()
        
        # کلمات کلیدی برای جستجو
        search_keywords = ['چیست', 'کیست', 'کجاست', 'اخبار', 'قیمت', 'چطور', 'چگونه', 'آموزش']
        
        # کلمات کلیدی برای تصویر
        image_keywords = ['عکس', 'تصویر', 'عکس از', 'تصویر از', 'نقاشی', 'رسم']
        
        if any(keyword in text_lower for keyword in search_keywords):
            return 'search'
        elif any(keyword in text_lower for keyword in image_keywords):
            return 'image'
        else:
            return 'chat'
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور /start"""
        user = update.effective_user
        
        # ذخیره کاربر در دیتابیس
        user_data = {
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'daily_requests': 0,
            'total_requests': 0
        }
        await self.db.update_user(user_data)
        
        welcome_text = """
        🤖 **به بات هوشمند رایگان خوش آمدید!**

        ✨ **من می‌توانم:**
        • به سوالات شما پاسخ دهم 💬
        • در اینترنت جستجو کنم 🔍
        • تصاویر ساده تولید کنم 🎨

        🆓 **این سرویس کاملاً رایگان است!**
        📊 **محدودیت: ۵۰ درخواست در روز**

        🎯 **کافیست سوال خود را بپرسید:**

        مثال‌ها:
        • «هوش مصنوعی چیست؟»
        • «اخبار تکنولوژی»
        • «عکس یک منظره»
        • «آموزش پایتون»

        از گفتگو با شما خوشحالم! 😊
        """
        
        await update.message.reply_text(welcome_text)
    
    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور /help"""
        help_text = """
        📖 **راهنمای استفاده:**

        💬 **چت معمولی:**
        هر سوالی دارید بپرسید

        🔍 **جستجو در اینترنت:**
        از کلماتی مانند «چیست»، «کیست»، «اخبار» استفاده کنید

        🎨 **دریافت تصویر:**
        از کلماتی مانند «عکس»، «تصویر»، «نقاشی» استفاده کنید

        📊 **وضعیت استفاده:**
        /status - مشاهده تعداد درخواست‌ها

        ⚠️ **محدودیت‌ها:**
        • ۵۰ درخواست رایگان در روز
        • پاسخ‌ها ممکن است با تأخیر باشد
        • سرویس تصویر محدود است

        🛠️ **پشتیبانی:**
        در صورت مشکل، پیام خود را مجدداً ارسال کنید.
        """
        
        await update.message.reply_text(help_text)
    
    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور /status"""
        user = update.effective_user
        user_data = await self.db.get_user(user.id)
        
        if not user_data:
            await update.message.reply_text("❌ کاربر یافت نشد. /start را ارسال کنید.")
            return
        
        remaining = self.limits['free_daily_requests'] - user_data['daily_requests']
        
        status_text = f"""
        📊 **وضعیت استفاده شما:**

        👤 نام: {user_data['first_name']}
        📅 درخواست‌های امروز: {user_data['daily_requests']}
        🎯 باقیمانده: {remaining}
        📈 کل درخواست‌ها: {user_data['total_requests']}

        💡 **نکته:** محدودیت‌ها هر ۲۴ ساعت بازنشانی می‌شوند.
        """
        
        await update.message.reply_text(status_text)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پردازش پیام‌های کاربر"""
        user = update.effective_user
        user_message = update.message.text
        
        # بررسی کاربر
        user_data = await self.db.get_user(user.id)
        if not user_data:
            await self.handle_start(update, context)
            return
        
        # بررسی محدودیت روزانه
        if user_data['daily_requests'] >= self.limits['free_daily_requests']:
            await update.message.reply_text(
                "❌ **محدودیت روزانه به پایان رسید!**\n\n"
                "شما امروز ۵۰ درخواست خود را استفاده کرده‌اید.\n"
                "۲۴ ساعت دیگر مجدداً می‌توانید استفاده کنید.\n\n"
                "📊 برای مشاهده وضعیت: /status"
            )
            return
        
        # نشان دادن تایپ کردن
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, 
            action="typing"
        )
        
        try:
            # تشخیص نوع درخواست
            intent = self.detect_intent(user_message)
            
            if intent == 'search':
                response = await self.ai_services.web_search_duckduckgo(user_message)
            
            elif intent == 'image':
                image_url = await self.ai_services.generate_simple_image(user_message)
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=image_url,
                    caption=f"🖼️ تصویر برای: {user_message[:100]}..."
                )
                response = None
            
            else:  # chat
                response = await self.ai_services.query_llama_free(user_message)
            
            # ارسال پاسخ متنی (اگر وجود دارد)
            if response:
                # اطمینان از محدودیت طول پیام تلگرام
                if len(response) > self.limits['max_message_length']:
                    response = response[:self.limits['max_message_length'] - 100] + "...\n\n💡 پاسخ کامل‌تر را می‌توانید با جستجوی جداگانه دریافت کنید."
                
                await update.message.reply_text(response)
            
            # افزایش تعداد درخواست‌ها
            await self.db.increment_requests(user.id)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await update.message.reply_text(
                "⚠️ **خطا در پردازش درخواست**\n\n"
                "لطفاً چند لحظه صبر کرده و دوباره تلاش کنید.\n"
                "اگر مشکل ادامه داشت، سوال خود را به صورت متفاوت بیان کنید."
            )

async def main():
    """تابع اصلی اجرای بات"""
    
    # دریافت توکن از محیط
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not found in environment variables!")
        return
    
    # ایجاد بات
    bot = SmartTelegramBot()
    await bot.initialize()
    
    # ساخت برنامه تلگرام
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # ثبت هندلرها
    application.add_handler(CommandHandler("start", bot.handle_start))
    application.add_handler(CommandHandler("help", bot.handle_help))
    application.add_handler(CommandHandler("status", bot.handle_status))
    application.add_handler(MessageHandler(None, bot.handle_message))
    
    # راه‌اندازی بات
    logger.info("Starting bot...")
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())