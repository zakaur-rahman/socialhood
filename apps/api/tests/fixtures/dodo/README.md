# Dodo fixtures

Real Dodo Payments **test-mode** answers, recorded 2026-09-30 with the test API key and
anonymised: the customer is "Test Owner" <owner@example.com>, the billing address and card holder
are made up, `metadata` is a Social Hood checkout's `{workspace_id}`, and the portal session token
is replaced. Ids (`sub_…`, `cus_…`, `pdt_…`, `pay_…`) are test-mode ids.

- `product_pro.json`: `GET /products/{id}` for the Pro product ($10.00 a month, its own 7-day
  trial, `payment_frequency_interval: "Month"`).
- `checkout_session.json`: `POST /checkouts` → `{session_id, checkout_url}`. Sent with
  `subscription_data.trial_period_days` 7 the hosted page shows "7 day free trial", $0.00 today;
  with 0 it shows no trial and $10.00 today (checked by opening both sessions).
- `subscription_active.json`: `GET /subscriptions/{id}`; `subscription_cancel_scheduled.json` and
  `subscription_resumed.json`: `PATCH /subscriptions/{id}` with `cancel_at_next_billing_date`
  true, then false (the subscription was left as it was); `subscription_cancelled.json`: a
  subscription cancelled at the end of its period (`cancelled_at` just after
  `next_billing_date`). Webhook `data` for `subscription.*` events is this object plus
  `payload_type: "Subscription"`.
- `customer_portal_session.json`: `POST /customers/{id}/customer-portal/session?return_url=` →
  `{link}`.
- `payment_succeeded.json`: `GET /payments/{id}`; webhook `data` for `payment.*` events is this
  object plus `payload_type: "Payment"`.
- `error_not_found.json` (404) and `error_invalid_request.json` (422, unknown product at
  checkout): Dodo's `{code, message}` errors.
