FROM node:26.12.1-alpine AS build-stage
WORKDIR /app

RUN npm install -g pnpm@11.9.0

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
RUN --mount=type=cache,target=/pnpm-store \
    pnpm install --frozen-lockfile --store-dir=/pnpm-store

COPY . .

ARG VITE_API_BASE_URL=http://localhost:8000
ARG VERSION=unknown
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV APP_VERSION=${VERSION}
RUN pnpm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine AS production

COPY --from=build-stage /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000
