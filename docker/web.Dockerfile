FROM node:22-alpine AS build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
# Which code this is (FU-050; scripts/update.sh passes them), shown on the About page
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=
ENV VITE_COMMIT=$GIT_COMMIT \
    VITE_BUILT=$BUILD_DATE
RUN npm run build

FROM caddy:2-alpine
COPY docker/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /web/dist /srv/www
