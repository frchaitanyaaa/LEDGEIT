# Build context: repository root (the web app imports packages/proof-core/ts)
FROM node:20-slim AS build
WORKDIR /repo
COPY packages/proof-core/ts/package.json packages/proof-core/ts/package-lock.json packages/proof-core/ts/
RUN npm ci --prefix packages/proof-core/ts --no-audit --no-fund
COPY apps/web/package.json apps/web/package-lock.json apps/web/
RUN npm ci --prefix apps/web --no-audit --no-fund
COPY packages/proof-core/ts packages/proof-core/ts
COPY apps/web apps/web
RUN cd apps/web && npx vite build

FROM nginx:1.27-alpine
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/apps/web/dist /usr/share/nginx/html
EXPOSE 80
