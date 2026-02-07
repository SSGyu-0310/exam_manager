FROM node:20-alpine AS base
WORKDIR /app/next_app

FROM base AS deps
COPY next_app/package*.json ./
RUN npm ci

FROM base AS dev
ENV NODE_ENV=development \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/next_app/node_modules ./node_modules
COPY next_app/ ./
EXPOSE 4000
CMD ["npm", "run", "dev"]

FROM base AS builder
ARG FLASK_BASE_URL=http://api:5000
ARG NEXT_PUBLIC_SITE_URL=http://localhost:4000
ARG NEXT_PUBLIC_APP_URL=http://localhost:4000
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    FLASK_BASE_URL=${FLASK_BASE_URL} \
    NEXT_PUBLIC_SITE_URL=${NEXT_PUBLIC_SITE_URL} \
    NEXT_PUBLIC_APP_URL=${NEXT_PUBLIC_APP_URL}
COPY --from=deps /app/next_app/node_modules ./node_modules
COPY next_app/ ./
RUN npm run build

FROM base AS runner
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/next_app/.next ./.next
COPY --from=builder /app/next_app/public ./public
COPY --from=builder /app/next_app/node_modules ./node_modules
COPY --from=builder /app/next_app/package.json ./package.json
COPY --from=builder /app/next_app/package-lock.json ./package-lock.json
COPY --from=builder /app/next_app/next.config.ts ./next.config.ts
EXPOSE 4000
CMD ["npm", "run", "start", "--", "-p", "4000", "-H", "0.0.0.0"]
