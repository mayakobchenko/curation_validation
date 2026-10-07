# Stage 1 — build the React frontend
FROM node:22.14.0-alpine AS frontend-build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci --legacy-peer-deps --silent --no-audit --no-fund
COPY frontend/ .
RUN npm run build

# Stage 2 — runtime: Python/FastAPI serving both the API and the built SPA
FROM python:3.12-slim AS runtime
WORKDIR /usr/src/app

# libreoffice-impress pulls in a 'writer' capable subset needed for the
# docx -> pdf export path; omit if PDF export isn't needed to shrink the image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend-build /app/dist ./frontend_dist

ENV FRONTEND_DIST_DIR=/usr/src/app/frontend_dist
ENV PORT=4100
EXPOSE 4100

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4100"]
