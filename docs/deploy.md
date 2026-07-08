# Deployment

Architecture: **frontend on Vercel**, **FastAPI backend on a container host**.
The React app calls the backend directly at `VITE_API_BASE` (CORS is handled by
the backend), so the two deploy independently.

```
 Browser ──► Vercel (static React app)  ──HTTPS──►  Container host (FastAPI + engine)
             webapp/                                Dockerfile
```

## 1. Deploy the backend (do this first — you need its URL)

Any container host works; the repo ships a `Dockerfile`. Render example:

1. Push this repo to GitHub.
2. Render → **New → Blueprint** → pick this repo. It reads `render.yaml` and
   builds the `Dockerfile` service `celltwin-api` (health check: `/health`).
3. When live, note the URL, e.g. `https://celltwin-api.onrender.com`.
4. (Recommended) set the env var `ALLOWED_ORIGINS` to your Vercel URL once you
   have it, e.g. `https://your-app.vercel.app`.

Manual / other hosts (Railway, Fly.io, Cloud Run): build the `Dockerfile` and
run it; the container binds to `$PORT`. Local check:

```bash
docker build -t celltwin-api .
docker run -p 8000:8000 celltwin-api      # then GET http://localhost:8000/health
```

> **Memory note:** the NUTS Bayesian, particle-filter, and ML-surrogate endpoints
> load JAX/scikit-learn and can need ~1 GB RAM. The fast endpoints (simulate,
> dose-response, graph, combine, population) run on the smallest tiers. Pick a
> plan with ≥1 GB if you rely on the heavy endpoints.

## 2. Deploy the frontend (Vercel)

1. Vercel → **New Project** → import this repo.
2. Set **Root Directory = `webapp`** (Vercel then reads `webapp/vercel.json`;
   framework Vite is auto-detected).
3. Add an environment variable:
   `VITE_API_BASE = https://celltwin-api.onrender.com`  (your backend URL, no
   trailing slash).
4. Deploy. The app is static; it fetches everything from the backend.

To change the backend later, update `VITE_API_BASE` and redeploy (the value is
baked in at build time).

## Local development (unchanged)

```bash
uvicorn celltwin.api.app:app --app-dir backend --port 8000   # terminal 1
cd webapp && npm install && npm run dev                       # terminal 2 -> :5173
```
With `VITE_API_BASE` unset, the Vite dev server proxies `/api` → `localhost:8000`.

## Alternative: static dashboard (no backend)

`frontend/index.html` is fully self-contained (real precomputed data). Deploy the
`frontend/` folder to Vercel as a static site for an instant, zero-backend demo —
it just isn't recomputed live.
