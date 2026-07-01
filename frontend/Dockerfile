# Сборка SPA и раздача через nginx. API проксируется на бэкенд (см. nginx.conf),
# поэтому браузер ходит на тот же origin — CORS не нужен.
FROM node:20-slim AS build
WORKDIR /ui
# Базовый URL API вшивается на сборке (Vite). Пусто = относительный путь (nginx-прокся).
ARG VITE_API_BASE=""
ENV VITE_API_BASE=$VITE_API_BASE
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /ui/dist /usr/share/nginx/html
EXPOSE 80
