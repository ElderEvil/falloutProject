# Build stage
FROM node:lts AS build-stage
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ENV VITE_API_BASE_URL=http://localhost:8000
RUN npm run build

# Production stage
FROM node:lts-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=build-stage /app/dist .
EXPOSE 3000

CMD ["serve"]
