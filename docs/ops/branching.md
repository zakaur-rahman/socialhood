# Branches, merges and releases

How code gets from a branch to staging and production, and the GitHub settings that enforce it.
Deploy details (Render, Vercel, secrets per environment) are in [deploy.md](deploy.md).

## 1. The model

| Branch | What it is | Deploys to |
|---|---|---|
| `main` | production; the default branch | Render production (after approval), Vercel production |
| `develop` | staging and integration | Render staging (automatically), Vercel `staging` |
| `feature/*`, `fix/*`, `chore/*` | short-lived work, branched from `develop` | Vercel preview per pull request |
| `hotfix/*` | urgent production fixes, branched from `main` | nothing until merged |

```
feature/x ──PR (squash)──▶ develop ──PR (merge commit)──▶ main
                              ▲                            │
                              └──PR (merge commit)─────────┤  after a hotfix
hotfix/y ──PR (merge commit)──────────────────────────────▶ main
```

Nobody pushes to `main` or `develop` directly. Every change is a pull request, and CI's four
checks (`api`, `web`, `contract`, `secrets`) must pass before it can merge. There are no required
approvals: the owner works alone, and GitHub does not let you approve your own pull request.

## 2. Merge strategies, and why

| Pull request | Method | Why |
|---|---|---|
| `feature/*`, `fix/*`, `chore/*` → `develop` | **Squash** | One commit per change on `develop`: easy to read, revert and bisect. The branch's work-in-progress commits disappear. |
| `develop` → `main` (a release) | **Merge commit**, never squash or rebase | `develop`'s commits stay ancestors of `main`. A squash or rebase would give `main` new commits that `develop` doesn't have, so the next release would conflict with changes already released and the two branches would drift apart for good. |
| `hotfix/*` → `main` | **Merge commit** | Keeps the fix's commit identical on both branches once `main` is merged back. |
| `main` → `develop` (after a hotfix) | **Merge commit** | Brings the hotfix, and `main`'s release merges, into `develop` so `main` stays an ancestor of `develop`. |

`main` therefore has merge commits and no linear history, by design. The release pull request's
title is the release name, for example "Release 2026-10-14"; its description lists the squashed
changes (GitHub shows them under Commits).

## 3. Everyday flow

1. `git switch develop && git pull`, then `git switch -c feature/short-name`.
2. Push and open a pull request into `develop`. CI runs; Vercel posts a preview link.
3. When the checks are green, **Squash and merge**, and delete the branch (GitHub does it if
   "Automatically delete head branches" is on; see section 6).
4. `develop` deploys to staging on its own once every check on the merge commit passes: the API
   migrates first, then the new code takes traffic. Check staging.
5. To release, open a pull request **`develop` → `main`** and **Create a merge commit**.
6. CI runs on `main`, then the Production workflow waits for your approval: Actions → the
   "Production" run → **Review deployments** → `production` → **Approve and deploy**. It calls the
   Render deploy hooks for that exact commit; the API migrates, then the API and worker switch
   over. Vercel deploys the web from `main` by itself (section 8). (In `manual` mode, section 6:
   Actions → Production → **Run workflow** → `main` instead.)

## 4. Hotfixes

1. `git switch main && git pull`, then `git switch -c hotfix/short-name`.
2. Pull request into **`main`**; checks pass; **Create a merge commit**.
3. Approve the production deploy as in step 6 above.
4. Straight away, open a pull request **`main` → `develop`** and **Create a merge commit** (do not
   squash). If it conflicts, resolve it on a branch made from `develop`
   (`git switch -c chore/merge-main develop && git merge origin/main`), push that branch and open
   its pull request into `develop` with a merge commit instead.

A hotfix skips staging, so keep it small, and never include a migration that isn't expand-only.

## 5. Migrations

Migrations are **expand-only** (TR-OPS-02): add tables, nullable or defaulted columns, and
indexes; stop using a column in one release and drop it in a later one. The API's pre-deploy
command runs `alembic upgrade head` before the new code takes traffic, and the worker and the
previous API version keep running on the new schema, so every migration must work with the code
that is live while it runs.

**Staging always migrates first.** Every migration reaches `develop`, and so the staging database,
before a release takes it to production. A migration that fails on staging stops the release. The
one exception is a hotfix, which is why a hotfix must not carry a migration that could fail.

CI checks that the migrations apply to an empty database and that the models match them
(`alembic upgrade head` and `alembic check` in the `api` job).

## 6. GitHub settings [owner account]

Do these once, after `develop` exists and CI has run at least once (GitHub only offers a status
check in the picker after it has reported on the repository).

**Plan check first.** On a **private** repository, rulesets and branch protection need GitHub Pro
(personal account) or Team (organization), and an environment's **required reviewers** need GitHub
Enterprise; on a public repository all of them work on every plan. Without required reviewers,
set the repository variable `PRODUCTION_DEPLOY` to `manual` (below): merges to `main` then deploy
nothing, and you release with **Actions → Production → Run workflow** on `main`, which deploys
`main`'s head once CI has passed on it. Either way nothing reaches production without you.

### General

**Settings → General**

1. **Default branch:** `main`.
2. **Pull Requests:**
   - **Allow merge commits:** on.
   - **Allow squash merging:** on. Default commit message: **Pull request title and description**.
   - **Allow rebase merging:** off.
   - **Always suggest updating pull request branches:** off.
   - **Automatically delete head branches:** on. It never deletes `main` or `develop`, because
     their rulesets block deletion.

### Rulesets

