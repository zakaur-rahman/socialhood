"""Email, push and digest delivery (P8: T8.5, T8.6, T8.7; FR-NOT-02…04, TR-FE-09).

Adapters sit behind protocols, like the AI provider: ``email.EmailSender`` (Resend in
``email_resend.py``, the in-memory ``email_fake.py``) and ``push.PushSender`` (Web Push with VAPID
in ``push_webpush.py``, the in-memory ``push_fake.py``). ``registry.py`` picks one per call and
lets tests swap them; tests/support/notify.py installs the fakes for every test, so no test sends
an email or a push. ``unsubscribe.py`` signs the digest's one-click unsubscribe links.
"""
