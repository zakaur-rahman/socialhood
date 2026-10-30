# syntax=docker/dockerfile:1.7
# The web image (C-145): Next.js standalone output, run with `node apps/web/server.js` on port 3000.
# Build from the repository root (the pnpm workspace):
#   docker build -f apps/web/Dockerfile --build-arg NEXT_PUBLIC_API_BASE_URL=... -t amplychat-web .
#
# NEXT_PUBLIC_* values are inlined into the bundles at build time, so each is a build argument
# (public by definition; the Production workflow takes them from GitHub variables). Server
# secrets (CLERK_SECRET_KEY) are never build arguments: they come from the environment at run
# time (/opt/amplychat/web.env). The optional Sentry source-map token is a BuildKit secret, so it
# never lands in a layer.

ARG NODE_VERSION=24

FROM node:${NODE_VERSION}-bookworm-slim AS base
ENV PNPM_HOME=/pnpm \
    NEXT_TELEMETRY_DISABLED=1
ENV PATH=$PNPM_HOME:$PATH
# The pnpm version pinned in package.json ("packageManager").
COPY package.json /tmp/package.json
RUN corepack enable \
 && corepack prepare "$(node -p "require('/tmp/package.json').packageManager")" --activate
WORKDIR /repo

# ---- deps: fetch the locked packages into the store (cached until the lockfile changes)
FROM base AS deps
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY patches ./patches
# The store is part of this layer (not a cache mount), so a layer cache restored on a fresh CI
# runner still has it for the offline install below.
RUN pnpm fetch --frozen-lockfile --store-dir /pnpm/store

# ---- build
FROM deps AS build
COPY apps/web ./apps/web
COPY packages ./packages
RUN pnpm install --offline --frozen-lockfile --store-dir /pnpm/store --filter "@socialhood/web..."

ARG NEXT_PUBLIC_API_BASE_URL=""
ARG NEXT_PUBLIC_SITE_URL=""
ARG NEXT_PUBLIC_APP_URL=""
ARG NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION=""
ARG NEXT_PUBLIC_BING_SITE_VERIFICATION=""
ARG NEXT_PUBLIC_FACEBOOK_DOMAIN_VERIFICATION=""
ARG NEXT_PUBLIC_STATUS_URL=""
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=""
ARG NEXT_PUBLIC_CLERK_SIGN_IN_URL="/sign-in"
ARG NEXT_PUBLIC_CLERK_SIGN_UP_URL="/sign-up"
ARG NEXT_PUBLIC_META_APP_ID=""
ARG NEXT_PUBLIC_WHATSAPP_CONFIG_ID=""
ARG NEXT_PUBLIC_SENTRY_DSN=""
ARG NEXT_PUBLIC_SENTRY_ENVIRONMENT="production"
ARG NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE="0"
ARG SENTRY_ORG=""
ARG SENTRY_PROJECT=""
ENV NEXT_OUTPUT=standalone \
    NODE_ENV=production \
    NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL     NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL \
    NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION=$NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION \
    NEXT_PUBLIC_BING_SITE_VERIFICATION=$NEXT_PUBLIC_BING_SITE_VERIFICATION \
    NEXT_PUBLIC_FACEBOOK_DOMAIN_VERIFICATION=$NEXT_PUBLIC_FACEBOOK_DOMAIN_VERIFICATION \
    NEXT_PUBLIC_STATUS_URL=$NEXT_PUBLIC_STATUS_URL \
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY \
    NEXT_PUBLIC_CLERK_SIGN_IN_URL=$NEXT_PUBLIC_CLERK_SIGN_IN_URL \
    NEXT_PUBLIC_CLERK_SIGN_UP_URL=$NEXT_PUBLIC_CLERK_SIGN_UP_URL \
    NEXT_PUBLIC_META_APP_ID=$NEXT_PUBLIC_META_APP_ID \
    NEXT_PUBLIC_WHATSAPP_CONFIG_ID=$NEXT_PUBLIC_WHATSAPP_CONFIG_ID \
    NEXT_PUBLIC_SENTRY_DSN=$NEXT_PUBLIC_SENTRY_DSN \
    NEXT_PUBLIC_SENTRY_ENVIRONMENT=$NEXT_PUBLIC_SENTRY_ENVIRONMENT \
    NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE=$NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE \
    SENTRY_ORG=$SENTRY_ORG \
    SENTRY_PROJECT=$SENTRY_PROJECT
# Source maps upload only when the sentry_auth_token secret is given (next.config.ts); the token
# exists for this one command and is not kept in the image.
RUN --mount=type=secret,id=sentry_auth_token,required=false \
    if [ -s /run/secrets/sentry_auth_token ]; then \
      export SENTRY_AUTH_TOKEN="$(cat /run/secrets/sentry_auth_token)"; \
    fi \
 && pnpm --filter @socialhood/web build

# ---- runtime: the standalone server, its traced node_modules, static assets and public/
FROM node:${NODE_VERSION}-bookworm-slim AS runtime
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
WORKDIR /app
COPY --from=build --chown=node:node /repo/apps/web/.next/standalone ./
COPY --from=build --chown=node:node /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=node:node /repo/apps/web/public ./apps/web/public
USER node
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/robots.txt').then((r) => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]
CMD ["node", "apps/web/server.js"]