**Settings → Rules → Rulesets → New ruleset → New branch ruleset**, twice.

**Ruleset `main`**

| Setting | Value |
|---|---|
| Ruleset name | `main` |
| Enforcement status | **Active** |
| Bypass list | empty |
| Target branches | **Add target → Include by pattern** → `main` |
| Restrict creations | off |
| Restrict updates | off |
| **Restrict deletions** | **on** |
| Require linear history | **off** (releases and hotfixes are merge commits) |
| Require deployments to succeed | off |
| Require signed commits | off |
| **Require a pull request before merging** | **on** |
| → Required approvals | **0** |
| → Dismiss stale approvals, Require review from Code Owners, Require approval of the most recent reviewable push | off |
| → Require conversation resolution before merging | on |
| → Allowed merge methods | **Merge** only |
| **Require status checks to pass** | **on** |
| → Require branches to be up to date before merging | **off** (see below) |
| → Do not require status checks on creation | off |
| → Status checks | **Add checks**: `api`, `web`, `contract`, `secrets`, each with source **GitHub Actions** |
| **Block force pushes** | **on** |
| Require code scanning results | off |

**Ruleset `develop`**: the same, except:

| Setting | Value |
|---|---|
| Ruleset name | `develop` |
| Target branches | **Include by pattern** → `develop` |
| → Allowed merge methods | **Squash** and **Merge** (squash for feature work; merge only for `main` → `develop` after a hotfix) |
| Require linear history | off (the merge-back after a hotfix is a merge commit) |

"Require branches to be up to date" stays off on both: `develop` never contains `main`'s release
merge commits, so on `main` it would demand a pointless back-merge before every release, and CI
already tests each pull request merged with its base (`refs/pull/N/merge`).

If the plan has no rulesets for this repository, use **Settings → Branches → Add classic branch
protection rule** with the same choices: branch name pattern `main` (then `develop`); **Require a
pull request before merging** with **Require approvals** unticked; **Require status checks to
pass before merging** with `api`, `web`, `contract` and `secrets`; **Do not allow bypassing the
above settings**; **Allow force pushes** and **Allow deletions** unticked; **Require linear
history** unticked. Classic rules cannot limit the merge method per branch, so pick it by hand
as in section 2.

The check names are the CI job names in `.github/workflows/ci.yml`. Renaming a job silently
blocks every merge (the old check never reports): change the rulesets in the same pull request.

### Environment `production`

**Settings → Environments → New environment** → `production` → **Configure environment**:

1. **Required reviewers:** on; add the owner. Leave **Prevent self-review** off (the owner merges
   the release and approves its deploy).
2. **Wait timer:** off.
3. **Deployment branches and tags:** **Selected branches and tags** → **Add deployment branch or
   tag rule** → `main`.
4. **Environment secrets:** the two deploy hooks below.

### Secrets

**Settings → Secrets and variables → Actions**

| Secret | Where | Value |
|---|---|---|
| `RENDER_DEPLOY_HOOK_API` | environment `production` | Render → `socialhood-api` → Settings → **Deploy Hook** |
| `RENDER_DEPLOY_HOOK_WORKER` | environment `production` | Render → `socialhood-worker` → Settings → **Deploy Hook** |
| `CLERK_E2E_PUBLISHABLE_KEY` | repository | Clerk **development** instance publishable key ([testing-e2e.md](../testing-e2e.md)) |
| `CLERK_E2E_SECRET_KEY` | repository | Clerk **development** instance secret key |
| `GITLEAKS_LICENSE` | repository | only if the repository belongs to a GitHub organization (free key from gitleaks.io); not needed on a personal account |

A deploy hook URL deploys the service to anyone who has it: keep it only in the environment
secret, and **Regenerate Hook** in Render if it leaks. (Environment secrets on a private
repository need GitHub Pro or Team; on Free, add the two hooks as repository secrets instead.)

**Variables** tab (repository): `PRODUCTION_DEPLOY` = `manual` only when required reviewers are not
available (see "Plan check" above); leave it unset otherwise.

## 7. Workflows

| Workflow | Runs on | What it does |
|---|---|---|
| `ci.yml` (CI) | pull requests into `develop` or `main`; pushes to `develop` and `main` | the four required checks. A newer push to the same branch or pull request cancels the older run. |
| `production.yml` (Production) | CI finishing green on a push to `main`; "Run workflow" on `main` | waits for approval in `production`, then calls both deploy hooks with the tested commit |
| `e2e-nightly.yml` (E2E nightly) | 21:30 UTC on `develop`; "Run workflow" on any branch | the Playwright suite against a local sandbox stack ([testing-e2e.md](../testing-e2e.md)) |
| `ops.yml` (Ops) | pull requests and pushes to `develop` and `main` that touch `infra/prometheus/` | the alert rules and their tests |

The API tests run in parallel in CI (`pytest -n 4 -m "not serial"`, each worker on its own
database and Valkey db), then the few `serial` tests alone. See the testing notes in the
repository README.

## 8. What deploys where

| Event | Render staging | Render production | Vercel |
|---|---|---|---|
| Pull request opened or updated | | | preview (staging API) |
| Merge into `develop` | deploys after every check on the commit passes | | `staging` environment |
| Merge into `main` | | deploys after CI passes **and** the owner approves | production |

The web goes live from `main` without waiting for the production approval, so until you approve
it runs against the previous API. Keep the API backward compatible with the web that is live (add
endpoints and fields before the web uses them), and approve release deploys promptly.
