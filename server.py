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

# ========== CoinGlass Endpoints ==========
COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY", "")

@app.get("/api/coinglass/funding")
async def get_funding():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://open-api.coinglass.com/public/v2/funding_rates",
                headers={"CG-API-KEY": COINGLASS_API_KEY},
                timeout=10.0
            )
            return response.json()
    except:
        return {}

@app.get("/api/coinglass/liquidation")
async def get_liquidation():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://open-api.coinglass.com/public/v2/liquidation/info?time_type=h1",
                headers={"CG-API-KEY": COINGLASS_API_KEY},
                timeout=10.0
            )
            return response.json()
    except:
        return {}

@app.get("/api/coinglass/sentiment")
async def get_sentiment():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://open-api.coinglass.com/public/v2/fear_greed",
                headers={"CG-API-KEY": COINGLASS_API_KEY},
                timeout=10.0
            )
            return response.json()
    except:
        return {}

# ========== Watchlist Endpoints ==========
@app.get("/api/watchlist/{user_id}")
async def get_watchlist(user_id: str):
    import json
    data_file = "data.json"
    if not os.path.exists(data_file):
        return {"watchlist": []}
    with open(data_file, 'r') as f:
        data = json.load(f)
    return {"watchlist": data.get("watchlists", {}).get(user_id, [])}

@app.post("/api/watchlist/{user_id}")
async def add_to_watchlist(user_id: str, coin: dict):
    import json
    data_file = "data.json"
    if not os.path.exists(data_file):
        data = {"watchlists": {}}
    else:
        with open(data_file, 'r') as f:
            data = json.load(f)
    if user_id not in data.get("watchlists", {}):
        data["watchlists"][user_id] = []
    if not any(c["id"] == coin["id"] for c in data["watchlists"][user_id]):
        data["watchlists"][user_id].append(coin)
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=2)
    return {"status": "success"}

@app.delete("/api/watchlist/{user_id}/{coin_id}")
async def remove_from_watchlist(user_id: str, coin_id: str):
    import json
    data_file = "data.json"
    if os.path.exists(data_file):
        with open(data_file, 'r') as f:
            data = json.load(f)
        if user_id in data.get("watchlists", {}):
            data["watchlists"][user_id] = [c for c in data["watchlists"][user_id] if c["id"] != coin_id]
            with open(data_file, 'w') as f:
                json.dump(data, f, indent=2)
    return {"status": "success"}
