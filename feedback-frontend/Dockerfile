ARG IMAGE_PREFIX=
FROM ${IMAGE_PREFIX}node:22-bookworm-slim AS builder
WORKDIR /app
COPY package.json package-lock.json ./
ARG NPM_REGISTRY=https://registry.npmjs.org
RUN npm ci --registry="$NPM_REGISTRY" --no-audit --no-fund --fetch-timeout=60000 --fetch-retries=2
COPY . .
RUN npm run build

FROM ${IMAGE_PREFIX}nginx:1.28-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY bin/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
