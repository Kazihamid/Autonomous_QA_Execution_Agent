FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_CONTROL_PLANE_URL=http://localhost:8080
ARG NEXT_PUBLIC_AUTH_MODE=dev
ARG NEXT_PUBLIC_RECORDER_VIEW_URL=http://localhost:6080/vnc.html?autoconnect=1&resize=scale
ENV NEXT_PUBLIC_CONTROL_PLANE_URL=$NEXT_PUBLIC_CONTROL_PLANE_URL
ENV NEXT_PUBLIC_AUTH_MODE=$NEXT_PUBLIC_AUTH_MODE
ENV NEXT_PUBLIC_RECORDER_VIEW_URL=$NEXT_PUBLIC_RECORDER_VIEW_URL
RUN npm run build

FROM node:24-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
EXPOSE 3000
CMD ["npm", "run", "start"]
