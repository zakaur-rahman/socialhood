<!-- Branch model: docs/ops/branching.md. feature/fix/chore → develop (squash);
     develop → main (merge commit); hotfix/* → main, then merge main back into develop. -->

## What and why



## How it was tested



## Migrations

- [ ] No migration
- [ ] Expand-only (new tables, nullable or defaulted columns, new indexes; drops wait for a later release)

## Screenshots (UI changes)



## Checklist

- [ ] API: `ruff format --check`, `ruff check`, `mypy` and `scripts/check_tenancy.py` pass
- [ ] API: tests pass (`pytest -n 4 -m "not serial"`, then `pytest -m serial`)
- [ ] Web: `lint`, `typecheck`, `test` and `build` pass
- [ ] API changed: `pnpm gen:api` run and `openapi.json` / `packages/api-client` committed
- [ ] No secrets, keys or `.env` files in the diff
- [ ] Docs updated where behaviour, settings or runbooks changed
