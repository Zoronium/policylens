FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
# npm install, not ci: a lockfile made on Windows can lack the Linux native bindings Vite needs.
RUN npm install
COPY web/ ./
# Vite bakes the (public) Clerk key into the bundle; pass it as a build arg. Empty = no sign-in UI.
ARG VITE_CLERK_PUBLISHABLE_KEY=
ENV VITE_CLERK_PUBLISHABLE_KEY=$VITE_CLERK_PUBLISHABLE_KEY
# Same for the (public) PostHog project token and host. Empty = no analytics.
ARG VITE_POSTHOG_KEY=
ARG VITE_POSTHOG_HOST=
ENV VITE_POSTHOG_KEY=$VITE_POSTHOG_KEY VITE_POSTHOG_HOST=$VITE_POSTHOG_HOST
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
