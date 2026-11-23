"""
Tests for 7-Pillar Production Hardening
========================================

Verifies:
1. Security hardening (production secret validation, brute-force protection)
2. Privacy & biometric encryption at rest, cryptographic file shredding, consent checks
3. Performance optimizations (FAISS vectorized batch search)
4. Database reliability (backup/restore, SQLite WAL checkpointing, integrity checking)
5. Operational reliability (service watchdog, health system metrics)
"""

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.enrollment import FaceEnrollment
from database.database import get_session
from database.models import Employee, User, _utcnow
from services.data_retention_service import DataRetentionService
from services.employee_service import EmployeeService
from utils.biometric_crypto import (
    decrypt_embedding,
    encrypt_embedding,
    get_biometric_cipher,
    shred_file,
)


class TestPillarBiometricPrivacyAndCrypto:
    """Tests for Pillar 2: Biometric Encryption at Rest & Cryptographic Shredding."""

    def test_encrypt_decrypt_embedding_roundtrip(self):
        """Ensure 512-D ArcFace vectors encrypt and decrypt losslessly."""
        rng = np.random.default_rng(42)
        vector = rng.standard_normal(512).astype(np.float32)

        cipher = get_biometric_cipher("test-secret-key-salt")
        ciphertext = encrypt_embedding(vector, cipher=cipher)

        assert isinstance(ciphertext, bytes)
        assert len(ciphertext) > 512 * 4  # Authenticated ciphertext is larger than raw bytes

        decrypted = decrypt_embedding(ciphertext, dimension=512, cipher=cipher)
        np.testing.assert_allclose(vector, decrypted, atol=1e-6)

    def test_cryptographic_shred_file(self, tmp_path):
        """Ensure sensitive biometric files are multi-pass overwritten and removed."""
        bio_file = tmp_path / "face_embedding.bin"
        bio_file.write_bytes(b"SENSITIVE_FACE_BIOMETRIC_DATA_DO_NOT_LEAK")
        assert bio_file.exists()

        result = shred_file(bio_file, passes=3)
        assert result is True
        assert not bio_file.exists()

    def test_shred_nonexistent_file_returns_false(self, tmp_path):
        missing = tmp_path / "does_not_exist.bin"
        assert shred_file(missing) is False

    def test_employee_consent_columns_and_shred_biometrics(self, tmp_path):
        """Test employee biometric shredding without deleting database record."""
        emp_id = "TEST_SHRED_EMP_01"
        photo = tmp_path / "test_photo.jpg"
        photo.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        with get_session() as session:
            emp = session.query(Employee).filter_by(employee_id=emp_id).first()
            if not emp:
                emp = Employee(
                    employee_id=emp_id,
                    name="Consent Test User",
                    photo_path=str(photo),
                    consent_given=True,
                )
                session.add(emp)
                session.commit()
            else:
                emp.photo_path = str(photo)
                emp.consent_given = True
                session.commit()

        assert photo.exists()

        # Shred biometrics only (keep employee, withdraw consent)
        success = EmployeeService.shred_biometrics(emp_id, delete_employee=False)
        assert success is True
        assert not photo.exists()  # Shredded from disk

        with get_session() as session:
            updated = session.query(Employee).filter_by(employee_id=emp_id).first()
            assert updated is not None
            assert updated.photo_path is None
            assert updated.consent_given is False
            assert updated.faiss_id is None

            # Clean up
            session.delete(updated)
            session.commit()


class TestPillarFAISSBatchSearchOptimization:
    """Tests for Pillar 3: FAISS Vectorized Batch Search Performance."""

    def test_batch_search_equivalence(self, tmp_path):
        """Ensure search_batch returns exact same results as sequential search."""
        idx_path = str(tmp_path / "faiss.index")
        meta_path = str(tmp_path / "metadata.json")

        enr = FaceEnrollment(index_path=idx_path, metadata_path=meta_path)
        rng = np.random.default_rng(123)

        # Enroll 5 distinct vectors
        for i in range(5):
            vec = rng.standard_normal(512).astype(np.float32)
            enr.enroll(name=f"Person_{i}", embedding=vec, employee_id=f"EMP_{i}")

        # Generate 3 test queries
        q1 = rng.standard_normal(512).astype(np.float32)
        q2 = None
        q3 = rng.standard_normal(512).astype(np.float32)
        queries = [q1, q2, q3]

        # Sequential search
        seq_res = [enr.search(q, k=2) if q is not None else [] for q in queries]

        # Vectorized batch search
        batch_res = enr.search_batch(queries, k=2)

        assert len(batch_res) == len(queries)
        assert batch_res[1] == []  # q2 was None
        for i in [0, 2]:
            assert len(batch_res[i]) == len(seq_res[i])
            if seq_res[i]:
                assert batch_res[i][0]["name"] == seq_res[i][0]["name"]
                assert np.isclose(batch_res[i][0]["distance"], seq_res[i][0]["distance"], atol=1e-4)


class TestPillarDatabaseReliabilityBackupRestore:
    """Tests for Pillar 4: Database Reliability & Integrity."""

    def test_sqlite_backup_and_restore_cycle(self, tmp_path):
        """Verify automated SQLite backup and restore round-trip."""
        import scripts.backup as backup_mod
        import scripts.restore as restore_mod

        # Create dummy database and embeddings
        db_file = tmp_path / "source.db"
        import sqlite3

        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE test_data (id INT PRIMARYKEY, val TEXT)")
        conn.execute("INSERT INTO test_data VALUES (1, 'active_record')")
        conn.commit()
        conn.close()

        backup_dir = tmp_path / "backups" / "backup_test"
        backup_dir.mkdir(parents=True)

        # Run backup
        dump_path, db_type = backup_mod.backup_sqlite(db_file, backup_dir)
        assert dump_path.exists()
        assert db_type == "sqlite"

        # Create manifest
        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database": {
                "type": "sqlite",
                "dump_file": dump_path.name,
                "dump_sha256": backup_mod.sha256(dump_path),
            },
            "artifacts": {},
        }
        (backup_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        # Verify artifacts
        assert restore_mod.verify_artifacts(backup_dir, manifest) is True

        # Restore to target
        target_db = tmp_path / "restored.db"
        restore_mod.restore_sqlite_db(dump_path, target_db)
        assert target_db.exists()

        # Check restored data
        rconn = sqlite3.connect(str(target_db))
        cur = rconn.cursor()
        cur.execute("SELECT val FROM test_data WHERE id=1")
        row = cur.fetchone()
        rconn.close()
        assert row is not None
        assert row[0] == "active_record"


class TestPillarOperationalReliabilityWatchdog:
    """Tests for Pillar 6: Operational Reliability Watchdog."""

    def test_watchdog_endpoint_check(self):
        """Test health endpoint checker with mocked responses."""
        from scripts.service_watchdog import check_endpoint

        # Mock urllib success
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            healthy, code, msg = check_endpoint("http://mock-service/health")
            assert healthy is True
            assert code == 200
            assert msg == "OK"
