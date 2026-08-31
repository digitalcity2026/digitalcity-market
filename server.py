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

# ========== Funding Rate ==========
# تلاش از چند صرافی مختلف - هرکدوم جواب داد استفاده کن
@app.get("/api/coinglass/funding")
async def get_funding():
    # لیست API های مختلف
    apis = [
        {"url": "https://fapi.binance.com/fapi/v1/premiumIndex", "type": "binance"},
        {"url": "https://api-futures.kucoin.com/api/v1/funding-history?limit=100", "type": "kucoin"},
        {"url": "https://api.bybit.com/v5/market/tickers?category=linear", "type": "bybit"},
    ]
    
    for api in apis:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(api["url"], timeout=8.0)
                data = response.json()
                
                if api["type"] == "binance" and isinstance(data, list) and len(data) > 0:
                    filtered = [item for item in data if isinstance(item, dict) and item.get("symbol", "").endswith("USDT")]
                    filtered.sort(key=lambda x: float(x.get("lastFundingRate", 0) or 0), reverse=True)
                    return {"data": filtered[:50], "source": "binance"}
                
                elif api["type"] == "kucoin" and isinstance(data, dict) and data.get("data"):
                    funding_data = data["data"]
                    latest = {}
                    for item in funding_data:
                        symbol = item.get("symbol", "")
                        rate = float(item.get("fundingRate", 0) or 0)
                        if symbol not in latest:
                            latest[symbol] = rate
                    result = [{"symbol": k, "lastFundingRate": v} for k, v in latest.items()]
                    result.sort(key=lambda x: x["lastFundingRate"], reverse=True)
                    return {"data": result[:50], "source": "kucoin"}
                
                elif api["type"] == "bybit" and isinstance(data, dict) and data.get("result", {}).get("list"):
                    tickers = data["result"]["list"]
                    result = []
                    for t in tickers:
                        result.append({
                            "symbol": t.get("symbol", ""),
                            "lastFundingRate": float(t.get("fundingRate", 0) or 0)
                        })
                    result.sort(key=lambda x: x["lastFundingRate"], reverse=True)
                    return {"data": result[:50], "source": "bybit"}
        except:
            continue
    
    # اگه هیچکدوم کار نکرد
    return {"error": "هیچ صرافی در دسترس نیست", "data": []}

# ========== Liquidation ==========
@app.get("/api/coinglass/liquidation")
async def get_liquidation():
    try:
        async with httpx.AsyncClient() as client:
            # تلاش از KuCoin
            try:
                response = await client.get(
                    "https://api-futures.kucoin.com/api/v1/contracts/active",
                    timeout=5.0
                )
                contracts = response.json()
                
                if isinstance(contracts, dict) and contracts.get("data"):
                    # ساخت داده نمونه از قراردادهای فعال
                    symbols = [c.get("symbol", "") for c in contracts["data"][:20]]
                    return {
                        "data": {
                            "total": {"long": 0, "short": 0},
                            "symbols": [{"symbol": s, "total": {"long": 0, "short": 0}} for s in symbols]
                        },
                        "source": "kucoin",
                        "note": "داده کامل لیکوئید در دسترس نیست"
                    }
            except:
                pass
            
            # Fallback
            return {
                "data": {
                    "total": {"long": 0, "short": 0},
                    "symbols": []
                },
                "note": "داده لیکوئید در دسترس نیست"
            }
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
