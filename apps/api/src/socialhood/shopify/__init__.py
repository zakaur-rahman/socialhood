"""Shopify (GR-31): the OAuth grant, the product reads and the webhook registration the store
connection makes, and the checks on what Shopify sends back.

``client.py`` is the interface and the shapes, ``http.py`` the real client (Admin GraphQL),
``fake.py`` a built-in store for development and the end-to-end stack, ``registry.py`` picks
between them (``SHOPIFY_PROVIDER``; tests swap it with ``use_shopify``), and ``signatures.py``
checks the install redirect and the webhooks. **Nothing here has run against a real Shopify
store**: the app needs the owner's Partner account and listing (O-10). Every Shopify behaviour is
listed as unverified in docs/CONFLICTS.md (C-116).
"""
