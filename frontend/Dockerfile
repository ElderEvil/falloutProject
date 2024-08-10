# Build stage
FROM node:lts AS build-stage
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM node:lts-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=build-stage /app/dist .
ENV VITE_API_BASE_URL=http://37.27.195.77:8000/api/v1
EXPOSE 3000

CMD ["serve"]
