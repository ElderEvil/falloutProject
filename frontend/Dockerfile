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

FROM node:26.12.1-alpine AS production
WORKDIR /app

RUN npm install -g serve@14.2.4

COPY --from=build-stage /app/dist .
COPY serve.json ./serve.json

EXPOSE 3000

CMD ["serve", "-s", ".", "-l", "3000"]
