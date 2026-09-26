# Build stage — pinned by digest (P1 supply chain), tag kept for readability.
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS build

WORKDIR /app

# Install dependencies
COPY ui_posture/package*.json ./
RUN npm ci

# Copy source code and build
COPY ui_posture/ ./
RUN npm run build

# Production stage — pinned by digest (P1 supply chain), tag kept for readability.
FROM nginx:alpine@sha256:1ed1b0e1d7652937d6cbdaf4018c7b6fc009a7dd6c3047351e2eddda745de43f

# Copy build output
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx config
COPY ui_posture/nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
