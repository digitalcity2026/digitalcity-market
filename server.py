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

# ========== Funding Rate از Bybit ==========
@app.get("/api/coinglass/funding")
async def get_funding():
    try:
        async with httpx.AsyncClient() as client:
            # گرفتن tickers از Bybit
            response = await client.get(
                "https://api.bybit.com/v5/market/tickers",
                params={"category": "linear", "limit": 100},
                timeout=10.0
            )
            data = response.json()
            
            if isinstance(data, dict) and data.get("result", {}).get("list"):
                tickers = data["result"]["list"]
                filtered = []
                for t in tickers:
                    symbol = t.get("symbol", "")
                    funding_rate = float(t.get("fundingRate", 0) or 0)
                    filtered.append({
                        "symbol": symbol,
                        "lastFundingRate": funding_rate
                    })
                
                # مرتب‌سازی
                filtered.sort(key=lambda x: x["lastFundingRate"], reverse=True)
                return {"data": filtered[:50]}
            else:
                return {"error": str(data)[:300]}
    except Exception as e:
        return {"error": str(e)}

# ========== Liquidation از Binance (با fallback) ==========
@app.get("/api/coinglass/liquidation")
async def get_liquidation():
    try:
        # تلاش از Binance اول
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://fapi.binance.com/fapi/v1/allForceOrders?limit=100",
                    timeout=5.0
                )
                orders = response.json()
                
                if isinstance(orders, list) and len(orders) > 0:
                    long_liq = 0
                    short_liq = 0
                    symbols_liq = {}
                    
                    for order in orders:
                        if not isinstance(order, dict):
                            continue
                        try:
                            price = float(order.get("avgPrice", 0) or 0)
                            qty = float(order.get("executedQty", order.get("origQty", 0)) or 0)
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
                        except:
                            continue
                    
                    return {
                        "data": {
                            "total": {"long": long_liq, "short": short_liq},
                            "symbols": [{"symbol": k, "total": v} for k, v in list(symbols_liq.items())[:20]]
                        }
                    }
        except:
            pass
        
        # Fallback: داده‌های نمونه
        return {
            "data": {
                "total": {"long": 0, "short": 0},
                "symbols": []
            },
            "note": "Binance API از این لوکیشن در دسترس نیست"
        }
    except Exception as e:
        return {"error": str(e)}

# ========== Fear & Greed از alternative.me ==========
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
