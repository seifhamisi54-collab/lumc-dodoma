# LUMC-Dodoma — Deploy **BURE** (Render + Neon)

**Gharama:** USD 0  
**Web:** Render Free (`*.onrender.com`)  
**Database:** Neon Free + PostGIS (Postgres ya Render si free tena)

> Muhimu: Web free **inalala** baada ya ~15 min bila traffic (cold start ~1 min).  
> Neon free: storage ~0.5 GB/project — dumps zako (~25 MB) zinafaa; usipakie shapefile kubwa sana.

---

## A) Neon (databases bure) — ~5 min

1. Fungua https://console.neon.tech → Sign up (Google OK)
2. **Create project**
   - Name: `lumc-dodoma`
   - Postgres version: **16** au **17** (si 18 — PostGIS inaweza kukosa)
   - Region: Europe au karibu
3. Baada ya project kuundwa, fungua **SQL Editor** na endesha:

```sql
CREATE DATABASE tanzania_gis_db;
CREATE DATABASE detailed_planning;
```

4. Kwenye kila database (chagua DB kwenye SQL Editor), endesha:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

5. **Connection string** (Dashboard → Connection details):
   - Tumia **pooled** au direct — nakili URI
   - Badilisha jina la database mwishoni kuwa:
     - `.../tanzania_gis_db?sslmode=require`
     - `.../detailed_planning?sslmode=require`

Mfano:
```
postgresql://USER:PASSWORD@ep-xxxx.region.aws.neon.tech/tanzania_gis_db?sslmode=require
postgresql://USER:PASSWORD@ep-xxxx.region.aws.neon.tech/detailed_planning?sslmode=require
```

### Restore dumps kutoka PC

```powershell
cd "D:\MFUMO LUMC\LUMC\tanzania_gis"

.\deploy\scripts\restore-to-render.ps1 `
  -GisUrl "postgresql://USER:PASS@HOST/tanzania_gis_db?sslmode=require" `
  -DetailedUrl "postgresql://USER:PASS@HOST/detailed_planning?sslmode=require" `
  -MainDump ".\deploy\db-dumps\tanzania_gis_db_20260723_120220.dump" `
  -DetailDump ".\deploy\db-dumps\detailed_planning_20260723_120220.dump"
```

---

## B) Render (web bure)

Repo: https://github.com/seifhamisi54-collab/lumc-dodoma

### Blueprint (rahisi)

1. https://dashboard.render.com → Sign up / Login
2. **New** → **Blueprint**
3. Connect GitHub → chagua `seifhamisi54-collab/lumc-dodoma`
4. Apply (`lumc-dodoma` web, plan **Free**)
5. Subiri Docker build (GDAL — dakika 5–15)

### Environment (Web → Environment)

Weka (Replace URL yako baada ya deploy):

| Key | Value |
|-----|--------|
| `DATABASE_URL` | Neon URI → `tanzania_gis_db` |
| `DETAILED_DATABASE_URL` | Neon URI → `detailed_planning` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://lumc-dodoma.onrender.com` |
| `GIS_PORTAL_URL` | `https://lumc-dodoma.onrender.com` |
| `DONATION_SITE_URL` | `https://lumc-dodoma.onrender.com` |
| `DJANGO_ALLOWED_HOSTS` | `lumc-dodoma.onrender.com,.onrender.com` |

(Badilisha `lumc-dodoma.onrender.com` kwa jina halisi Render atakachotoa.)

6. **Manual Deploy** → Clear build cache & deploy (au Restart)

---

## C) Jaribio

- Fungua `https://<jina>.onrender.com/login/`
- Login + ramani
- Request ya kwanza baada ya usingizi inaweza kuchukua dakika 1

---

## Troubleshooting

| Tatizo | Suluhisho |
|--------|-----------|
| Build fail | Angalia Logs — Dockerfile / GDAL |
| DB connection | `sslmode=require` kwenye Neon URI |
| PostGIS missing | Postgres 16/17 + `CREATE EXTENSION postgis` |
| CSRF | `DJANGO_CSRF_TRUSTED_ORIGINS` = URL kamili https |
| Neon storage full | Ondoa data / upgrade baadaye |

---

## Baada ya free kufaulu

Ikiwa unahitaji site isiyolala + storage kubwa: Web Starter + Neon Launch au Render Postgres (paid) — angalia `DEPLOY_RENDER.md`.
