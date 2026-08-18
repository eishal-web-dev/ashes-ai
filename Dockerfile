FROM python:3.12-slim

WORKDIR /app

# Install OS packages needed to build common Python wheels
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into the system environment so they are
# available on sys.path at runtime (no venvs, no custom prefixes).
COPY apps/api/requirements.txt apps/api/requirements.txt
RUN pip install --no-cache-dir -r apps/api/requirements.txt

# Copy the rest of the repository
COPY . .

EXPOSE 8000

ENTRYPOINT ["python", "-m", "uvicorn", "apps.api.production:app", "--host", "0.0.0.0", "--port", "8000"]
