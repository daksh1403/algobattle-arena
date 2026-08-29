# Algobattle — Vercel Deployment Guide

**Target audience:** Developers who want the fastest path to a live Algobattle frontend, paired with a backend on Railway or Render (serverless VPS). Vercel excels at zero-config React/TypeScript deployments with global CDN distribution and instant rollbacks. The backend must run on a persistent host — Vercel only serves serverless functions, not long-running background workers.

> **Important:** This is a **hybrid approach**. The frontend deploys to Vercel (excellent DX, free tier). The backend + worker + database deploy to a Platform-as-a-Service provider (Railway or Render) for persistent processes.

---

## Prerequisites

| Requirement | Details |
|---|---|
| Vercel Account | Sign up at vercel.com (GitHub login recommended) |
| Railway or Render Account | Backend hosting (free tiers available) |
| GitHub repository | Vercel connects directly to GitHub |
| PostgreSQL | Railway/Render managed Postgres |
| Redis | Railway/Render managed Redis |

---

## Step-by-Step Deployment

### Part A — Deploy the Backend to Railway

Railway is recommended because it auto-detects Dockerfiles and manages environment variables. Render is an equivalent alternative.

#### A1. Connect Railway to GitHub

1. Go to [railway.app](https://railway.app) → Sign in with GitHub
2. Click **New Project** → **Deploy from GitHub repo**
3. Select `your-org/algobattle`
4. Set the **Root Directory** to `backend`

#### A2. Configure environment variables in Railway

In the Railway project dashboard → **Variables** tab, add:

```
DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<host>:<port>/algobattle
REDIS_URL=redis://<host>:<port>/0
SECRET_KEY=<generate with openssl rand -hex 32>
JWT_SECRET=<same as SECRET_KEY>
APP_ENV=production
LOG_LEVEL=info
RANK_EXPIRE_MINUTES=1440
```

To create the database and Redis:
1. **New** → **Database** → **Add PostgreSQL** → copy the `DATABASE_URL`
2. **New** → **Database** → **Add Redis** → copy the `REDIS_URL`

#### A3. Deploy the judge worker

Railway detects the `Dockerfile` and runs the API server by default. For the judge worker:

1. **New** → **Blank Service**
2. Connect the same GitHub repo, set Root Directory to `judge`
3. Override the start command in **Settings** → **Start Command**:
   ```
   python -m rq.worker algobattle-judge
   ```
4. Add the same environment variables as the API service

The worker service should have **at least 1 always-on instance** to process the queue.

#### A4. Get the backend URL

Railway provides a public URL like `https://algobattle-api.up.railway.app`. Copy it — you'll use it in the frontend build.

---

### Part B — Deploy the Frontend to Vercel

#### B1. Connect Vercel to GitHub

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import `your-org/algobattle`
3. Set **Root Directory** to `frontend`
4. Vercel auto-detects Vite settings.

#### B2. Set environment variables in Vercel

In the Vercel project settings → **Environment Variables**, add:

```
VITE_API_URL=https://algobattle-api.up.railway.app/api
VITE_WS_URL=wss://algobattle-api.up.railway.app
```

> **Note:** Replace `algobattle-api.up.railway.app` with your actual Railway/Render backend URL. For production, use your own domain (e.g. `https://api.algobattle.com`).

#### B3. Configure build settings

Vercel detects `vite.config.ts` automatically. No custom build command needed. The output directory is `dist` (default for Vite).

**Override settings if needed:**
- Build Command: `npm run build`
- Output Directory: `dist`
- Install Command: `npm install`

#### B4. Deploy

Click **Deploy**. Vercel will:
1. Clone the repo
2. Run `npm install` in `frontend/`
3. Run `npm run build` (Vite produces the `dist/` folder)
4. Serve `dist/` from the Vercel Edge Network (globally distributed)

Your frontend will be live at `https://your-project.vercel.app`.

---

### Part C — Connect a Custom Domain (Optional)

```bash
# In Vercel dashboard → Domains → Add
# Add a CNAME or A record in your DNS provider:
#   Type: CNAME
#   Name: contest
#   Value: cname.vercel-dns.com

# In Railway dashboard → Settings → Domains → Add custom domain
#   api.algobattle.com → algobattle-api.up.railway.app
```

Then update the Vercel environment variable:
```
VITE_API_URL=https://api.algobattle.com/api
```

---

## Estimated Monthly Cost (dev tier)

| Resource | Provider | Free Tier | Est. $/mo |
|---|---|---|---|
| Frontend | Vercel Hobby | 100 GB bandwidth | **$0** |
| API server | Railway Hobby | 500 hrs/mo, 1 project | **$0–5** |
| Judge worker | Railway Hobby | 500 hrs/mo | **$0–5** |
| PostgreSQL | Railway | 1 database, 1 GB RAM | **$0–5** |
| Redis | Railway / Render | 30 MB / 256 MB | **$0** |
| **Total** | | | **$0–15/mo** |

Both Vercel and Railway have generous free tiers suitable for a class of up to 50 students.

---

## Verify the Deployment

```bash
# Check backend health
curl https://algobattle-api.up.railway.app/api/health
# Expected: {"status":"ok","database":"ok","redis":"ok"}

# Check frontend
curl https://your-project.vercel.app
# Expected: Algobattle landing page

# Smoke test — register and submit
TOKEN=$(curl -s -X POST https://algobattle-api.up.railway.app/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@test.com","password":"TestPass123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST https://algobattle-api.up.railway.app/api/submissions/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"problem_id":1,"language":"python3","code":"print(42)"}'
```

---

## Teardown (Avoid Lingering Resources)

**Vercel:**
```bash
# Dashboard → Project Settings → Danger Zone → Delete Project
# Or via CLI:
vercel remove <project-name>
```

**Railway:**
```bash
# Dashboard → Project → Settings → Delete Project
# This deletes all services (API, worker, DB, Redis) in one step
```

**Render:**
```bash
# Dashboard → Service → Settings → Delete Service
# Repeat for each service
```

---

## How to Modify and Customize

**Add GitHub Actions CI/CD:**
```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]
    paths: ['frontend/**']

jobs:
  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          working-directory: frontend
          vercel-args: '--prod'
```

**Swap Railway for Render:**
1. Create a Render account and connect the same GitHub repo
2. Render → **New** → **Web Service** for the API, set Start Command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
3. Render → **New** → **Background Worker** for the judge worker
4. Add a PostgreSQL and Redis via Render's **New** → **Database**
5. Update the `VERCEL_API_URL` environment variable with the Render URL

**Add Stripe for paid contests:**
```bash
# In Railway, add to API service environment variables:
STRIPE_SECRET_KEY=sk_test_...
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...

# Then update frontend/src/features/billing/ to use Stripe.js
```

**Enable real-time leaderboard updates:**
The WebSocket endpoint is already at `/ws`. Vercel supports WebSocket connections to external backends natively — no special config needed. Users will see leaderboard updates in real-time during contests.

**Scale for exams:** Railway Hobby allows 1 always-on instance. For exam scenarios with hundreds of simultaneous submissions:
1. Upgrade Railway to Pro ($5/project) for 3 always-on instances
2. Or switch to Railway's new "Nixpacks" deployment with auto-scaling settings

---

## Known Limitations of This Hybrid Approach

| Limitation | Impact | Mitigation |
|---|---|---|
| Vercel serverless functions can't host FastAPI | The API must run on a persistent VPS | Railway/Render handles this |
| Long WebSocket connections on free tier | Railway Hobby sleeps after 15 min inactivity | Upgrade to Pro or use a ping keepalive |
| Cold starts on Railway | ~5–10s first request after inactivity | Always-on instance (Pro plan) |
| No built-in CI/CD on Railway free | Must push manually or use GitHub Actions | Wire up the Actions workflow above |
