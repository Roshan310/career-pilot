# Self-contained frontend image (mirrors backend/'s standalone Dockerfile).
# Dev-oriented: runs `next dev` with the source bind-mounted by docker-compose.
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
