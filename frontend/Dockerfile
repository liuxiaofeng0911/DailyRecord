FROM node:18.20-alpine AS build

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

ENV TZ=Asia/Shanghai \
    API_UPSTREAM=api:9111 \
    IMMICH_UPSTREAM=immich-server:2283

RUN apk add --no-cache tzdata \
    && mkdir -p /var/cache/nginx/photo \
    && chown -R nginx:nginx /var/cache/nginx

COPY deploy/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 9110

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:9110/healthz || exit 1
