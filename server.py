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

# ========== Funding Rate از KCEx ==========
@app.get("/api/coinglass/funding")
async def get_funding():
    try:
        async with httpx.AsyncClient() as client:
            # KCEx API - گرفتن تیکرهای فیوچرز
            response = await client.get(
                "https://api.kcex.com/api/v1/tickers",
                timeout=10.0
            )
            data = response.json()
            
            if isinstance(data, dict) and data.get("data"):
                tickers = data["data"]
                result = []
                for t in tickers:
                    symbol = t.get("symbol", "")
                    funding_rate = float(t.get("fundingRate", t.get("funding_rate", 0)) or 0)
                    result.append({
                        "symbol": symbol,
                        "lastFundingRate": funding_rate
                    })
                
                result.sort(key=lambda x: x["lastFundingRate"], reverse=True)
                return {"data": result[:50]}
            elif isinstance(data, list):
                result = []
                for t in data:
                    symbol = t.get("symbol", "")
                    funding_rate = float(t.get("fundingRate", t.get("funding_rate", 0)) or 0)
                    result.append({
                        "symbol": symbol,
                        "lastFundingRate": funding_rate
                    })
                result.sort(key=lambda x: x["lastFundingRate"], reverse=True)
                return {"data": result[:50]}
            else:
                return {"error": str(data)[:500]}
    except Exception as e:
        return {"error": str(e)}

# ========== Liquidation از KCEx ==========
@app.get("/api/coinglass/liquidation")
async def get_liquidation():
    try:
        async with httpx.AsyncClient() as client:
            # KCEx liquidation orders
            response = await client.get(
                "https://api.kcex.com/api/v1/liquidation",
                timeout=10.0
            )
            data = response.json()
            
            if isinstance(data, dict) and data.get("data"):
                orders = data["data"]
                if isinstance(orders, list):
                    long_liq = 0
                    short_liq = 0
                    symbols_liq = {}
                    
                    for order in orders:
                        if not isinstance(order, dict):
                            continue
                        try:
                            price = float(order.get("price", order.get("avgPrice", 0)) or 0)
                            qty = float(order.get("qty", order.get("amount", 0)) or 0)
                            value = price * qty
                            symbol = order.get("symbol", "")
                            side = order.get("side", "").upper()
                            
                            if side in ("SELL", "SHORT"):
                                long_liq += value
                            else:
                                short_liq += value
                            
                            if symbol not in symbols_liq:
                                symbols_liq[symbol] = {"long": 0, "short": 0}
                            if side in ("SELL", "SHORT"):
                                symbols_liq[symbol]["long"] += value
                            else:
                                symbols_liq[symbol]["short"] += value
                        except:
                            continue
                    
                    return {
                        "data": {
                            "total": {"long": long_liq, "short": short_liq},
                            "symbols": [{"symbol": k, "total": v} for k, v in list(symbols_liq.items())[:20]]
                        }
                    }
            return {"error": str(data)[:500]}
    except Exception as e:
        return {"error": str(e)}

# ========== Fear & Greed ==========
@app.get("/api/coinglass/sentiment")
async def get_sentiment():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.alternative.me/fng/",
                timeout=10.0
            )
            data = response.json()
            
            if isinstance(data, dict) and data.get("data") and len(data["data"]) > 0:
                item = data["data"][0]
                value = int(item.get("value", 50))
                label = item.get("value_classification", "خنثی")
                
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
