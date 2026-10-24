"""The real Shopify client (GR-31): OAuth and the Admin GraphQL API over the shared httpx client.

- Authorise: the install redirect with the app's key, scopes and callback; the access token that
  comes back is Shopify's offline token (it does not expire until the app is uninstalled).
- Products are read 50 at a time with a cursor; the store, its currency and its own domain come
  from the ``shop`` query; webhooks are subscribed with ``webhookSubscriptionCreate`` to this
  server's address (a subscription that already exists counts as done).
- A response is classified into a ``ShopifyError`` kind (client.py); no body is logged or kept,
  because it can carry the store's data.

**Unverified against a real store** (C-116): the endpoint paths, the GraphQL field names
(``inventoryItem.tracked``, ``onlineStoreUrl``), the ``read_products`` scope being enough for
stock, and the API version. The shapes follow Shopify's published documentation.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from socialhood.settings import Settings
from socialhood.shopify.client import Grant, ProductPage, ShopifyError, ShopInfo
from socialhood.shopify.parse import from_graphql

PRODUCTS_QUERY = """
query Products($cursor: String) {
  products(first: 50, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id title descriptionHtml handle status onlineStoreUrl
      featuredImage { url }
      variants(first: 100) {
        nodes {
          id title sku price inventoryQuantity
          inventoryItem { tracked }
          selectedOptions { name value }
        }
      }
    }
  }
}
"""

SHOP_QUERY = """
query { shop { name currencyCode myshopifyDomain primaryDomain { host } } }
"""

WEBHOOK_MUTATION = """
mutation($topic: WebhookSubscriptionTopic!, $address: URL!) {
  webhookSubscriptionCreate(
    topic: $topic
    webhookSubscription: { callbackUrl: $address, format: JSON }
  ) {
    webhookSubscription { id }
    userErrors { field message }
  }
}
"""


def _kind(status: int) -> ShopifyError:
    if status in (401, 403):
        return ShopifyError("auth", "Shopify no longer accepts the access.", status=status)
    if status == 404:
        return ShopifyError("not_found", "Shopify can't find that store.", status=status)
    if status == 429:
        return ShopifyError("rate_limited", "Shopify asked us to slow down.", status=status)
    if status >= 500:
        return ShopifyError("unavailable", "Shopify isn't responding.", status=status)
    return ShopifyError("rejected", "Shopify refused the request.", status=status)


def _topic(topic: str) -> str:
    """ "products/create" as the GraphQL enum, PRODUCTS_CREATE."""
    return topic.upper().replace("/", "_")


class HttpShopifyClient:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings

    def _secret(self) -> str:
        secret = self._settings.shopify_api_secret
        return secret.get_secret_value() if secret else ""

    def _api(self, shop: str) -> str:
        return f"https://{shop}/admin/api/{self._settings.shopify_api_version}"

    # ---------------------------------------------------------------- OAuth

    def authorize_url(self, shop: str, state: str) -> str:
        query = urlencode(
            {
                "client_id": self._settings.shopify_api_key or "",
                "scope": self._settings.shopify_scopes,
                "redirect_uri": self._settings.shopify_redirect_uri or "",
                "state": state,
            }
        )
        return f"https://{shop}/admin/oauth/authorize?{query}"

    async def exchange_code(self, shop: str, code: str) -> Grant:
        try:
            response = await self._http.post(
                f"https://{shop}/admin/oauth/access_token",
                json={
                    "client_id": self._settings.shopify_api_key or "",
                    "client_secret": self._secret(),
                    "code": code,
                },
            )
        except httpx.HTTPError as error:
            raise ShopifyError("unavailable", "Shopify isn't responding.") from error
        if response.status_code in (400, 401, 403):  # the code was used, expired or forged
            raise ShopifyError("auth", "Shopify no longer accepts the access.")
        if response.status_code >= 400:
            raise _kind(response.status_code)
        body: dict[str, Any] = response.json()
        token = body.get("access_token")
        if not token:
            raise ShopifyError("auth", "Shopify didn't give access.")
        return Grant(str(token), tuple(str(body.get("scope", "")).replace(",", " ").split()))

    async def revoke(self, shop: str, token: str) -> None:
        try:
            await self._http.delete(
                f"https://{shop}/admin/api_permissions/current.json",
                headers={"X-Shopify-Access-Token": token},
            )
        except httpx.HTTPError:
            return  # best effort: the connection is removed here either way

    # ---------------------------------------------------------------- GraphQL

    async def _graphql(
        self, shop: str, token: str, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            response = await self._http.post(
                f"{self._api(shop)}/graphql.json",
                json={"query": query, "variables": variables or {}},
                headers={"X-Shopify-Access-Token": token},
            )
        except httpx.HTTPError as error:
            raise ShopifyError("unavailable", "Shopify isn't responding.") from error
        if response.status_code >= 400:
            raise _kind(response.status_code)
        body: dict[str, Any] = response.json()
        for problem in body.get("errors") or []:
            extensions = problem.get("extensions") if isinstance(problem, dict) else None
            if isinstance(extensions, dict) and extensions.get("code") == "THROTTLED":
                raise ShopifyError("rate_limited", "Shopify asked us to slow down.")
        if body.get("errors"):
            raise ShopifyError("rejected", "Shopify refused the request.")
        data: dict[str, Any] = body.get("data") or {}
        return data

    async def shop_info(self, shop: str, token: str) -> ShopInfo:
        data = await self._graphql(shop, token, SHOP_QUERY)
        info = data.get("shop") or {}
        primary = (info.get("primaryDomain") or {}).get("host")
        return ShopInfo(
            name=info.get("name"),
            domain=str(info.get("myshopifyDomain") or shop),
            storefront_domain=primary if primary and primary != shop else None,
            currency=info.get("currencyCode"),
        )

    async def list_products(self, shop: str, token: str, cursor: str | None) -> ProductPage:
        data = await self._graphql(shop, token, PRODUCTS_QUERY, {"cursor": cursor})
        listing = data.get("products") or {}
        products = [p for node in listing.get("nodes") or [] if (p := from_graphql(node))]
        paging = listing.get("pageInfo") or {}
        more = bool(paging.get("hasNextPage"))
        return ProductPage(products, str(paging["endCursor"]) if more else None)

    async def register_webhooks(
        self, shop: str, token: str, topics: tuple[str, ...], address: str
    ) -> list[str]:
        done = []
        for topic in topics:
            data = await self._graphql(
                shop, token, WEBHOOK_MUTATION, {"topic": _topic(topic), "address": address}
            )
            errors = (data.get("webhookSubscriptionCreate") or {}).get("userErrors") or []
            taken = any("already" in str(e.get("message", "")).casefold() for e in errors)
            if not errors or taken:
                done.append(topic)
        return done
