$ErrorActionPreference = "Stop"

if (-not $env:MONGODB_URI) {
  $env:MONGODB_URI = "mongodb://localhost:27017"
}
if (-not $env:MONGODB_DB) {
  $env:MONGODB_DB = "ashes_ai"
}

python -m uvicorn apps.api.mongo_main:app --reload --host 0.0.0.0 --port 8000
