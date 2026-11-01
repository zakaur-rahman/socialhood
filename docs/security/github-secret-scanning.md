# GitHub secret scanning: joining the partner programme

**Status:** the endpoint is built and tested (C-167). Amplychat isn't enrolled yet. The owner does the steps below.

GitHub scans public repositories, gists, issues, pull requests, wikis, npm packages and Actions logs for secrets. When it finds one matching a partner's pattern, it POSTs the match to the partner. Once Amplychat is enrolled, an Amplychat API key pushed to a public repository is revoked within seconds, and the workspace's owners and admins get an in-app notification.

Source: [GitHub's partner programme page](https://docs.github.com/en/code-security/secret-scanning/secret-scanning-partnership-program/secret-scanning-partner-program), read 2026-11-01.

## What to send GitHub

Email **secret-scanning@github.com** and ask to join the secret scanning partner programme. GitHub replies with its terms of participation, which must be agreed before it goes live. Then send the following, which is everything GitHub asks for per secret type:

| GitHub asks for | Send |
|---|---|
| A unique, human-readable name for the secret type | `amplychat_api_key` (display name: "Amplychat API Key") |
| A regular expression that finds the secret type | `shk_[A-Za-z0-9_-]{43}` |
| The URL of the endpoint that receives the alerts | `https://api.amplychat.com/v1/security/secret-scanning` |
| A test account for the service | A Pro test workspace with one owner login (see step 3 below) |
| A contact | `support@amplychat.com` |

### Why this regex

- A key is `shk_` plus `secrets.token_urlsafe(32)` (`services/api_keys.generate_key`).
- `token_urlsafe(32)` is 32 random bytes in URL-safe base64 with the padding removed. That is always 43 characters, from `A–Z a–z 0–9 - _`.
- So every key matches `shk_[A-Za-z0-9_-]{43}` exactly. `tests/integration/test_api_key_hardening.py::test_our_keys_match_the_pattern_github_is_given` checks this for 200 fresh keys.
- The `shk_` prefix plus 256 bits of randomness is the kind of pattern GitHub recommends ("a uniquely defined prefix" and "high entropy random strings").
- Our keys carry no checksum, so GitHub can't drop false matches before calling us. Any false match is answered `false_positive` and changes nothing.

## Steps

1. **Email GitHub** at secret-scanning@github.com, asking to join. Agree to the terms they send.
2. **Send the table above.** If GitHub's form asks for "before" and "after" boundary patterns, use a non-word character or the start or end of the text, so that `shk_` inside a longer identifier doesn't match.
3. **Make the test account.**
   1. Create a workspace on production, put it on Pro, and make one API key with `contacts:read`.
   2. Give GitHub the login only if they ask for one. They usually test by pushing a key to a test repository.
   3. After GitHub's test, the key shows **Revoked** in Settings › API keys. The audit log says "revoked: found in a public GitHub repository" with the repository URL. The owner gets a notification.
4. **Optional: false-positive feedback.**
   1. Our endpoint already answers every alert with GitHub's feedback array: `[{"token_hash", "token_type", "label"}]`.
      - `label` is `true_positive` for one of our keys (whether it was on or already revoked), and `false_positive` otherwise.
      - `token_hash` is the token's SHA-256 in lowercase hex.
   2. GitHub's page says to email them to take part in feedback, and doesn't say whether `token_hash` is hex or base64. Ask in the same email: "Is `token_hash` hex or base64?". If they say base64, it's a one-line change in `services/secret_scanning.handle`.
5. **Nothing else to configure.**
   - The endpoint fetches GitHub's public keys itself from `https://api.github.com/meta/public_keys/secret_scanning` and keeps them for a day.
   - It needs no GitHub token. A key id it doesn't know triggers one refetch, at most once a minute, well inside the unauthenticated limit of 60 an hour.

## How the endpoint behaves

`POST /v1/security/secret-scanning` (`api/v1/security.py`, `services/secret_scanning.py`):

- It is public and outside any workspace, rate limited at 120 a minute per IP (`secret_scanning`).
- It verifies `Github-Public-Key-Signature`: the base64 of a DER ECDSA P-256 SHA-256 signature over the raw body, made with the key named in `Github-Public-Key-Identifier`.
  - A missing, malformed, unknown or wrong signature gets 401 "This request isn't signed by GitHub." Nothing is looked up or changed.
  - If GitHub's keys can't be fetched and none are cached, it is also 401, and GitHub retries.
- Each `shk_` token in the payload `[{token, type, url, source}]` is looked up by its SHA-256.
  - If the key is still on, it is revoked (its REST hooks deleted). One audit row "revoked: found in a public GitHub repository" records the URL and the source. Owners and admins get a critical in-app notification, without the key itself.
  - A key that is already revoked changes nothing again.
  - A token that isn't one of our keys changes nothing.
- The 200 response is the feedback array. Only a request GitHub signed receives it, so nobody but GitHub can learn from it whether a token is a key.
