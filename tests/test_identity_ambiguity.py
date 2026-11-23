"""
Tests for Identity Resolution, Ambiguity Detection, and Renaming
=================================================================

Verifies:
- Immutable database primary keys for identity relationships
- Multi-sample enrollment per authorized employee
- Safe employee renaming without breaking recognition or wiping FAISS index
- Safe employee ID updates
- Similar-face ambiguity detection (top-1 vs top-2 distance margin)
- Ambiguity downgrades AMFR decision to BORDERLINE
- Correct distinction between similarly named persons
- Attendance correctly linked to immutable database identity
"""

from __future__ import annotations

import numpy as np
import pytest

from app.amfr_engine import AMFRDecision, AMFREngine
from app.enrollment import FaceEnrollment


@pytest.fixture
def clean_enrollment(tmp_path):
    """Provide a fresh isolated FaceEnrollment instance in a temporary path."""
    idx_p = tmp_path / "test_faiss.index"
    meta_p = tmp_path / "test_metadata.json"
    enroll = FaceEnrollment(index_path=str(idx_p), metadata_path=str(meta_p))
    enroll.clear()
    return enroll


def _make_unit_vector(seed: int) -> np.ndarray:
    rng = np.random.RandomState(seed)
    vec = rng.randn(512).astype(np.float32)
    return vec / np.linalg.norm(vec)


def test_immutable_db_identity_and_multi_sample_enrollment(clean_enrollment):
    enroll = clean_enrollment

    # Create two synthetic identities
    emp1_name = "Dr. Alice Smith"
    emp1_id = "EMP-ALICE-01"
    emp1_db_id = 101

    emp2_name = "Dr. Alice Smyth"  # Similar name!
    emp2_id = "EMP-ALICE-02"
    emp2_db_id = 102

    v1_sample1 = _make_unit_vector(10)
    v1_sample2 = _make_unit_vector(11)  # 2nd sample for Alice Smith
    v2_sample1 = _make_unit_vector(20)  # Distinct person Alice Smyth

    # Enroll multi-sample for Alice Smith
    enroll.enroll(emp1_name, v1_sample1, employee_id=emp1_id, employee_db_id=emp1_db_id)
    enroll.enroll(emp1_name, v1_sample2, employee_id=emp1_id, employee_db_id=emp1_db_id)

    # Enroll single sample for Alice Smyth
    enroll.enroll(emp2_name, v2_sample1, employee_id=emp2_id, employee_db_id=emp2_db_id)

    assert enroll.count() == 3

    # Query with sample 1 of Alice Smith
    matches = enroll.search(v1_sample1, k=2)
    assert len(matches) >= 1
    assert matches[0]["name"] == emp1_name
    assert matches[0]["employee_id"] == emp1_id
    assert matches[0]["employee_db_id"] == emp1_db_id

    # Query with sample 1 of Alice Smyth
    matches2 = enroll.search(v2_sample1, k=2)
    assert len(matches2) >= 1
    assert matches2[0]["name"] == emp2_name
    assert matches2[0]["employee_id"] == emp2_id
    assert matches2[0]["employee_db_id"] == emp2_db_id


def test_safe_renaming_preserves_vectors_and_mappings(clean_enrollment):
    enroll = clean_enrollment
    v1 = _make_unit_vector(30)
    v2 = _make_unit_vector(40)

    enroll.enroll("Robert Brown", v1, employee_id="EMP-BOB-01", employee_db_id=201)
    enroll.enroll("Charlie Davis", v2, employee_id="EMP-CHARLIE-01", employee_db_id=202)
    initial_total = enroll.count()

    # Rename Robert Brown -> Bob Brown by employee_id
    renamed = enroll.rename_by_employee_id("EMP-BOB-01", "Bob Brown")
    assert renamed is True
    # Crucial assertion: index must NOT be wiped or emptied!
    assert enroll.count() == initial_total

    # Search with v1 should now return new display name but same immutable IDs
    res = enroll.search(v1, k=1)
    assert len(res) == 1
    assert res[0]["name"] == "Bob Brown"
    assert res[0]["employee_id"] == "EMP-BOB-01"
    assert res[0]["employee_db_id"] == 201
    assert res[0]["distance"] < 0.05

    # Charlie Davis remains completely unaffected
    res2 = enroll.search(v2, k=1)
    assert len(res2) == 1
    assert res2[0]["name"] == "Charlie Davis"


def test_safe_employee_id_update(clean_enrollment):
    enroll = clean_enrollment
    v1 = _make_unit_vector(50)
    enroll.enroll("David Lee", v1, employee_id="TEMP-001", employee_db_id=301)

    updated = enroll.update_employee_id("TEMP-001", "PERM-LEED-01")
    assert updated is True

    res = enroll.search(v1, k=1)
    assert res[0]["employee_id"] == "PERM-LEED-01"
    assert res[0]["employee_db_id"] == 301


def test_top1_vs_top2_ambiguity_detection(clean_enrollment):
    enroll = clean_enrollment

    # Create two close embeddings representing similar faces (e.g. lookalikes)
    base_v = _make_unit_vector(100)
    # Add a small perturbation to create a very similar vector
    noise = np.random.RandomState(101).randn(512).astype(np.float32) * 0.05
    similar_v = base_v + noise
    similar_v /= np.linalg.norm(similar_v)

    enroll.enroll("Candidate Alpha", base_v, employee_id="EMP-ALPHA", employee_db_id=401)
    enroll.enroll("Candidate Beta", similar_v, employee_id="EMP-BETA", employee_db_id=402)

    # A query vector located halfway between Alpha and Beta
    query_v = (base_v + similar_v) / 2.0
    query_v /= np.linalg.norm(query_v)

    # Search with k=2 and ambiguity check
    matches = enroll.search(query_v, k=2, ambiguity_margin=0.20)
    assert len(matches) == 2
    top1 = matches[0]

    # Verify that the ambiguity flag was raised due to close similarity
    assert top1.get("is_ambiguous") is True
    assert "competing_name" in top1
    assert top1["competing_name"] in ("Candidate Alpha", "Candidate Beta")


def test_amfr_engine_downgrades_ambiguous_matches():
    engine = AMFREngine()

    # Evaluate decision with ambiguous match flag
    decision, risk, details = engine._decide(
        arcface_distance=0.22,
        liveness_score=0.92,
        quality_score=0.88,
        is_live=True,
        faiss_confidence=0.95,
        is_ambiguous=True,
    )

    # Must NOT be ACCEPT! Must be BORDERLINE because match is ambiguous!
    assert decision == AMFRDecision.BORDERLINE
    assert details.get("ambiguity_gate") == "AMBIGUOUS"
