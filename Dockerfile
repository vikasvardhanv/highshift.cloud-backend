# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
# Copy frontend package files
COPY frontend/package*.json ./
# Install dependencies
RUN npm ci
# Copy source code
COPY frontend/ ./
# Build the project
RUN npm run build

# Stage 2: Setup Backend
FROM node:20-alpine
WORKDIR /app

# Copy backend package files
COPY package*.json ./
# Install production dependencies
RUN npm ci --only=production

# Copy backend source code
COPY . .

# Copy built frontend assets from builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Set environment variables
ENV NODE_ENV=production
ENV PORT=3000

# Expose port
EXPOSE 3000

# Start server
CMD ["npm", "start"]
