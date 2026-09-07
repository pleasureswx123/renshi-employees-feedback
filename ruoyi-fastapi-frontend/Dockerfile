# 构建阶段
ARG IMAGE_PREFIX=
FROM ${IMAGE_PREFIX}node:22-bookworm-slim AS builder
WORKDIR /app

# 依赖独立缓存，页面修改不重复下载。
COPY package.json package-lock.json ./

# 设置npm镜像源
ARG NPM_REGISTRY=https://registry.npmmirror.com
RUN npm config set registry "$NPM_REGISTRY"

# 安装依赖
RUN npm ci --no-audit --no-fund --fetch-timeout=60000 --fetch-retries=2
COPY . .

# 只注入公开访问入口。
ARG VITE_FEEDBACK_APP_URL
ARG VITE_APP_BASE_API=/docker-api
ENV VITE_FEEDBACK_APP_URL=$VITE_FEEDBACK_APP_URL VITE_APP_BASE_API=$VITE_APP_BASE_API

# 执行docker构建命令
RUN npm run build:docker

# 运行阶段
FROM ${IMAGE_PREFIX}nginx:1.28-alpine
WORKDIR /usr/share/nginx/html

# 复制构建产物
COPY --from=builder /app/dist .

# 暴露端口
EXPOSE 80

# 启动nginx
CMD ["nginx", "-g", "daemon off;"]
