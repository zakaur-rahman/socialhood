"""Razorpay (GR-32): payment links created with the business's own keys, so the money goes to
their Razorpay account and never through us, and the check on the webhooks Razorpay sends back.

``client.py`` is the interface and the shapes, ``http.py`` the real client (Payment Links API),
``fake.py`` a sandbox for development and the end-to-end stack, ``registry.py`` picks between
them (``RAZORPAY_PROVIDER``; tests swap it with ``use_razorpay``) and ``signatures.py`` checks
the webhooks. The keys are per workspace (services/orders/payments.py); there are no app-wide
credentials. Partner OAuth is not used: it needs Razorpay Technology Partner sign-up (C-120).
"""
