FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /srv
COPY pyproject.toml ./
COPY app ./app
COPY engine ./engine
COPY evals ./evals
COPY samples ./samples
# Editable install so app/main.py finds web/dist next to the package.
RUN pip install --no-cache-dir -e ".[postgres]"
COPY --from=web /web/dist ./web/dist
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
