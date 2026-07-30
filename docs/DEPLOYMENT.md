# Deployment Guide — Face Recognition AI

## Quick Start (Development)

```bash
# 1. Clone and install
git clone https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI.git
cd FaceRecognitionAI
pip install -r requirements.txt

# 2. Run startup validation
python tools/validate_startup.py

# 3. Start Streamlit dashboard
streamlit run dashboard/app.py

# 4. Open in browser
# http://localhost:8501
```

## Docker Deployment (Production)

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Start Services

```bash
# Build and start all services
docker compose up -d

# Run database migrations
docker compose exec api alembic upgrade head

# View logs
docker compose logs -f api
docker compose logs -f dashboard
```

### Services Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Docker Network                         │
│                                                          │
│  ┌──────────────┐      ┌──────────────┐                 │
│  │   Streamlit   │      │   FastAPI    │                 │
│  │  Dashboard    │      │   Backend    │                 │
│  │  :8501        │      │  :8000       │                 │
│  └──────┬───────┘      └──────┬───────┘                 │
│         │                     │                          │
│         └─────────┬───────────┘                          │
│                   │                                      │
│          ┌────────┴────────┐                             │
│          │   PostgreSQL    │    ┌──────────┐             │
│          │   :5432         │    │  Redis   │             │
│          │   faceai:changeme│   │  :6379   │             │
│          └─────────────────┘    └──────────┘             │
└─────────────────────────────────────────────────────────┘
```

| Service | Port | Purpose |
|:--------|:----:|:--------|
| **Streamlit Dashboard** | 8501 | Operator UI (primary interface) |
| **FastAPI Backend** | 8000 | REST API + rate limiting |
| **PostgreSQL** | 5432 | Persistent database |
| **Redis** | 6379 | Cache & cooldowns (optional) |

## Configuration

### Environment Variables

| Variable | Default | Description |
|:---------|:-------:|:------------|
| `DB_TYPE` | `sqlite` | Database backend: `sqlite` or `postgres` |
| `DATABASE_URL` | — | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection (optional) |
| `SECRET_KEY` | `dev-secret-...` | JWT signing key (⚠️ CHANGE IN PROD) |
| `ENVIRONMENT` | `development` | `development` or `production` |

### settings.yaml

Edit `config/settings.yaml` for runtime configuration without touching Python code:

```yaml
camera:
  source_type: webcam       # webcam | android_wifi | ip_camera | etc.
  id: 0
  width: 640
  height: 480

recognition:
  yolo_confidence: 0.5
  recognition_threshold: 1.2
  frame_skip: 4             # Higher = faster but fewer recognitions
  cooldown_seconds: 60

faiss:
  index_type: hnsw          # flat | hnsw | ivf
  hnsw:
    M: 32
    ef_search: 128

amfr:
  high_confidence_threshold: 0.70
  borderline_threshold: 0.40
```

## Production Checklist

### Essential

- [ ] **`SECRET_KEY`** set to random 64+ character string
- [ ] **`ENVIRONMENT=production`**
- [ ] PostgreSQL configured with persistent volume
- [ ] Database migrations applied (`alembic upgrade head`)
- [ ] Startup validation passes (`python tools/validate_startup.py`)

### Security

- [ ] Firewall restricts ports 5432 and 6379 to localhost/docker network
- [ ] Redis configured with password
- [ ] HTTPS configured via reverse proxy (nginx/Caddy)
- [ ] Rate limiting enabled for API endpoints
- [ ] Audit logging configured

### Operations

- [ ] Monitoring/alerts configured
- [ ] Regular backups scheduled
- [ ] Log rotation configured
- [ ] Health check endpoints verified (`/_stcore/health`, `/health`)

## Startup Validation

Always run startup validation before deploying:

```bash
python tools/validate_startup.py
```

### Expected Output (Healthy System)

```
============================================================
  STARTUP VALIDATION — Face Recognition AI
============================================================

[1/6] Python & Environment      ✅  PASS
[2/6] Core Dependencies         ✅  PASS
[3/6] Project Modules           ✅  PASS  (30/31)
[4/6] AI Models                 ✅  PASS
[5/6] FAISS Index               ✅  PASS
[6/6] Database & Migrations     ✅  PASS

⚠️  Redis — optional, not required
============================================================
  RESULT: All critical checks passed — system is healthy
============================================================
```

## Backup & Restore

### PostgreSQL Backup

```bash
# Daily backup
pg_dump -U faceai face_recognition > backup_$(date +%Y%m%d).sql

# Restore
psql -U faceai face_recognition < backup_20260730.sql
```

### FAISS Index Backup

```bash
# Backup
cp embeddings/faiss.index embeddings/backup_$(date +%Y%m%d).index
cp embeddings/metadata.json embeddings/backup_$(date +%Y%m%d).json

# Restore
cp embeddings/backup_20260730.index embeddings/faiss.index
cp embeddings/backup_20260730.json embeddings/metadata.json
```

### Automated Backup Script

```bash
#!/bin/bash
# backup.sh — run daily via cron
BACKUP_DIR=/backups/faceai
mkdir -p $BACKUP_DIR

# Database
pg_dump -U faceai face_recognition > $BACKUP_DIR/db_$(date +%Y%m%d).sql

# FAISS index
cp embeddings/faiss.index $BACKUP_DIR/faiss_$(date +%Y%m%d).index
cp embeddings/metadata.json $BACKUP_DIR/metadata_$(date +%Y%m%d).json

# Keep last 30 days
find $BACKUP_DIR -name "*.sql" -mtime +30 -delete
find $BACKUP_DIR -name "*.index" -mtime +30 -delete
find $BACKUP_DIR -name "*.json" -mtime +30 -delete
```

## Docker Commands Reference

```bash
# Build and start
docker compose up -d

# Stop
docker compose down

# View logs
docker compose logs -f

# Rebuild single service
docker compose build api
docker compose up -d api

# Run migrations
docker compose exec api alembic upgrade head

# Check health
curl http://localhost:8000/health
curl http://localhost:8000/health/ready

# Shell access
docker compose exec api bash
docker compose exec dashboard bash
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose logs api

# Check port conflicts
netstat -tlnp | grep -E '8501|8000|5432|6379'

# Rebuild from scratch
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

### Database connection failed

```bash
# Check PostgreSQL is running
docker compose ps

# Check connection string
docker compose exec api env | grep DATABASE_URL

# Manually test
docker compose exec api python -c "
from database.database import get_session
with get_session() as s:
    print('Connected:', s.bind.url)
"
```

### See Also

- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Common issues & solutions
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design & component map
