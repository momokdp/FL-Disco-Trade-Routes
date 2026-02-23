from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx
from typing import Optional
from pydantic import BaseModel

app = FastAPI(title="Freelancer Trade Routes")

# Configuration CORS pour permettre au frontend de communiquer avec le backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DARKSTAT_API = "https://darkstat.dd84ai.com/api/npc_bases"

async def fetch_bases(nicknames: list[str] = None):
    payload = {
        "filter_market_good_category": ["commodity"],
        "filter_to_useful": True,
        "include_market_goods": True,
    }
    if nicknames:
        payload["filter_nicknames"] = nicknames

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(DARKSTAT_API, json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"API Error: {e}")
            return []

@app.get("/api/bases")
async def get_all_bases():
    data = await fetch_bases()
    if not data:
        raise HTTPException(status_code=502, detail="Could not fetch data from Darkstat")
    return data

@app.get("/api/routes")
async def get_trade_routes(
    commodity: Optional[str] = None,
    min_profit: int = 0,
    limit: int = 100
):
    bases = await fetch_bases()
    if not bases:
        raise HTTPException(status_code=502, detail="Darkstat API is unreachable")

    commodity_map = {}

    for base in bases:
        seen = set()
        for good in base.get("market_goods", []):
            nick = good.get("nickname")
            if not nick: continue
            
            # Déduplication
            key = (base.get("nickname"), nick)
            if key in seen: continue
            seen.add(key)

            # Filtre par nom de marchandise
            if commodity and commodity.lower() not in nick.lower() and commodity.lower() not in good.get("name", "").lower():
                continue

            if nick not in commodity_map:
                commodity_map[nick] = []

            # Sécurité sur les prix et volumes (évite les NoneType ou 0)
            price = good.get("price_base_sells_for", 0)
            vol = good.get("volume", 1) # Par défaut 1 pour éviter division par zéro

            commodity_map[nick].append({
                "commodity_nickname": nick,
                "commodity_name": good.get("name", "Unknown"),
                "base_nickname": base.get("nickname"),
                "base_name": base.get("name"),
                "system_name": base.get("system_name"),
                "region_name": base.get("region_name"),
                "faction_name": base.get("faction_name"),
                "sector_coord": base.get("sector_coord"),
                "price": price,
                "base_sells": good.get("base_sells", False),
                "volume": vol,
            })

    routes = []
    for nick, entries in commodity_map.items():
        sellers = [e for e in entries if e["base_sells"]]
        buyers = [e for e in entries if not e["base_sells"]]

        for sell_point in sellers:
            for buy_point in buyers:
                if sell_point["base_nickname"] == buy_point["base_nickname"]:
                    continue
                
                profit_per_unit = buy_point["price"] - sell_point["price"]
                if profit_per_unit <= min_profit:
                    continue

                # Calcul sécurisé du profit par volume
                vol = sell_point["volume"]
                profit_vol = round(profit_per_unit / vol, 2) if vol > 0 else 0

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
                    "profit_per_unit": profit_per_unit,
                    "volume": vol,
                    "profit_per_volume": profit_vol,
                })

    routes.sort(key=lambda r: r["profit_per_unit"], reverse=True)
    return routes[:limit]

@app.get("/api/commodities")
async def get_commodities():
    bases = await fetch_bases()
    seen = {}
    for base in bases:
        for good in base.get("market_goods", []):
            n = good.get("nickname")
            if n and n not in seen:
                seen[n] = good.get("name", n)

    return [{"nickname": k, "name": v} for k, v in sorted(seen.items(), key=lambda x: x[1])]

# Servir le dossier frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
