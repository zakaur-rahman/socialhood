# Connecting a WhatsApp number in development

Connect WhatsApp (F-04) uses Meta's Embedded Signup, and Embedded Signup **can't connect Meta's
test number** (the one on the app's WhatsApp → API Setup page). The popup finishes without a
number, and Social Hood answers "This WhatsApp Business Account has no phone number yet … Meta's
test numbers can't be connected this way; use a number your business owns."

For development, `apps/api/scripts/connect_whatsapp_number.py` connects a number directly with a
token. It takes the same path as Embedded Signup after its code exchange
(`services/whatsapp_connect.py`, `connect_number`): the plan limit, an active workspace,
`account_in_use`, the token stored encrypted, our app subscribed to the WhatsApp Business Account
(`POST /{waba_id}/subscribed_apps`), and registration with a PIN we keep. It refuses to run when
`APP_ENV` is `production`.

## 1. Get a permanent token (a system user's)

1. Open Meta Business Settings for the business that owns the app: **Users → System users → Add**.
   Give it a name and the **Admin** role.
2. **Assign assets → WhatsApp accounts**: pick the WhatsApp Business Account (the test one from API
   Setup, or your own) and give it full control.
3. **Generate new token**: choose this app, set the expiry to never, and tick
   `whatsapp_business_messaging` and `whatsapp_business_management`. Copy the token.

The temporary token on the API Setup page also works, but it lasts about a day; after that the
number shows "Needs reconnecting". Run the script again with a new token to reconnect the same row.

## 2. Put it in `apps/api/.env`

```sh
WHATSAPP_DEV_TOKEN=<the token>
```

The script reads it from the environment or that file only. It is never an argument and never
printed. Don't commit it (`.env` is ignored).

## 3. Run the script

The API Setup page shows the **Phone number ID** and the **WhatsApp Business Account ID**. The
workspace is its slug (from the URL, `/w/<slug>/…`) or its id.

```sh
cd apps/api
uv run python scripts/connect_whatsapp_number.py --workspace <slug or id> \
    --waba-id <WhatsApp Business Account ID> --phone-number-id <Phone number ID>
```

It prints the account id, the number and its status, nothing secret:

```
Connected WhatsApp account 0192…
  number: +1 555 000 0000 (Test Number)
  status: active
```

Exit code 1 means Meta or Social Hood refused (`account_in_use`, the plan's WhatsApp limit, a
Graph error); 2 a usage problem (production, no token, no such workspace, a workspace being
deleted). Meta refuses to register its test numbers; the script logs `whatsapp_register_failed`
and carries on, and the number still sends. A failed webhook subscription shows as status
`error` with Retry on the card, as it does after Embedded Signup.

## Limits of the test number

- It can only message the recipient numbers added on the API Setup page (the "To" list, up to
  five, each verified with a code).
- Messages reach the API through the WhatsApp webhook, so locally run `pnpm tunnel` and set the
  app's WhatsApp webhook (WhatsApp → Configuration) to `<tunnel URL>/webhooks/whatsapp` with
  `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, subscribed to `messages`.
- To remove the number, disconnect it in Settings → Connections.
