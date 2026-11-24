FROM node:26.13.1-alpine AS build-stage
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

FROM nginxinc/nginx-unprivileged:1.31-alpine AS production

# ARGs do not cross build stages, so re-declare the value the bundle was built with. It becomes
# the extra CSP connect source, keeping local builds working without widening production.
ARG VITE_API_BASE_URL=http://localhost:8000

COPY --from=build-stage /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN extra=""; \
    api_base="$(printf '%s' "$VITE_API_BASE_URL" | sed -e 's:/*$::')"; \
    if [ -n "$api_base" ]; then \
      origin="$api_base/"; \
      extra="$origin $(printf '%s' "$origin" | sed -e 's|^https|wss|' -e 's|^http|ws|')"; \
    fi; \
    sed -i "s|__EXTRA_API_ORIGINS__|$extra|g" /etc/nginx/conf.d/default.conf

EXPOSE 3000
