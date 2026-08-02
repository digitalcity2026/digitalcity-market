import os
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

TOKEN = os.getenv("BOT_TOKEN", "8631947965:AAGc9y7vcfeEtIsj4_yt7-2OpDq7a5NklHM")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 به DigitalCity Market خوش آمدید!\n\n"
        "📊 اسم ارز رو بفرستید تا قیمتش رو بدم\n"
        "📊 چند ارز با کاما جدا کنید: btc,eth,doge\n"
        "🏆 /top - ۱۰ ارز برتر\n"
        "❓ /help - راهنما"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 راهنما:\n\n"
        "✨ کافیه اسم ارز رو بفرستی:\n"
        "`bitcoin` یا `btc`\n\n"
        "✨ چند ارز با کاما:\n"
        "`btc, eth, doge`\n\n"
        "✨ دستورات:\n"
        "/top - ۱۰ ارز برتر بازار"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # چک کن متن شبیه دستور نباشه
    if text.startswith('/'):
        return
    
    coins_list = [c.strip().lower() for c in text.split(",")]
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "ids": ",".join(coins_list[:10]),
                    "order": "market_cap_desc",
                    "sparkline": "false",
                    "price_change_percentage": "24h"
                },
                timeout=10.0
            )
            data = response.json()
            
            if not data:
                await update.message.reply_text("❌ ارز مورد نظر پیدا نشد!")
                return
            
            for coin in data:
                change = coin.get("price_change_percentage_24h", 0)
                emoji = "🟢" if change >= 0 else "🔴"
                price = coin.get("current_price", 0)
                if price >= 1:
                    price_str = f"${price:,.2f}"
                elif price >= 0.01:
                    price_str = f"${price:.4f}"
                else:
                    price_str = f"${price:.8f}"
                
                await update.message.reply_text(
                    f"{emoji} **{coin['name']} ({coin['symbol'].upper()})**\n"
                    f"💰 قیمت: {price_str}\n"
                    f"📊 تغییر ۲۴h: {change:+.2f}%\n"
                    f"🏆 رتبه: #{coin.get('market_cap_rank', 'N/A')}"
                )
    except Exception as e:
        pass

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 10,
                    "page": 1,
                    "sparkline": "false",
                    "price_change_percentage": "24h"
                },
                timeout=10.0
            )
            data = response.json()
            
            msg = "🏆 **۱۰ ارز برتر بازار:**\n\n"
            for i, coin in enumerate(data, 1):
                change = coin.get("price_change_percentage_24h", 0)
                emoji = "🟢" if change >= 0 else "🔴"
                price = coin.get("current_price", 0)
                if price >= 1:
                    price_str = f"${price:,.2f}"
                else:
                    price_str = f"${price:.6f}"
                msg += f"{i}. {emoji} {coin['name']} - {price_str} ({change:+.2f}%)\n"
            
            await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text("⚠️ خطا در دریافت اطلاعات.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ ربات DigitalCity Market شروع به کار کرد...")
    app.run_polling()

if __name__ == "__main__":
    main()
