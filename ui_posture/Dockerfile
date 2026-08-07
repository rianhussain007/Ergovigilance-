# Build stage
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies
COPY ui_posture/package*.json ./
RUN npm ci

# Copy source code and build
COPY ui_posture/ ./
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy build output
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx config
COPY ui_posture/nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
