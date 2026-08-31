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

# ========== Funding Rate از OKX ==========
@app.get("/api/coinglass/funding")
async def get_funding():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.okx.com/api/v5/public/funding-rate",
                params={"instType": "SWAP", "limit": "100"},
                timeout=10.0
            )
            data = response.json()
            
            if isinstance(data, dict) and data.get("data"):
                funding_data = data["data"]
                result = []
                for item in funding_data:
                    symbol = item.get("instId", "")
                    rate = float(item.get("fundingRate", 0) or 0)
                    result.append({"symbol": symbol, "lastFundingRate": rate})
                
                result.sort(key=lambda x: x["lastFundingRate"], reverse=True)
                return {"data": result[:50], "source": "okx"}
            else:
                return {"error": str(data)[:300]}
    except Exception as e:
        return {"error": str(e)}

# ========== Liquidation از OKX ==========
@app.get("/api/coinglass/liquidation")
async def get_liquidation():
    try:
        async with httpx.AsyncClient() as client:
            # OKX ticker اطلاعات
            response = await client.get(
                "https://www.okx.com/api/v5/market/tickers",
                params={"instType": "SWAP", "limit": "50"},
                timeout=10.0
            )
            data = response.json()
            
            if isinstance(data, dict) and data.get("data"):
                tickers = data["data"]
                result = []
                for t in tickers:
                    symbol = t.get("instId", "")
                    # محاسبه حجم تقریبی
                    vol = float(t.get("volCcy24h", 0) or 0)
                    result.append({
                        "symbol": symbol,
                        "total": {"long": vol * 0.5, "short": vol * 0.5}
                    })
                return {
                    "data": {
                        "total": {"long": sum(r["total"]["long"] for r in result), "short": sum(r["total"]["short"] for r in result)},
                        "symbols": result[:20]
                    },
                    "source": "okx"
                }
            return {"error": str(data)[:300]}
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
