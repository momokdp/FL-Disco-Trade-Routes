from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import httpx
from typing import Optional

app = FastAPI(title="Freelancer Trade Routes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DARKSTAT_API = "https://darkstat.dd84ai.com/api/npc_bases"

async def fetch_bases():
    payload = {
        "filter_market_good_category": ["commodity"],
        "filter_to_useful": True,
        "include_market_goods": True,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(DARKSTAT_API, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"CRITICAL API ERROR: {e}")
            return []

@app.get("/api/routes")
async def get_trade_routes(commodity: Optional[str] = None, min_profit: int = 0, limit: int = 100):
    bases = await fetch_bases()
    if not bases:
        raise HTTPException(status_code=502, detail="API vide")

    commodity_map = {}
    print(f"DEBUG: Processing {len(bases)} bases...")

    for base in bases:
        # Blindage total contre les bases qui ne sont pas des dictionnaires
        if not isinstance(base, dict):
            continue
            
        # Ligne 70 corrigée avec sécurité supplémentaire
        market_data = base.get("market_goods")
        market_goods = market_data if market_data is not None else []
        
        base_nick = base.get("nickname") or "unknown"
        
        for good in market_goods:
            if not isinstance(good, dict):
                continue
                
            nick = good.get("nickname")
            if not nick:
                continue

            if commodity:
                c_lower = commodity.lower()
                if c_lower not in nick.lower() and c_lower not in (good.get("name") or "").lower():
                    continue

            if nick not in commodity_map:
                commodity_map[nick] = []

            commodity_map[nick].append({
                "commodity_nickname": nick,
                "commodity_name": good.get("name") or "Unknown",
                "base_nickname": base_nick,
                "base_name": base.get("name") or "Unknown Base",
                "system_name": base.get("system_name") or "Unknown System",
                "region_name": base.get("region_name") or "Unknown Region",
                "faction_name": base.get("faction_name") or "Unknown Faction",
                "sector_coord": base.get("sector_coord") or "N/A",
                "price": good.get("price_base_sells_for") or 0,
                "base_sells": bool(good.get("base_sells")),
                "volume": good.get("volume") or 1,
            })

    routes = []
    for nick, entries in commodity_map.items():
        sellers = [e for e in entries if e["base_sells"]]
        buyers = [e for e in entries if not e["base_sells"]]
        for sell_point in sellers:
            for buy_point in buyers:
                if sell_point["base_nickname"] == buy_point["base_nickname"]:
                    continue
                profit = buy_point["price"] - sell_point["price"]
                if profit <= min_profit:
                    continue
                
                vol = sell_point["volume"]
                routes.append({
                    "commodity_nickname": nick,
                    "commodity_name": sell_point["commodity_name"],
                    "from_base": sell_point["base_name"],
                    "from_base_nickname": sell_point["base_nickname"],
                    "from_system": sell_point["system_name"],
                    "from_region": sell_point["region_name"],
                    "from_faction": sell_point["faction_name"],
                    "from_sector": sell_point["sector_coord"],
                    "buy_price": sell_point["price"],
                    "to_base": buy_point["base_name"],
                    "to_base_nickname": buy_point["base_nickname"],
                    "to_system": buy_point["system_name"],
                    "to_region": buy_point["region_name"],
                    "to_faction": buy_point["faction_name"],
                    "to_sector": buy_point["sector_coord"],
                    "sell_price": buy_point["price"],
                    "profit_per_unit": profit,
                    "volume": vol,
                    "profit_per_volume": round(profit / vol, 2) if vol > 0 else 0,
                })

    routes.sort(key=lambda r: r["profit_per_unit"], reverse=True)
    print(f"DEBUG: Found {len(routes)} routes")
    return routes[:limit]

@app.get("/api/commodities")
async def get_commodities():
    bases = await fetch_bases()
    seen = {}
    for base in bases:
        if not isinstance(base, dict): continue
        market_goods = base.get("market_goods") or []
        for good in market_goods:
            if isinstance(good, dict) and good.get("nickname"):
                n = good["nickname"]
                seen[n] = good.get("name") or n
    return [{"nickname": k, "name": v} for k, v in sorted(seen.items(), key=lambda x: x[1])]

app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
