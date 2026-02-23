# FL Trade Routes

Application web pour calculer les routes commerciales rentables dans Freelancer via l'API Darkstat.

## Structure

```
app/
├── backend/
│   └── main.py          # FastAPI backend
├── frontend/
│   └── index.html       # Interface web
├── requirements.txt
└── run.sh               # Script de lancement
```

## Installation & Lancement

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Lancer le serveur
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 3. Ouvrir dans le navigateur
# http://localhost:8000
```

Ou via le script :
```bash
chmod +x run.sh
./run.sh
```

## Endpoints API

| Endpoint | Description |
|---|---|
| `GET /api/routes?min_profit=50&limit=100&commodity=gold` | Routes commerciales calculées |
| `GET /api/bases` | Toutes les bases NPC avec leurs marchés |
| `GET /api/commodities` | Liste de toutes les marchandises |

## Logique de calcul

Une route est définie comme :
- **Base A** : vend la marchandise (`base_sells: true`) → prix d'achat
- **Base B** : accepte la marchandise (`base_sells: false`) au prix le plus élevé
- **Profit/unit** = `price_B - price_A`
- **Profit/volume** = `profit_unit / volume` (comparaison entre types de cargo)
