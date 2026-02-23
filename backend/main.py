from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx
import asyncio
from typing import Optional
from pydantic import BaseModel

app = FastAPI(title="Freelancer Trade Routes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DARKSTAT_API = "https://darkstat.dd84ai.com/api/npc_bases"

class BasesRequest(BaseModel):
    filter_market_good_category: list[str] = ["commodity"]
    filter_to_useful: bool = True
    include_market_goods: bool = True

async def fetch_bases(nicknames: list[str] = None):
    payload = {
        "filter_market_good_category": ["commodity"],
        "filter_to_useful": True,
        "include_market_goods": True,
    }
    if nicknames:
        payload["filter_nicknames"] = nicknames

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(DARKSTAT_API, json=payload)
        resp.raise_for_status()
        return resp.json()

@app.get("/api/bases")
async def get_all_bases():
    """Fetch all NPC bases with their market goods"""
    try:
        data = await fetch_bases()
        return data
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/routes")
async def get_trade_routes(
    commodity: Optional[str] = None,
    min_profit: int = 0,
    limit: int = 100
):
    """
    Calculate profitable trade routes.
    A route is: buy commodity on base A (base_sells=True) → sell on base B (base_sells=False, higher price).
    Profit = price_base_sells_for(B) - price_base_sells_for(A)
    """
    try:
        bases = await fetch_bases()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Build index: commodity_nickname -> list of {base, price, sells}
    commodity_map: dict[str, list[dict]] = {}

    for base in bases:
        seen = set()
        for good in base.get("market_goods", []):
            nick = good["nickname"]
            # deduplicate by nickname (keep highest price entry)
            key = (base["nickname"], nick)
            if key in seen:
                continue
            seen.add(key)

            if commodity and commodity.lower() not in nick.lower() and commodity.lower() not in good["name"].lower():
                continue

            if nick not in commodity_map:
                commodity_map[nick] = []

            commodity_map[nick].append({
                "commodity_nickname": nick,
                "commodity_name": good["name"],
                "base_nickname": base["nickname"],
                "base_name": base["name"],
                "system_name": base["system_name"],
                "region_name": base["region_name"],
                "faction_name": base["faction_name"],
                "sector_coord": base["sector_coord"],
                "price": good["price_base_sells_for"],
                "base_sells": good["base_sells"],
                "volume": good["volume"],
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
                    "volume": sell_point["volume"],
                    "profit_per_volume": round(profit_per_unit / sell_point["volume"], 2) if sell_point["volume"] > 0 else 0,
                })

    routes.sort(key=lambda r: r["profit_per_unit"], reverse=True)
    return routes[:limit]

@app.get("/api/commodities")
async def get_commodities():
    """Return list of all unique tradeable commodities"""
    try:
        bases = await fetch_bases()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    seen = {}
    for base in bases:
        for good in base.get("market_goods", []):
            if good["nickname"] not in seen:
                seen[good["nickname"]] = good["name"]

    return [{"nickname": k, "name": v} for k, v in sorted(seen.items(), key=lambda x: x[1])]

app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
