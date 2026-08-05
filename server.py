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
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            return {"answer": "کلید API تنظیم نشده است"}
        
        question = request.get("question", "")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "google/gemini-2.5-flash-lite-preview-06-2025",
                    "messages": [
                        {"role": "system", "content": "تو یک تحلیلگر بازار ارز دیجیتال هستی. همیشه فارسی و خلاصه جواب بده."},
                        {"role": "user", "content": question}
                    ]
                },
                timeout=30.0
            )
            data = response.json()
            answer = data.get("choices", [{}])[0].get("message", {}).get("content", "خطا در دریافت پاسخ")
            return {"answer": answer}
    except Exception as e:
        return {"answer": f"خطا: {str(e)}"}

@app.get("/api/news")
async def get_news():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://news.google.com/rss/search?q=cryptocurrency+bitcoin+OR+ethereum+OR+altcoin&hl=en-US&gl=US&ceid=US:en&num=15",
                timeout=10.0
            )
            return {"rss": response.text}
    except:
        return {"rss": ""}
