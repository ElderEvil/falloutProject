# Build stage
FROM node:lts AS build-stage
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ENV VUE_APP_API_URL=http://backend:8000
RUN npm run build

# Production stage
FROM node:lts-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=build-stage /app/dist .
EXPOSE 3000

CMD ["serve"]
