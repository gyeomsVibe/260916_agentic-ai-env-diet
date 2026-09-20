"""
Tests for Context Lease validation (Acceptance #1).
"""

import unittest
from datetime import datetime, timedelta, timezone

from v7_harness.context_lease import (
    ContextLease,
    ContextLeaseValidator,
)


class TestContextLease(unittest.TestCase):

    def setUp(self):
        self.validator = ContextLeaseValidator()
        self.now = datetime.now(timezone.utc)
        self.past = (self.now - timedelta(hours=2)).isoformat()
        self.future = (self.now + timedelta(hours=2)).isoformat()
        self.far_past = (self.now - timedelta(hours=5)).isoformat()

    def test_valid_active_lease(self):
        lease = ContextLease(
            lease_id="L-001",
            document_path="docs/spec.md",
            authority="APPROVED-DESIGN",
            scope=["v7_harness/*"],
            created_at=self.past,
            expires_at=self.future,
            tier="Tier 1",
        )
        res = self.validator.validate_lease(lease, reference_time=self.now, target_scope="v7_harness/cli.py")
        self.assertTrue(res.valid)
        self.assertEqual(res.errors, [])

    def test_expired_lease_fails_closed(self):
        lease = ContextLease(
            lease_id="L-002",
            document_path="docs/old_spec.md",
            authority="APPROVED-DESIGN",
            scope=["*"],
            created_at=self.far_past,
            expires_at=self.past,  # Expired
        )
        res = self.validator.validate_lease(lease, reference_time=self.now)
        self.assertFalse(res.valid)
        self.assertTrue(any("expired" in err.lower() for err in res.errors))

    def test_unauthorized_authority_rejected(self):
        lease = ContextLease(
            lease_id="L-003",
            document_path="docs/spec.md",
            authority="UNVERIFIED",  # Not in acceptable active authorities
            scope=["*"],
            created_at=self.past,
            expires_at=self.future,
        )
        res = self.validator.validate_lease(lease, reference_time=self.now)
        self.assertFalse(res.valid)
        self.assertTrue(any("not acceptable" in err for err in res.errors))

    def test_scope_mismatch_rejected(self):
        lease = ContextLease(
            lease_id="L-004",
            document_path="docs/spec.md",
            authority="FACT",
            scope=["docs/*"],
            created_at=self.past,
            expires_at=self.future,
        )
        res = self.validator.validate_lease(lease, reference_time=self.now, target_scope="src/main.py")
        self.assertFalse(res.valid)
        self.assertTrue(any("does not match lease scope" in err for err in res.errors))

    def test_superseded_lease_invalidated(self):
        lease_old = ContextLease(
            lease_id="L-OLD",
            document_path="docs/spec_v1.md",
            authority="APPROVED-DESIGN",
            scope=["*"],
            created_at=self.far_past,
            expires_at=self.future,
        )
        lease_new = ContextLease(
            lease_id="L-NEW",
            document_path="docs/spec_v2.md",
            authority="APPROVED-DESIGN",
            scope=["*"],
            created_at=self.past,
            expires_at=self.future,
            supersedes=["L-OLD"],
        )
        results, valid_ids = self.validator.validate_lease_set([lease_old, lease_new], reference_time=self.now)
        self.assertIn("L-NEW", valid_ids)
        self.assertNotIn("L-OLD", valid_ids)
        self.assertFalse(results["L-OLD"].valid)
        self.assertTrue(any("superseded" in err for err in results["L-OLD"].errors))


if __name__ == "__main__":
    unittest.main()
