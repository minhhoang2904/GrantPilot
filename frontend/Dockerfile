FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_SERVER_B_URL=http://server-b-retrieval:8001
ENV VITE_SERVER_B_URL=${VITE_SERVER_B_URL}
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
RUN printf 'server {\n  listen 8501;\n  root /usr/share/nginx/html;\n  index index.html;\n\n  location /api/ {\n    proxy_pass http://server-b-retrieval:8001/;\n    proxy_set_header Host $host;\n    proxy_set_header X-Real-IP $remote_addr;\n  }\n\n  location / {\n    try_files $uri $uri/ /index.html;\n  }\n}\n' \
    > /etc/nginx/conf.d/default.conf
EXPOSE 8501
