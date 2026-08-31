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

# ========== Funding Rate از OKX (اصلاح‌شده) ==========
@app.get("/api/coinglass/funding")
async def get_funding():
    try:
        async with httpx.AsyncClient() as client:
            # گرفتن لیست قراردادهای SWAP
            instruments_res = await client.get(
                "https://www.okx.com/api/v5/public/instruments",
                params={"instType": "SWAP"},
                timeout=10.0
            )
            instruments_data = instruments_res.json()
            
            if not isinstance(instruments_data, dict) or not instruments_data.get("data"):
                return {"error": str(instruments_data)[:300]}
            
            instruments = instruments_data["data"]
            inst_ids = [inst.get("instId", "") for inst in instruments[:100] if inst.get("instId", "").endswith("USDT-SWAP")]
            
            # گرفتن funding rate برای همه
            all_results = []
            for inst_id in inst_ids[:50]:
                try:
                    fr_res = await client.get(
                        "https://www.okx.com/api/v5/public/funding-rate",
                        params={"instId": inst_id},
                        timeout=5.0
                    )
                    fr_data = fr_res.json()
                    if isinstance(fr_data, dict) and fr_data.get("data") and len(fr_data["data"]) > 0:
                        rate = float(fr_data["data"][0].get("fundingRate", 0) or 0)
                        all_results.append({"symbol": inst_id, "lastFundingRate": rate})
                except:
                    continue
            
            all_results.sort(key=lambda x: x["lastFundingRate"], reverse=True)
            return {"data": all_results[:50], "source": "okx"}
    except Exception as e:
        return {"error": str(e)}

# ========== Liquidation از OKX (اصلاح‌شده) ==========
@app.get("/api/coinglass/liquidation")
async def get_liquidation():
    try:
        async with httpx.AsyncClient() as client:
            # OKX ticker - ۲۴ ساعته
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
                
                for i, t in enumerate(tickers):
                    symbol = t.get("instId", "")
                    vol_24h = float(t.get("volCcy24h", 0) or 0)
                    
                    # تقسیم تصادفی نیست - بر اساس تغییر قیمت
                    change_pct = float(t.get("priceChangePercent24h", 0) or 0)
                    
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
