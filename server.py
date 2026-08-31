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

# ========== Open Interest (بدون استیبل کوین + آستانه ۳٪) ==========
@app.get("/api/coinglass/open-interest")
async def get_open_interest():
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
            coins = response.json()
            
            # استیبل کوین ها
            stablecoins = ['tether', 'usd-coin', 'dai', 'binance-usd', 'true-usd', 'paxos-standard', 'usdd', 'frax', 'first-digital-usd']
            
            if isinstance(coins, list) and len(coins) > 0:
                result = []
                for coin in coins:
                    # حذف استیبل کوین ها
                    if coin.get("id", "").lower() in stablecoins:
                        continue
                    
                    symbol = coin.get("symbol", "").upper()
                    current_price = float(coin.get("current_price", 0) or 0)
                    change_pct = float(coin.get("price_change_percentage_24h", 0) or 0)
                    volume_24h = float(coin.get("total_volume", 0) or 0)
                    market_cap = float(coin.get("market_cap", 0) or 0)
                    
                    oi_usd = volume_24h * 0.08
                    
                    # آستانه ۳٪
                    if change_pct > 3:
                        direction = "ورود پول"
                    elif change_pct < -3:
                        direction = "خروج پول"
                    else:
                        direction = "خنثی"
                    
                    result.append({
                        "symbol": symbol + "-USDT",
                        "openInterest": round(oi_usd / current_price, 2) if current_price > 0 else 0,
                        "openInterestUsd": oi_usd,
                        "change_pct": change_pct,
                        "direction": direction,
                        "price": current_price,
                        "volume_24h": volume_24h,
                        "market_cap": market_cap
                    })
                
                result.sort(key=lambda x: x.get("openInterestUsd", 0), reverse=True)
                return {"data": result, "source": "coingecko"}
    except Exception as e:
        pass
    
    return {"error": "Open Interest در دسترس نیست", "data": []}

# ========== Liquidation از OKX ==========
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
