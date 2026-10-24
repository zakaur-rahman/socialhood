"""Google (GR-27): the OAuth grant and the Sheets calls Social Hood's sheet sync makes.

``client.py`` is the interface, ``http.py`` the real client, ``fake.py`` the in-memory one and
``registry.py`` picks between them (``GOOGLE_PROVIDER``; tests swap it with ``use_google``).
"""
