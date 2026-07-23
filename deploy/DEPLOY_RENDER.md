# LUMC-Dodoma — Deploy kwenye Render

> **Deploy BURE (ilipendekezwa sasa):** [`DEPLOY_RENDER_FREE.md`](./DEPLOY_RENDER_FREE.md)  
> = Render Free Web + Neon Free PostGIS (USD 0)

**URL (mfano):** `https://lumc-dodoma.onrender.com`  
**Stack:** Web Service (Docker) + Postgres × 2 (PostGIS)

Dump za database tayari zipo kwenye `deploy/db-dumps/` ikiwa ulizitoa kwenye PC.

---

## Muhimu kuhusu gharama

| Kipengele | Maelezo |
|-----------|---------|
| Web **Free** | Inalala baada ya ~15 min bila traffic (cold start ~1 min) |
| Web **Starter** (~USD 7/mwezi) | Inabaki awake — bora kwa ~50 users |
| Postgres | **Hakuna free** — Basic ~USD 6–7 / DB / mwezi |
| Databases 2 | GIS + Detailed Planning ≈ **USD 12–14 / mwezi** |

PostGIS inasaidiwa: `CREATE EXTENSION postgis;`

---

## A) GitHub (lazima)

Render hujenga kutoka Git repo.

1. Unda repo (private OK) na push mradi `tanzania_gis` (au folder yenye `Dockerfile` + `render.yaml`)
2. Hakikisha `.gitignore` ina `.env*`, `venv/`, `deploy/db-dumps/*.dump` (dumps **usizipush** — zirestore tofauti)

---

## B) Deploy Blueprint

1. Fungua https://dashboard.render.com → **New** → **Blueprint**
2. Chagua repo yenye `render.yaml`
3. Confirm services:
   - Web: `lumc-dodoma`
   - DB: `lumc-gis-db` (`tanzania_gis_db`)
   - DB: `lumc-detailed-db` (`detailed_planning`)
4. Apply → subiri build (Docker + GDAL inaweza kuchukua dakika kadhaa)

Baada ya deploy, nakili URL: `https://<jina>.onrender.com`

### Environment (Dashboard → Web → Environment)

Thibitisha / ongeza:

| Key | Value |
|-----|--------|
| `DJANGO_DEBUG` | `False` |
| `SERVE_MEDIA` | `1` |
| `DJANGO_ALLOWED_HOSTS` | `<jina>.onrender.com,.onrender.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://<jina>.onrender.com` |
| `GIS_PORTAL_URL` | `https://<jina>.onrender.com` |
| `DONATION_SITE_URL` | `https://<jina>.onrender.com` |
| `DATABASE_URL` | (auto kutoka Blueprint) |
| `DETAILED_DATABASE_URL` | (auto kutoka Blueprint) |

`DJANGO_SECRET_KEY` hutengenezwa otomatiki na Blueprint.

---

## C) Wezesha PostGIS + restore dumps

Kwenye kila database (Dashboard → DB → **Connect** → **External Database URL**):

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

(Unaweza kuifanya kupitia Shell ya Render au `psql` kwenye PC.)

### Kutoka Windows (PC)

```powershell
cd "D:\MFUMO LUMC\LUMC\tanzania_gis"

.\deploy\scripts\restore-to-render.ps1 `
  -GisUrl "postgresql://USER:PASSWORD@HOST/tanzania_gis_db" `
  -DetailedUrl "postgresql://USER:PASSWORD@HOST/detailed_planning" `
  -MainDump ".\deploy\db-dumps\tanzania_gis_db_20260723_120220.dump" `
  -DetailDump ".\deploy\db-dumps\detailed_planning_20260723_120220.dump"
```

Badilisha URLs kwa **External** connection strings kutoka Render (si Internal).

Kisha: Dashboard → Web service → **Manual Deploy** → Restart.

---

## D) Custom domain (hiari)

- Render free: subdomain `.onrender.com` tu
- Paid: unaweza kuunganisha `lumc-dodoma.duckdns.org` (CNAME) + SSL otomatiki

---

## E) Checklist

- [ ] `https://<jina>.onrender.com/login/` inafunguka
- [ ] Login inafanya kazi
- [ ] Ramani / wilaya zinaonekana
- [ ] Upload SHP ndogo inafanya kazi
- [ ] Baada ya cold start (free plan) site inakuja baada ya ~30–90s

---

## Troubleshooting

- **Build fail (GDAL):** angalia Docker logs — image inahitaji `libgdal-dev`
- **OperationalError / SSL:** hakikisha `DATABASE_URL` ni ya Render (SSL)
- **CSRF failed:** weka `DJANGO_CSRF_TRUSTED_ORIGINS=https://<jina>.onrender.com`
- **Ramani tupu baada ya restore:** thibitisha PostGIS extension + dumps zilirestore kwenye DB sahihi
- **Media zinapotea baada ya redeploy:** disk ya free ni ephemeral — uploads mpya zipotea; disk ya kudumu ni paid au S3 baadaye

---

## GCP vs Render

| | Render | GCP VM |
|--|--------|--------|
| Setup | Rahisi (Blueprint) | Docker + nginx + DNS |
| PostGIS | Managed | Docker PostGIS |
| Free | Web free (inalala) | Free tier / bill |
| Control | Chini | Kamili |

Faili za GCP bado zipo: `deploy/DEPLOY_GCP.md`
