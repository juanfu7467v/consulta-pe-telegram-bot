# syntax = docker/dockerfile:1

ARG NODE_VERSION=20.18.0
FROM node:${NODE_VERSION}-slim AS base

LABEL fly_launch_runtime="Node.js"

WORKDIR /app

ENV NODE_ENV=production

# --- Build stage ---
FROM base AS build

# Dependencias necesarias para compilar módulos nativos
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y \
    build-essential \
    node-gyp \
    pkg-config \
    python-is-python3 && \
    rm -rf /var/lib/apt/lists/*

# Copiamos package.json y lockfile primero (para aprovechar cache)
COPY package*.json ./

# Instalamos dependencias
RUN npm install --production=false

# Copiamos el resto del código
COPY . .

# --- Final stage ---
FROM base

COPY --from=build /app /app

EXPOSE 3000

CMD [ "npm", "run", "start" ]
