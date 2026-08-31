from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import json

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

# ========== Binance Funding Rate (رایگان) ==========
@app.get("/api/coinglass/funding")
async def get_funding():
    try:
        async with httpx.AsyncClient() as client:
            # گرفتن لیست نمادهای معتبر از Binance Futures
            symbols_res = await client.get(
                "https://fapi.binance.com/fapi/v1/exchangeInfo",
                timeout=10.0
            )
            symbols_data = symbols_res.json()
            symbols = [s["symbol"] for s in symbols_data.get("symbols", []) if s.get("status") == "TRADING" and s["symbol"].endswith("USDT")]
            
            # گرفتن funding rate برای همه
            funding_res = await client.get(
                "https://fapi.binance.com/fapi/v1/premiumIndex",
                timeout=10.0
            )
            funding_data = funding_res.json()
            
            # فیلتر فقط USDT pairs
            filtered = [f for f in funding_data if f["symbol"].endswith("USDT")]
            
            # مرتب‌سازی بر اساس funding rate
            filtered.sort(key=lambda x: float(x.get("lastFundingRate", 0)), reverse=True)
            
            return {"data": filtered[:50]}
    except Exception as e:
        return {"error": str(e)}

# ========== Binance Liquidation (رایگان) ==========
@app.get("/api/coinglass/liquidation")
async def get_liquidation():
    try:
        async with httpx.AsyncClient() as client:
            # گرفتن force orders اخیر
            response = await client.get(
                "https://fapi.binance.com/fapi/v1/allForceOrders?limit=50",
                timeout=10.0
            )
            orders = response.json()
            
            # محاسبه مجموع لانگ و شورت
            long_liq = 0
            short_liq = 0
            symbols_liq = {}
            
            for order in orders:
                price = float(order.get("price", 0))
                qty = float(order.get("origQty", 0))
                value = price * qty
                symbol = order.get("symbol", "")
                side = order.get("side", "")
                
                if side == "SELL":
                    long_liq += value
                else:
                    short_liq += value
                
                if symbol not in symbols_liq:
                    symbols_liq[symbol] = {"long": 0, "short": 0}
                if side == "SELL":
                    symbols_liq[symbol]["long"] += value
                else:
                    symbols_liq[symbol]["short"] += value
            
            return {
                "data": {
                    "total": {"long": long_liq, "short": short_liq},
                    "symbols": [{"symbol": k, "total": v} for k, v in symbols_liq.items()]
                }
            }
    except Exception as e:
        return {"error": str(e)}

# ========== Fear & Greed Index (رایگان - alternative.me) ==========
@app.get("/api/coinglass/sentiment")
async def get_sentiment():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.alternative.me/fng/",
                timeout=10.0
            )
            data = response.json()
            
            if data.get("data") and len(data["data"]) > 0:
                item = data["data"][0]
                value = int(item.get("value", 50))
                label = item.get("value_classification", "خنثی")
                
                # ترجمه label به فارسی
                fa_labels = {
                    "Extreme Fear": "ترس شدید",
                    "Fear": "ترس",
                    "Neutral": "خنثی",
                    "Greed": "طمع",
                    "Extreme Greed": "طمع شدید"
                }
                label_fa = fa_labels.get(label, label)
                
                return {"data": [{"value": value, "label": label_fa}]}
            return {"error": "No data"}
    except Exception as e:
        return {"error": str(e)}

# ========== Watchlist ==========
@app.get("/api/watchlist/{user_id}")
async def get_watchlist(user_id: str):
    data_file = "data.json"
    if not os.path.exists(data_file):
        return {"watchlist": []}
    with open(data_file, 'r') as f:
        data = json.load(f)
    return {"watchlist": data.get("watchlists", {}).get(user_id, [])}

@app.post("/api/watchlist/{user_id}")
async def add_to_watchlist(user_id: str, coin: dict):
    data_file = "data.json"
    if not os.path.exists(data_file):
        data = {"watchlists": {}}
    else:
        with open(data_file, 'r') as f:
            data = json.load(f)
    if "watchlists" not in data:
        data["watchlists"] = {}
    if user_id not in data["watchlists"]:
        data["watchlists"][user_id] = []
    if not any(c["id"] == coin["id"] for c in data["watchlists"][user_id]):
        data["watchlists"][user_id].append(coin)
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=2)
    return {"status": "success"}

@app.delete("/api/watchlist/{user_id}/{coin_id}")
async def remove_from_watchlist(user_id: str, coin_id: str):
    data_file = "data.json"
    if os.path.exists(data_file):
        with open(data_file, 'r') as f:
            data = json.load(f)
        if user_id in data.get("watchlists", {}):
            data["watchlists"][user_id] = [c for c in data["watchlists"][user_id] if c["id"] != coin_id]
            with open(data_file, 'w') as f:
                json.dump(data, f, indent=2)
    return {"status": "success"}
