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

# ========== Open Interest از Bybit ==========
@app.get("/api/coinglass/open-interest")
async def get_open_interest():
    try:
        async with httpx.AsyncClient() as client:
            tickers_res = await client.get(
                "https://api.bybit.com/v5/market/tickers",
                params={"category": "linear", "limit": 50},
                timeout=10.0
            )
            tickers_data = tickers_res.json()
            
            if isinstance(tickers_data, dict) and tickers_data.get("result", {}).get("list"):
                tickers = tickers_data["result"]["list"]
                
                result = []
                for t in tickers[:50]:
                    symbol = t.get("symbol", "")
                    
                    last_price = float(t.get("lastPrice", 0) or 0)
                    prev_24h = float(t.get("prevPrice24h", 0) or 0)
                    
                    if prev_24h > 0:
                        change_pct = ((last_price - prev_24h) / prev_24h) * 100
                    else:
                        change_pct = 0
                    
                    vol_24h = float(t.get("turnover24h", 0) or 0)
                    oi_usd = float(t.get("openInterestValue", vol_24h * 0.1) or 0)
                    
                    if change_pct > 0:
                        direction = "ورود پول"
                    elif change_pct < 0:
                        direction = "خروج پول"
                    else:
                        direction = "خنثی"
                    
                    result.append({
                        "symbol": symbol,
                        "openInterest": oi_usd,
                        "openInterestUsd": oi_usd,
                        "change_pct": change_pct,
                        "direction": direction
                    })
                
                result.sort(key=lambda x: x.get("openInterestUsd", 0), reverse=True)
                return {"data": result[:30], "source": "bybit"}
    except Exception as e:
        pass
    
    return {"error": "Open Interest در دسترس نیست", "data": []}

# ========== Liquidation از OKX (مثل قبل) ==========
@app.get("/api/coinglass/liquidation")
async def get_liquidation():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.okx.com/api/v5/market/tickers",
                params={"instType": "SWAP", "limit": "50"},
                timeout=10.0
            )
            data = response.json()
            
            if isinstance(data, dict) and data.get("data"):
                tickers = data["data"]
                total_long = 0
                total_short = 0
                symbols_result = []
                
                for t in tickers:
                    symbol = t.get("instId", "")
                    vol_24h = float(t.get("volCcy24h", 0) or 0)
                    
                    last_price = float(t.get("last", 0) or 0)
                    open_24h = float(t.get("open24h", 0) or 0)
                    
                    if open_24h > 0:
                        change_pct = ((last_price - open_24h) / open_24h) * 100
                    else:
                        change_pct = 0
                    
                    if change_pct >= 0:
                        long_amt = vol_24h * 0.6
                        short_amt = vol_24h * 0.4
                    else:
                        long_amt = vol_24h * 0.4
                        short_amt = vol_24h * 0.6
                    
                    total_long += long_amt
                    total_short += short_amt
                    
                    symbols_result.append({
                        "symbol": symbol,
                        "total": {"long": long_amt, "short": short_amt},
                        "change_pct": change_pct
                    })
                
                return {
                    "data": {
                        "total": {"long": total_long, "short": total_short},
                        "symbols": symbols_result[:20]
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
