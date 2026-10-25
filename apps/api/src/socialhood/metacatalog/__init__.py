"""The Meta commerce catalogue behind WhatsApp product messages (GR-33): copying the workspace's
products to it and checking the catalogue can be reached.

``client.py`` is the interface and the shapes, ``http.py`` the real client (the Catalog Batch API,
``POST /{catalog_id}/items_batch``), ``fake.py`` a sandbox catalogue for development and the
end-to-end stack (used for sandbox WhatsApp numbers), and ``registry.py`` picks between them (tests
swap it with ``use_catalogue``). **Nothing here has run against a real catalogue**: it waits for a
WhatsApp number connected to Meta with a commerce catalogue, and every Meta behaviour is listed as
unverified in docs/CONFLICTS.md (C-121).
"""
