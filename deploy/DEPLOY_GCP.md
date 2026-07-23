# LUMC-Dodoma — Deploy kwenye Google Cloud
>
> **Sasa tunatumia Render** — angalia [`DEPLOY_RENDER.md`](./DEPLOY_RENDER.md).
> Faili hii inabaki kama chaguo la GCP VM.

**URL lengwa:** `https://lumc-dodoma.duckdns.org`  
**Watumiaji:** ~50  
**Stack:** GCE VM + Docker Compose (Django + PostGIS + Nginx)
> PostGIS kwenye PC haitumiki moja kwa moja — data itahamishwa kwenda VM.

---

## A) Kwenye PC yako (Windows)

### 1. Dump database
PowerShell (katika folder `tanzania_gis`):

```powershell
.\deploy\scripts\dump-local-db.ps1
```

Ikiwa `pg_dump` haipo PATH, weka path kamili:

```powershell
.\deploy\scripts\dump-local-db.ps1 -PgDump "C:\Program Files\PostgreSQL\13\bin\pg_dump.exe"
```

Faili zitaonekana kwenye `deploy\db-dumps\`.

### 2. Pakia mradi + dumps kwenye VM
Tumia `gcloud compute scp` au WinSCP baada ya VM kuundwa.

---

## B) DuckDNS (subdomain bure)

1. Fungua https://www.duckdns.org — login na Google
2. Unda domain: **`lumc-dodoma`** → itakuwa `lumc-dodoma.duckdns.org`
3. Nakili **token**
4. Baada ya VM kuwa na IP ya nje, weka IP hiyo kwenye DuckDNS (au tumia `deploy/scripts/update-duckdns.sh`)

---

## C) Google Cloud — unda VM

1. https://console.cloud.google.com → wezesha **Compute Engine**
2. **Create Instance:**
   - Name: `lumc-dodoma`
   - Region: `europe-west1` (au karibu nawe)
   - Machine: **e2-medium** (2 vCPU / 4 GB) — salama kwa GIS
   - Boot disk: Ubuntu 22.04 LTS, **50 GB SSD**
   - Firewall: allow HTTP + HTTPS
3. **VPC firewall** (ikiwa inahitajika): allow tcp:80, tcp:443, tcp:22
4. Nakili **External IP** → weka kwenye DuckDNS

### Sakinisha Docker kwenye VM (SSH)

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# logout / login tena
sudo apt install -y docker-compose-plugin
```

### Pakia mradi

```bash
# mfano
mkdir -p ~/lumc && cd ~/lumc
# scp / git clone mradi hapa
cd tanzania_gis   # folder yenye docker-compose.yml
```

### Environment

```bash
cp deploy/.env.production.example .env.production
nano .env.production
```

Badilisha:
- `DJANGO_SECRET_KEY` (string ndefu random)
- `DB_PASSWORD`
- `DUCKDNS_TOKEN`

```bash
chmod +x deploy/entrypoint.sh deploy/init-db/*.sh deploy/scripts/*.sh
mkdir -p deploy/nginx/ssl deploy/certbot/www deploy/db-dumps
```

### Anzisha

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f web
```

Fungua browser: `http://lumc-dodoma.duckdns.org`

---

## D) Hamisha data (restore dumps)

Nakili dumps kwenda VM `deploy/db-dumps/`, kisha:

```bash
chmod +x deploy/scripts/restore-to-docker.sh
./deploy/scripts/restore-to-docker.sh \
  ./deploy/db-dumps/tanzania_gis_db_XXXX.dump \
  ./deploy/db-dumps/detailed_planning_XXXX.dump
docker compose restart web
```

---

## E) HTTPS (Let’s Encrypt)

```bash
sudo apt install -y certbot
sudo docker compose stop nginx
sudo certbot certonly --standalone -d lumc-dodoma.duckdns.org
sudo cp /etc/letsencrypt/live/lumc-dodoma.duckdns.org/fullchain.pem deploy/nginx/ssl/
sudo cp /etc/letsencrypt/live/lumc-dodoma.duckdns.org/privkey.pem deploy/nginx/ssl/
sudo chmod 644 deploy/nginx/ssl/*.pem
```

Kisha fungua SSL block ndani ya `deploy/nginx/default.conf` (sehemu iliyocomment), kisha:

```bash
docker compose up -d nginx
```

Au tumia certbot nginx plugin baada ya HTTP kuwa live.

**Renew:** cron `certbot renew` + copy pems + `docker compose restart nginx`

---

## F) Checklist ya jaribio

- [ ] `https://lumc-dodoma.duckdns.org` inafunguka
- [ ] Login inafanya kazi
- [ ] Ramani / wilaya zinaonekana
- [ ] Upload SHP ndogo inafanya kazi
- [ ] Locality / Mpango SHP vinafanya kazi
- [ ] Port 5432 **haifunguliwi** kwa internet

---

## Gharama

| Kipengele | Takriban |
|-----------|----------|
| e2-medium VM | ~USD 25–35 / mwezi |
| Disk 50GB | ~USD 8 / mwezi |
| DuckDNS | Bure |

---

## Troubleshooting

- **502 Bad Gateway:** `docker compose logs web`
- **DB connection:** `docker compose exec db pg_isready -U postgres`
- **GDAL error:** hakikisha container `web` ina `GDAL_LIBRARY_PATH`
- **CSRF failed:** hakikisha `DJANGO_CSRF_TRUSTED_ORIGINS` ina `https://lumc-dodoma.duckdns.org`
