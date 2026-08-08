# Ashes AI — MongoDB Setup

Ashes now has a MongoDB-backed FastAPI entrypoint at `apps.api.mongo_main:app`.

## 1. Install backend dependencies

```powershell
pip install -r apps/api/requirements.txt
```

## 2. Choose MongoDB

### Local MongoDB

```powershell
$env:MONGODB_URI="mongodb://localhost:27017"
$env:MONGODB_DB="ashes_ai"
```

### MongoDB Atlas

Create a cluster, database user, and network access rule in Atlas, then use your connection string:

```powershell
$env:MONGODB_URI="mongodb+srv://USERNAME:PASSWORD@YOUR-CLUSTER.mongodb.net/?retryWrites=true&w=majority"
$env:MONGODB_DB="ashes_ai"
```

Do not commit the real MongoDB username/password to GitHub.

## 3. Start the Mongo backend

```powershell
uvicorn apps.api.mongo_main:app --reload --host 0.0.0.0 --port 8000
```

Or on Windows:

```powershell
.\apps\api\run_mongo.ps1
```

Expected health response from `http://localhost:8000/health`:

```json
{
  "ok": true,
  "service": "ashes-api",
  "version": "1.3.0",
  "database": "mongodb"
}
```

## 4. Frontend

```powershell
$env:VITE_API_BASE_URL="http://localhost:8000"
npm install
npm run dev
```

## 5. Optional: migrate existing SQLite data

The migration utility preserves Ashes string IDs and converts orders into Mongo documents with embedded items/history.

```powershell
python tools/migrate_sqlite_to_mongo.py
```

To target Atlas explicitly:

```powershell
python tools/migrate_sqlite_to_mongo.py --mongo-uri "$env:MONGODB_URI" --mongo-db ashes_ai
```

Use `--replace` only when you intentionally want to clear Ashes collections in the target database before importing:

```powershell
python tools/migrate_sqlite_to_mongo.py --replace
```

## Mongo collections

- `users`
- `businesses`
- `products`
- `analytics_events`
- `orders`
- `table_qrs`
- `menu_imports`

Orders contain their items and status history in the same Mongo document, which removes the separate relational `order_items` and `order_status_history` tables used by the SQLite version.

## Production notes

- Use MongoDB Atlas rather than a MongoDB server stored on an ephemeral hosting filesystem.
- Keep `MONGODB_URI` server-side only.
- Restrict Atlas network access to your deployment environment when possible.
- Use a strong dedicated database password.
- The old SQLite entrypoint remains in the repository temporarily for rollback; production should start `apps.api.mongo_main:app`.
