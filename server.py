import os
import json
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"watchlists": {}, "alerts": {}}
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app.get("/api/prices")
async def get_prices():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 50,
                    "page": 1,
                    "sparkline": "false",
                    "price_change_percentage": "24h"
                },
                timeout=10.0
            )
            return response.json()
    except:
        return []

@app.get("/api/search")
async def search_coins(q: str = ""):
    if not q or len(q) < 2:
        return []
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/search",
                params={"query": q},
                timeout=10.0
            )
            data = response.json()
            
            if data.get("coins") and len(data["coins"]) > 0:
                ids = [c["id"] for c in data["coins"][:30]]
                market_response = await client.get(
                    "https://api.coingecko.com/api/v3/coins/markets",
                    params={
                        "vs_currency": "usd",
                        "ids": ",".join(ids),
                        "order": "market_cap_desc",
                        "sparkline": "false",
                        "price_change_percentage": "24h"
                    },
                    timeout=10.0
                )
                return market_response.json()
            return []
    except:
        return []

@app.get("/api/watchlist/{user_id}")
async def get_watchlist(user_id: str):
    data = load_data()
    return {"watchlist": data["watchlists"].get(user_id, [])}

@app.post("/api/watchlist/{user_id}")
async def add_to_watchlist(user_id: str, coin: dict):
    data = load_data()
    if user_id not in data["watchlists"]:
        data["watchlists"][user_id] = []
    if not any(c["id"] == coin["id"] for c in data["watchlists"][user_id]):
        data["watchlists"][user_id].append(coin)
        save_data(data)
    return {"status": "success"}

@app.delete("/api/watchlist/{user_id}/{coin_id}")
async def remove_from_watchlist(user_id: str, coin_id: str):
    data = load_data()
    if user_id in data["watchlists"]:
        data["watchlists"][user_id] = [c for c in data["watchlists"][user_id] if c["id"] != coin_id]
        save_data(data)
    return {"status": "success"}

@app.post("/api/alerts/{user_id}")
async def set_alert(user_id: str, alert: dict):
    data = load_data()
    if user_id not in data["alerts"]:
        data["alerts"][user_id] = []
    alert["id"] = f"{user_id}_{len(data['alerts'][user_id])}_{datetime.now().timestamp()}"
    alert["active"] = True
    data["alerts"][user_id].append(alert)
    save_data(data)
    return {"status": "success", "alert": alert}

@app.delete("/api/alerts/{user_id}/{alert_id}")
async def delete_alert(user_id: str, alert_id: str):
    data = load_data()
    if user_id in data["alerts"]:
        data["alerts"][user_id] = [a for a in data["alerts"][user_id] if a["id"] != alert_id]
        save_data(data)
    return {"status": "success"}

@app.get("/api/alerts/{user_id}")
async def get_alerts(user_id: str):
    data = load_data()
    return {"alerts": data["alerts"].get(user_id, [])}

# ========== Gemini AI Endpoint ==========
@app.post("/api/ask-ai")
async def ask_ai(request: dict):
    try:
        api_key = os.getenv("GEMINI_API_KEY", "")
        question = request.get("question", "")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
                json={
                    "contents": [{"parts": [{"text": f"تو یک تحلیلگر حرفه‌ای بازار ارزهای دیجیتال هستی. لطفاً به سوال زیر به فارسی و با توضیح کامل پاسخ بده:\n\n{question}"}]}]
                },
                timeout=30.0
            )
            data = response.json()
            answer = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "خطا در دریافت پاسخ")
            return {"answer": answer}
    except:
        return {"answer": "⚠️ خطا در ارتباط با هوش مصنوعی. لطفاً دوباره تلاش کنید."}
