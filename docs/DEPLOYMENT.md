# Deployment Guide

## Quick Start (Development)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run startup validation
python tools/validate_startup.py

# 3. Start Streamlit dashboard
streamlit run dashboard/app.py

# 4. (Optional) Start FastAPI server
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## Docker Deployment (Production)

```bash
# Start all services
docker compose up -d

# Run database migrations
docker compose exec api alembic upgrade head

# View logs
docker compose logs -f api
```

### Services

| Service | Port | Purpose |
|---------|------|---------|
| Streamlit Dashboard | 8501 | Operator UI |
| FastAPI Backend | 8000 | REST API |
| PostgreSQL | 5432 | Persistent storage |
| Redis | 6379 | Cache & cooldowns |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_TYPE` | `sqlite` | Database type: `sqlite` or `postgres` |
| `DATABASE_URL` | — | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `SECRET_KEY` | `dev-secret-...` | JWT signing key (change in prod) |
| `ENVIRONMENT` | `development` | `development` or `production` |

### settings.yaml

Edit `config/settings.yaml` for runtime configuration:
- Camera source and resolution
- Recognition thresholds
- FAISS index type (flat, hnsw, ivf)
- AMFR weights
- Face quality / liveness thresholds
- Logging level

## Startup Validation

Always run startup validation before deploying:

```bash
python tools/validate_startup.py
```

Expected output for a healthy system:

```
✅ [PASS ] Configuration
✅ [PASS ] YOLO Model
✅ [PASS ] InsightFace
✅ [PASS ] FAISS Index
✅ [PASS ] AMFR Engine
✅ [PASS ] Database
⚠️  [WARN ] Redis (optional)
```

## Production Checklist

- [ ] `SECRET_KEY` set to a random 64+ character string
- [ ] `ENVIRONMENT=production`
- [ ] PostgreSQL configured with persistent volume
- [ ] Redis configured with password
- [ ] Database migrations applied (`alembic upgrade head`)
- [ ] Startup validation passes
- [ ] Firewall restricts ports 5432 and 6379 to localhost
- [ ] HTTPS configured for production API
- [ ] Regular backups configured (database + FAISS index + metadata)
- [ ] Monitoring/alerts configured

## Backup

### PostgreSQL
```bash
pg_dump -U faceai face_recognition > backup_$(date +%Y%m%d).sql
```

### FAISS Index
```bash
cp embeddings/faiss.index embeddings/backup_$(date +%Y%m%d).index
cp embeddings/metadata.json embeddings/backup_$(date +%Y%m%d).json
```

### Restore
```bash
psql -U faceai face_recognition < backup_20260730.sql
cp embeddings/backup_20260730.index embeddings/faiss.index
cp embeddings/backup_20260730.json embeddings/metadata.json
```

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues.
