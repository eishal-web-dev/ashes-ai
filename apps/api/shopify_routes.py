from __future__ import annotations

import os
from typing import Any

import requests
from fastapi import HTTPException

from apps.api.mongo_main import app

SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-07")


def _shop() -> str:
    return (os.getenv("SHOPIFY_SHOP") or "ashes-stack.myshopify.com").strip()


def _client_id() -> str:
    return (os.getenv("SHOPIFY_CLIENT_ID") or os.getenv("ASHES_SHOPIFY_CLIENT_ID") or "").strip()


def _client_secret() -> str:
    return (os.getenv("SHOPIFY_CLIENT_SECRET") or os.getenv("ASHES_SHOPIFY_CLIENT_SECRET") or "").strip()


def _access_token() -> tuple[str, dict[str, Any]]:
    client_id = _client_id()
    client_secret = _client_secret()
    if not client_id:
        raise HTTPException(status_code=500, detail="SHOPIFY_CLIENT_ID is not configured")
    if not client_secret:
        raise HTTPException(status_code=500, detail="SHOPIFY_CLIENT_SECRET is not configured")

    url = f"https://{_shop()}/admin/oauth/access_token"
    try:
        response = requests.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Accept": "application/json"},
            timeout=20,
        )
        payload = response.json() if response.content else {}
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Shopify token request failed: {str(exc)[:180]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Shopify token endpoint returned invalid JSON") from exc

    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not response.ok or not token:
        detail = payload.get("error_description") or payload.get("error") or payload
        raise HTTPException(status_code=response.status_code or 502, detail=f"Shopify client credentials grant failed: {detail}")
    return str(token), payload


def _graphql(token: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        response = requests.post(
            f"https://{_shop()}/admin/api/{SHOPIFY_API_VERSION}/graphql.json",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Shopify-Access-Token": token,
            },
            json={"query": query, "variables": variables or {}},
            timeout=30,
        )
        payload = response.json() if response.content else {}
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Shopify GraphQL request failed: {str(exc)[:180]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Shopify GraphQL returned invalid JSON") from exc

    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=payload)
    if payload.get("errors"):
        raise HTTPException(status_code=502, detail=payload["errors"])
    return payload


@app.get("/api/shopify/products")
def shopify_products() -> dict[str, Any]:
    token, token_payload = _access_token()
    data = _graphql(
        token,
        """
        query AshesProducts {
          shop { name }
          products(first: 50) {
            nodes {
              id
              title
              handle
              status
              featuredMedia { preview { image { url } } }
            }
          }
        }
        """,
    )
    shop_data = data.get("data") or {}
    return {
        "connected": True,
        "shop": _shop(),
        "store_name": (shop_data.get("shop") or {}).get("name"),
        "token_expires_in": token_payload.get("expires_in"),
        "scopes": token_payload.get("scope"),
        "products": ((shop_data.get("products") or {}).get("nodes") or []),
    }


@app.get("/api/shopify/health")
def shopify_health() -> dict[str, Any]:
    token, token_payload = _access_token()
    data = _graphql(token, "query AshesShopHealth { shop { name myshopifyDomain } }")
    return {
        "ok": True,
        "shop": (data.get("data") or {}).get("shop"),
        "scopes": token_payload.get("scope"),
    }
