FROM node:18.20-alpine AS build

ARG APP_VERSION=dev
ENV VITE_APP_VERSION=${APP_VERSION}

WORKDIR /app

COPY frontend/package*.json ./
RUN if [ -f package-lock.json ]; then \
        npm ci --no-audit --no-fund; \
    else \
        npm install --no-audit --no-fund; \
    fi

COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine

ARG APP_VERSION=dev

ENV TZ=Asia/Shanghai \
    APP_VERSION=${APP_VERSION} \
    WEB_PORT=8080 \
    API_UPSTREAM=api:8000 \
    IMMICH_UPSTREAM=immich-server:2283

LABEL org.opencontainers.image.version=$APP_VERSION

RUN apk add --no-cache tzdata \
    && mkdir -p /var/cache/nginx/photo \
    && chown -R nginx:nginx /var/cache/nginx

COPY deploy/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- "http://127.0.0.1:${WEB_PORT:-8080}/healthz" || exit 1
