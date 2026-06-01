FROM node:20-alpine

WORKDIR /app

# Install deps
COPY package*.json ./
RUN npm install

# Copy source
COPY . .

# Expose Vite port
EXPOSE 5173

# Run dev server (host 0.0.0.0 so Docker can expose it)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]