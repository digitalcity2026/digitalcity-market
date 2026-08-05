from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok", "message": "DigitalCity Market API"}

@app.get("/api/prices")
async def get_prices():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd", "order": "market_cap_desc",
                    "per_page": 50, "page": 1, "sparkline": "false",
                    "price_change_percentage": "24h"
                }, timeout=10.0
            )
            return response.json()
    except:
        return []

@app.post("/api/ask-ai")
async def ask_ai(request: dict):
    try:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return {"answer": "کلید API تنظیم نشده است"}
        
        question = request.get("question", "")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
                json={"contents": [{"parts": [{"text": f"به فارسی و خلاصه پاسخ بده:\n\n{question}"}]}]},
                timeout=30.0
            )
            data = response.json()
            answer = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "خطا")
            return {"answer": answer}
    except Exception as e:
        return {"answer": f"خطا: {str(e)}"}

# ========== endpoint جدید برای اخبار ==========
@app.get("/api/news")
async def get_news():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://news.google.com/rss/search?q=cryptocurrency+bitcoin+OR+ethereum+OR+altcoin&hl=en-US&gl=US&ceid=US:en&num=15",
                timeout=10.0
            )
            # برگردوندن raw XML - توی جاوااسکریپت parse می‌کنیم
            return {"rss": response.text}
    except:
        return {"rss": ""}
