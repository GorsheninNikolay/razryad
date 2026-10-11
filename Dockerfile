FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY content/ /app/content/
COPY --from=frontend-builder /frontend/dist /app/frontend/dist
COPY deploy/container-start.sh /usr/local/bin/container-start
RUN useradd --system --uid 10001 app && mkdir /data && chown app /data
USER app
ENV DATABASE_URL=sqlite:////data/razryad.db DEV_MODE=false PYTHONPATH=/app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["sh", "/usr/local/bin/container-start"]
