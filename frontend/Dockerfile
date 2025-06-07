FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Install serve to serve static files
RUN npm install -g serve

# Expose port
EXPOSE 3000

# Serve the built application
CMD ["serve", "-s", "dist", "-l", "tcp://0.0.0.0:3000"]