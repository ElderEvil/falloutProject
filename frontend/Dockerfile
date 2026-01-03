# Build stage
FROM node:25-alpine AS build-stage
WORKDIR /app

# Install pnpm directly
RUN npm install -g pnpm@10.26.2

# Copy package files
COPY package.json pnpm-lock.yaml .npmrc ./

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy source files
COPY . .

# Set environment and build
ENV VITE_API_BASE_URL=http://37.27.195.77:30008
RUN pnpm run build

# Production stage
FROM node:25-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=build-stage /app/dist .
EXPOSE 3000

CMD ["serve", "-s", ".", "-l", "3000"]
