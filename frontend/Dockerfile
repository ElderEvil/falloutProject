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
COPY --from=build-stage /app/dist ./dist
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000", "-n", "0.0.0.0"]
