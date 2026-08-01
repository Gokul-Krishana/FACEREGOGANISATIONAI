# Backups

Generated backup artifacts are stored here and are **git-ignored**
(see `.gitignore`: `backups/*`, `!backups/README.md`).

## What's generated

`scripts/backup.py` writes a timestamped subdirectory per backup run:

- `face_recognition.sql` — SQL dump of the database
- `faiss.index` — FAISS embeddings index snapshot
- `metadata.json` — embedding metadata
- `manifest.json` — backup manifest (run metadata, checksums)

`scripts/restore.py` restores a backup from a selected snapshot.

## Why not committed

These files are large, machine-generated artifacts that change on every
run. Keeping them out of version control avoids bloating the repository
with binary/index dumps.

## Keeping the directory

The `!backups/README.md` negation keeps this documentation tracked so the
directory structure survives a fresh clone.
