import os
import random
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters
import asyncio

# Database setup
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (user_id INTEGER, task TEXT, date TEXT, status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reminders
                 (user_id INTEGER, reminder_time TEXT, message TEXT, chat_id INTEGER)''')
    conn.commit()
    conn.close()

# Load quotes and tips
def load_quotes():
    with open('quotes.txt', 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def load_tips():
    with open('tips.txt', 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

QUOTES = load_quotes()
TIPS = load_tips()

# Helper functions
def get_user_tasks(user_id):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT rowid, task, status FROM tasks WHERE user_id=? AND date=? ORDER BY rowid", 
              (user_id, today))
    tasks = c.fetchall()
    conn.close()
    return tasks

async def start(update: Update, context: CallbackContext):
    welcome = """🌟 Welcome to InspireMate!

I'm your personal motivation and productivity companion. Let's make today amazing!

🔥 What would you like to do?
• /quote - Get inspired
• /tip - Learn productivity hacks
• /task - Add a new task
• /mytasks - See your tasks
• /daily - Your daily inspiration

Type /help to see all commands!

Remember: Small steps lead to big achievements! 💪"""
    
    keyboard = [[
        InlineKeyboardButton("✨ Get Quote", callback_data='quote'),
        InlineKeyboardButton("💡 Get Tip", callback_data='tip')
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome, reply_markup=reply_markup)

async def help_command(update: Update, context: CallbackContext):
    help_text = """📚 *InspireMate Commands*

/start - Start the bot
/help - Show this help message
/quote - Get a motivational quote
/tip - Get a productivity tip
/task [your task] - Add a task (e.g., /task Finish project report)
/mytasks - View your current tasks
/done [task number] - Complete a task (e.g., /done 1)
/reminder [time] [message] - Set a reminder (e.g., /reminder 15:30 Meeting)
/daily - Get your daily inspiration
/about - About this bot

*Tips:*
• Use /task to add what you want to accomplish
• Check /mytasks to stay on track
• Set /reminder for important deadlines

Stay productive! 🌟"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def about(update: Update, context: CallbackContext):
    about_text = """🤖 *About InspireMate*

InspireMate is a simple yet powerful bot designed to boost your productivity and keep you motivated throughout the day.

*Features:*
• Daily motivational quotes
• Productivity tips and hacks
• Task management system
• Reminder system
• Daily inspiration

*Made with ❤️ for the Telegram community*

Version: 1.0.0

Remember: Consistency is key to success! 🚀"""
    
    await update.message.reply_text(about_text, parse_mode='Markdown')

async def quote(update: Update, context: CallbackContext):
    quote = random.choice(QUOTES)
    await update.message.reply_text(f"💭 *Quote of the moment*\n\n_{quote}_", parse_mode='Markdown')

async def tip(update: Update, context: CallbackContext):
    tip = random.choice(TIPS)
    await update.message.reply_text(f"💡 *Productivity Tip*\n\n{tip}", parse_mode='Markdown')

async def add_task(update: Update, context: CallbackContext):
    if not context.args:
        await update.message.reply_text("❌ Please specify a task.\nExample: /task Finish my report")
        return
    
    task_text = ' '.join(context.args)
    user_id = update.effective_user.id
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("INSERT INTO tasks (user_id, task, date, status) VALUES (?, ?, ?, ?)",
              (user_id, task_text, today, 'pending'))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ Task added successfully!\n📝 {task_text}")

async def my_tasks(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    tasks = get_user_tasks(user_id)
    
    if not tasks:
        await update.message.reply_text("🎉 No pending tasks today! You're all caught up!")
        return
    
    task_list = "📋 *Your Tasks Today:*\n\n"
    for task_id, task, status in tasks:
        status_emoji = "✅" if status == 'done' else "⬜"
        task_list += f"{status_emoji} {task_id}. {task}\n"
    
    await update.message.reply_text(task_list, parse_mode='Markdown')

async def done_task(update: Update, context: CallbackContext):
    if not context.args:
        await update.message.reply_text("❌ Please specify which task to mark as done.\nExample: /done 1")
        return
    
    try:
        task_num = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid task number.")
        return
    
    user_id = update.effective_user.id
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    
    # Check if task exists
    c.execute("SELECT rowid, task, status FROM tasks WHERE user_id=? AND date=? AND rowid=?",
              (user_id, today, task_num))
    task = c.fetchone()
    
    if not task:
        await update.message.reply_text("❌ Task not found. Use /mytasks to see your tasks.")
        conn.close()
        return
    
    if task[2] == 'done':
        await update.message.reply_text(f"✅ Task '{task[1]}' is already completed!")
        conn.close()
        return
    
    c.execute("UPDATE tasks SET status='done' WHERE rowid=?", (task_num,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"🎉 Great job! Task '{task[1]}' completed!")

async def set_reminder(update: Update, context: CallbackContext):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Please specify time and message.\nExample: /reminder 15:30 Meeting with team")
        return
    
    time_str = context.args[0]
    message = ' '.join(context.args[1:])
    
    try:
        reminder_time = datetime.strptime(time_str, '%H:%M').time()
        now = datetime.now()
        reminder_datetime = datetime.combine(now.date(), reminder_time)
        
        if reminder_datetime < now:
            reminder_datetime += timedelta(days=1)
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute("INSERT INTO reminders (user_id, reminder_time, message, chat_id) VALUES (?, ?, ?, ?)",
                  (user_id, reminder_datetime.strftime('%Y-%m-%d %H:%M:%S'), message, chat_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"⏰ Reminder set for {reminder_datetime.strftime('%H:%M')}!\n📝 {message}")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid time format. Please use HH:MM (24-hour format).")

async def daily_inspiration(update: Update, context: CallbackContext):
    quote = random.choice(QUOTES)
    tip = random.choice(TIPS)
    
    message = f"""🌅 *Your Daily Inspiration*

💭 *Quote of the Day:*
_{quote}_

💡 *Today's Productivity Tip:*
{tip}

✨ Remember: Every day is a new opportunity to grow!

Make today count! 🚀"""
    
    await update.message.reply_text(message, parse_mode='Markdown')

# Background reminder checker
def check_reminders():
    while True:
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn = sqlite3.connect('tasks.db')
            c = conn.cursor()
            
            # Get reminders due in the next minute
            time_until = (datetime.now() + timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')
            c.execute("SELECT * FROM reminders WHERE reminder_time BETWEEN ? AND ?",
                      (now, time_until))
            reminders = c.fetchall()
            
            for reminder in reminders:
                # Send reminder
                # This would require the application instance
                # We'll implement this differently
                pass
            
            conn.close()
            time.sleep(60)
        except Exception as e:
            print(f"Reminder check error: {e}")
            time.sleep(60)

# Callback query handler
async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'quote':
        quote = random.choice(QUOTES)
        await query.edit_message_text(f"💭 *Quote*\n\n_{quote}_", parse_mode='Markdown')
    elif query.data == 'tip':
        tip = random.choice(TIPS)
        await query.edit_message_text(f"💡 *Tip*\n\n{tip}", parse_mode='Markdown')

# Error handler
async def error_handler(update: Update, context: CallbackContext):
    print(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("⚠️ Something went wrong. Please try again later.")

def main():
    # Initialize database
    init_db()
    
    # Get token from environment variable
    TOKEN = os.environ.get('BOT_TOKEN')
    if not TOKEN:
        print("Please set BOT_TOKEN environment variable")
        return
    
    # Create application
    app = Application.builder().token(TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(CommandHandler("tip", tip))
    app.add_handler(CommandHandler("task", add_task))
    app.add_handler(CommandHandler("mytasks", my_tasks))
    app.add_handler(CommandHandler("done", done_task))
    app.add_handler(CommandHandler("reminder", set_reminder))
    app.add_handler(CommandHandler("daily", daily_inspiration))
    
    # Add callback handler
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Add error handler
    app.add_error_handler(error_handler)
    
    # Start bot
    print("Bot is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
