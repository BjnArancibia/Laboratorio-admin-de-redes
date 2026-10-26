# Dockerfile HEREDADO del servicio orders (lo dejó el equipo anterior).
# Hoy NO funciona. Diagnostica el error, corrígelo y luego déjalo listo para producción.
FROM node:20-alpne

WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY . .

EXPOSE 3000
CMD ["node", "server.js"]
