# Deploying PolicyLens on Coolify

PolicyLens ships as one image (API and built UI on port 8100). These steps use Coolify's Dockerfile build pack. (If you use the Docker Compose pack instead, the compose file
publishes host port 8100, because Coolify's dashboard already holds 8000.) The container listens on `PORT`,
default 8100.
Nothing here contains a secret: you paste the values into Coolify yourself.

Status: the image build has not been run end to end on the author's machine (Docker was unavailable). The first
Coolify build is its first real test. If it fails, the build log names the step; the Dockerfile has only two.

## 1. Create the resource

1. Coolify: **Projects → your project → + New → Public Repository** (or a private one through your GitHub App).
2. Repository: `https://github.com/Zoronium/policylens`, branch `main`.
3. **Build Pack: Dockerfile.** Base directory `/`. Do not use the Docker Compose build pack: the compose file has a
   Postgres profile meant for local use.
4. **Ports Exposes: `8100`** (the app listens on `PORT`, default 8100; Coolify's own dashboard holds 8000).

## 2. Environment variables

Add these under **Environment Variables** (tick "Runtime only"; mark `LLM_API_KEY` as a secret):

| Variable | Value |
|---|---|
| `LLM_BASE_URL` | your provider's OpenAI-compatible URL |
| `LLM_API_KEY` | your key (secret) |
| `LLM_MODEL` | for example `openai/gpt-oss-120b` |
| `TRUST_PROXY` | `1` (Coolify's proxy sits in front, so the real client IP comes from `X-Forwarded-For`) |
| `EXTRACTIONS_PER_HOUR` | `5` (per client IP) |
| `LLM_DAILY_LIMIT` | `100` (all visitors together; your spend ceiling) |
| `MONGODB_URI` | your Atlas connection string (secret). Set it and policies live in MongoDB; leave it out to use SQLite below |
| `PUBLIC_URL` | `https://your.domain`: the absolute address used in `/sitemap.xml` and `/robots.txt` (Coolify's proxy hides the real scheme) |
| `MONGODB_DB` | `policylens` |
| `CLERK_PUBLISHABLE_KEY` | your Clerk publishable key (public by design) |
| `VITE_CLERK_PUBLISHABLE_KEY` | the same value, and tick **Build Variable** too: the UI bakes it in at build time |
| `VITE_POSTHOG_KEY` | optional: your PostHog project token (public by design). Tick **Build Variable**: baked in at build time |
| `VITE_POSTHOG_HOST` | optional: your PostHog host, for example `https://us.i.posthog.com` (also a Build Variable) |
| `DATABASE_URL` | `sqlite:////data/policylens.db` (only used when `MONGODB_URI` is empty) |

Sign-in is optional and only scopes saved policies to their owner. Anyone with the link can run up to `EXTRACTIONS_PER_HOUR` extractions per IP, and `LLM_DAILY_LIMIT`
in total per day, before getting 429. Set a spend cap at your LLM provider before you share the link.

## 3. Storage, domain, health

- **Persistent Storage:** add a volume with destination path `/data`, so stored policies survive redeploys. Not needed
  when policies are in MongoDB.
- **Atlas Network Access:** allow the Coolify server's public IP (or `0.0.0.0/0` if you accept the wider exposure).
  Atlas answers a blocked IP with a TLS handshake error, not a clear message.
- **Clerk:** add your domain to the instance's allowed origins, and switch on the sign-in methods you want.
- **Domains:** set your domain; Coolify issues the certificate.
- **Health check:** path `/health`, port `8100`.
- **Replicas: exactly one.** Rate-limit counters live in memory, so a second replica would double every limit.

## 4. Deploy and check

After the first deploy:

```bash
curl https://YOUR-DOMAIN/health
# {"ok":true,"llm_configured":true}
```

Open the site, go to Try it, pick a sample and extract it. After `EXTRACTIONS_PER_HOUR` extractions from one
address the next one should answer 429.

## Limits worth knowing

- Behind Cloudflare's orange-cloud proxy every visitor can arrive from a few Cloudflare addresses, which makes the
  per-IP limit coarse. The daily cap still holds. Prefer a DNS-only record.
- Set a spend cap at your LLM provider as well. This service limits how much can be spent, but a leaked key is
  still a leaked key.
- Counters reset when the container restarts.
