"""Unit and integration tests for Two-Person OTP Authorization in DealRecall."""

import json
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

from dealrecall.agent import run_brief
from dealrecall.security import (
    OPERATION_DELETE_DEAL,
    OPERATION_EDIT_DEAL,
    OPERATION_LOG_INTERACTION,
    SecurityManager,
    generate_otp,
    get_authorized_users,
    hash_otp,
    verify_otp_hash,
)
from dealrecall.store import Store, is_overdue


class MockMemory:
    """Mock Hindsight Memory client for testing retain and recall."""

    def __init__(self):
        self.retained_interactions = []
        self.recalled_deals = []
        self.recalled_playbooks = []

    def retain_interaction(self, deal: dict, row: dict) -> None:
        self.retained_interactions.append({"deal": deal, "row": row})

    def recall_deal(self, slug: str, question: str) -> list[dict]:
        self.recalled_deals.append((slug, question))
        return [
            {
                "text": "Priya Shah is the VP of Operations and champion for DealRecall.",
                "type": "world",
                "tags": [f"deal:{slug}"],
                "metadata": {"deal": "Northwind Logistics"},
            }
        ]

    def recall_playbook(self, question: str) -> list[dict]:
        self.recalled_playbooks.append(question)
        return [
            {
                "text": "Meridian Health refused early discount and closed at full price.",
                "type": "experience",
                "tags": ["playbook"],
                "metadata": {"deal": "Meridian Health"},
            }
        ]


class MockGroq:
    """Mock Groq client for testing briefing workflow."""

    def __init__(self, response_text: str = ""):
        self.response_text = response_text or (
            "1. Deal Summary\nNorthwind Logistics is evaluating security compliance.\n"
            "2. Key Stakeholders\nPriya Shah is the champion.\n"
            "3. Objection Handling\nPrice and security architecture.\n"
            "4. Competitor Differentiation\nCargoFlow is cheaper but less secure.\n"
            "5. Open Commitments\nSend two-page security note.\n"
            "6. Recommended Discovery Questions\n1. What does Anil Deshpande require before signing?"
        )
        self.chat = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = self.response_text
        mock_choice.message.tool_calls = None
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        self.chat.completions.create.return_value = mock_completion


class OtpSecurityTests(unittest.TestCase):
    def setUp(self):
        import os
        self.orig_test_otp = os.environ.get("DEALRECALL_TEST_OTP")
        os.environ["DEALRECALL_TEST_OTP"] = ""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_dealrecall.db"
        self.outbox_path = Path(self.temp_dir.name) / "dev_otp_outbox.json"
        self.store = Store(self.db_path)
        self.sec = SecurityManager(
            self.store,
            outbox_path=self.outbox_path,
            expiry_seconds=300,
            max_attempts=5,
        )
        self.user_a, self.user_b = get_authorized_users()
        self.memory = MockMemory()

    def tearDown(self):
        import os
        if self.orig_test_otp is not None:
            os.environ["DEALRECALL_TEST_OTP"] = self.orig_test_otp
        else:
            os.environ["DEALRECALL_TEST_OTP"] = "090904"
        self.temp_dir.cleanup()

    def _get_delivered_otps(self) -> dict[str, str]:
        """Read plaintext OTPs from the developer outbox file for testing."""
        if not self.outbox_path.exists():
            return {}
        with open(self.outbox_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        otps = {}
        for entry in entries:
            otps[entry["recipient"]] = entry["otp"]
        return otps

    # 1. OTP generation produces a valid 6-digit OTP
    def test_otp_generation_produces_valid_six_digits(self):
        for _ in range(50):
            otp = generate_otp()
            self.assertEqual(len(otp), 6)
            self.assertTrue(otp.isdigit())
            val = int(otp)
            self.assertGreaterEqual(val, 0)
            self.assertLess(val, 1_000_000)

    # 2. OTP expires correctly
    def test_otp_expires_correctly(self):
        short_sec = SecurityManager(
            self.store,
            outbox_path=self.outbox_path,
            expiry_seconds=1,  # 1 second expiry
            max_attempts=5,
        )
        req = short_sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={"company": "Northwind Logistics", "notes": "Security review meeting"},
        )
        otps = self._get_delivered_otps()
        # Wait 1.1s for expiration
        time.sleep(1.1)

        result = short_sec.verify_user_otp(
            approval_id=req["id"],
            user_name=self.user_a,
            otp=otps[self.user_a],
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.status, "expired")
        self.assertIn("expired", result.message.lower())

    # 3. Correct OTP succeeds
    def test_correct_otp_succeeds(self):
        req = self.sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={"company": "Northwind Logistics", "notes": "Call notes"},
        )
        otps = self._get_delivered_otps()
        res_a = self.sec.verify_user_otp(
            approval_id=req["id"],
            user_name=self.user_a,
            otp=otps[self.user_a],
        )
        self.assertTrue(res_a.ok)
        self.assertTrue(res_a.first_verified)
        self.assertFalse(res_a.second_verified)
        self.assertEqual(res_a.status, "partially_verified")

        res_b = self.sec.verify_user_otp(
            approval_id=req["id"],
            user_name=self.user_b,
            otp=otps[self.user_b],
        )
        self.assertTrue(res_b.ok)
        self.assertTrue(res_b.first_verified)
        self.assertTrue(res_b.second_verified)
        self.assertEqual(res_b.status, "approved")

    # 4. Incorrect OTP fails
    def test_incorrect_otp_fails(self):
        req = self.sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={"company": "Northwind Logistics", "notes": "Call notes"},
        )
        otps = self._get_delivered_otps()
        wrong_otp = "000000" if otps[self.user_a] != "000000" else "111111"

        res = self.sec.verify_user_otp(
            approval_id=req["id"],
            user_name=self.user_a,
            otp=wrong_otp,
        )
        self.assertFalse(res.ok)
        self.assertEqual(res.status, "invalid_otp")
        self.assertIn("Invalid OTP", res.message)
        self.assertEqual(res.attempts_left, 4)

    # 5. OTP cannot be reused
    def test_otp_cannot_be_reused(self):
        req = self.sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={"company": "Northwind Logistics", "notes": "Call notes"},
        )
        otps = self._get_delivered_otps()
        res_first = self.sec.verify_user_otp(
            approval_id=req["id"],
            user_name=self.user_a,
            otp=otps[self.user_a],
        )
        self.assertTrue(res_first.ok)

        # Attempt to verify again with the exact same OTP for User A
        res_second = self.sec.verify_user_otp(
            approval_id=req["id"],
            user_name=self.user_a,
            otp=otps[self.user_a],
        )
        self.assertFalse(res_second.ok)
        self.assertEqual(res_second.status, "already_verified")

    # 6. User A cannot approve as User B
    def test_user_a_cannot_approve_as_user_b(self):
        req = self.sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={"company": "Northwind Logistics", "notes": "Call notes"},
        )
        otps = self._get_delivered_otps()

        # User A attempts to enter User B's OTP under User A's identity
        res_wrong_otp = self.sec.verify_user_otp(
            approval_id=req["id"],
            user_name=self.user_a,
            otp=otps[self.user_b],
        )
        self.assertFalse(res_wrong_otp.ok)
        self.assertEqual(res_wrong_otp.status, "invalid_otp")

        # Unauthorized third party attempts to approve
        res_unauthorized = self.sec.verify_user_otp(
            approval_id=req["id"],
            user_name="Eve",
            otp="123456",
        )
        self.assertFalse(res_unauthorized.ok)
        self.assertEqual(res_unauthorized.status, "unauthorized")

    # 7. Same user cannot provide both approvals
    def test_same_user_cannot_provide_both_approvals(self):
        req = self.sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={"company": "Northwind Logistics", "notes": "Call notes"},
        )
        otps = self._get_delivered_otps()

        # User A verifies User A's slot
        res_a = self.sec.verify_user_otp(
            approval_id=req["id"],
            user_name=self.user_a,
            otp=otps[self.user_a],
        )
        self.assertTrue(res_a.ok)

        # User A tries to also verify User B's slot
        res_a_again = self.sec.verify_user_otp(
            approval_id=req["id"],
            user_name=self.user_a,
            otp=otps[self.user_b],
        )
        self.assertFalse(res_a_again.ok)
        self.assertEqual(res_a_again.status, "already_verified")

        # Session should still only be partially verified
        session = self.sec.get_session_status(req["id"])
        self.assertEqual(session["status"], "partially_verified")
        self.assertFalse(session["user_b_verified"])

    # 8. One approval alone does NOT save
    def test_one_approval_alone_does_not_save(self):
        initial_count = len(self.store.interactions())
        req = self.sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={
                "company": "Northwind Logistics",
                "notes": "Sensitive security disclosure note",
                "contact": "Raj Malhotra",
                "interaction_type": "Working session",
                "happened": "2026-10-01",
                "result": "advanced",
            },
        )
        otps = self._get_delivered_otps()
        self.sec.verify_user_otp(
            approval_id=req["id"],
            user_name=self.user_a,
            otp=otps[self.user_a],
        )

        # Attempt to commit with only one approval
        commit_res = self.sec.commit_approved_operation(
            approval_id=req["id"],
            memory=self.memory,
        )
        self.assertFalse(commit_res.ok)
        self.assertTrue(
            "unapproved request" in commit_res.message.lower()
            or "both authorized users must be verified" in commit_res.message.lower()
        )

        # Persistence check: store must remain unchanged
        self.assertEqual(len(self.store.interactions()), initial_count)
        self.assertEqual(len(self.memory.retained_interactions), 0)

    # 9. Two approvals DO allow save
    def test_two_approvals_do_allow_save(self):
        initial_count = len(self.store.interactions())
        req = self.sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={
                "company": "Northwind Logistics",
                "notes": "Security architecture approved by InfoSec",
                "contact": "Raj Malhotra",
                "interaction_type": "Working session",
                "happened": "2026-10-01",
                "result": "advanced",
                "promise_what": "Deliver compliance certificate",
                "promise_who": "Raj Malhotra",
                "promise_due": "2026-10-05",
            },
        )
        otps = self._get_delivered_otps()
        self.sec.verify_user_otp(
            approval_id=req["id"],
            user_name=self.user_a,
            otp=otps[self.user_a],
        )
        self.sec.verify_user_otp(
            approval_id=req["id"],
            user_name=self.user_b,
            otp=otps[self.user_b],
        )

        commit_res = self.sec.commit_approved_operation(
            approval_id=req["id"],
            memory=self.memory,
        )
        self.assertTrue(commit_res.ok)
        self.assertEqual(len(self.store.interactions()), initial_count + 1)
        self.assertTrue(commit_res.hindsight_retained)

        # Check commitments updated
        promises = self.store.commitments("northwind-logistics")
        new_promise = next((p for p in promises if "compliance certificate" in p["what"].lower()), None)
        self.assertIsNotNone(new_promise)

    # 10. Cancelled approval does NOT save
    def test_cancelled_approval_does_not_save(self):
        initial_count = len(self.store.interactions())
        req = self.sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={"company": "Northwind Logistics", "notes": "Cancelled call"},
        )
        cancelled = self.sec.cancel_approval(approval_id=req["id"])
        self.assertTrue(cancelled)

        commit_res = self.sec.commit_approved_operation(
            approval_id=req["id"],
            memory=self.memory,
        )
        self.assertFalse(commit_res.ok)
        self.assertEqual(len(self.store.interactions()), initial_count)
        self.assertEqual(len(self.memory.retained_interactions), 0)

    # 11. Expired approval does NOT save
    def test_expired_approval_does_not_save(self):
        initial_count = len(self.store.interactions())
        short_sec = SecurityManager(
            self.store,
            outbox_path=self.outbox_path,
            expiry_seconds=1,
            max_attempts=5,
        )
        req = short_sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={"company": "Northwind Logistics", "notes": "Expired call notes"},
        )
        time.sleep(1.1)

        commit_res = short_sec.commit_approved_operation(
            approval_id=req["id"],
            memory=self.memory,
        )
        self.assertFalse(commit_res.ok)
        self.assertEqual(len(self.store.interactions()), initial_count)
        self.assertEqual(len(self.memory.retained_interactions), 0)

    # 12. Failed approval does NOT write to Hindsight
    def test_failed_approval_does_not_write_to_hindsight(self):
        req = self.sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={"company": "Northwind Logistics", "notes": "Failed approval notes"},
        )
        # Lock out via 5 wrong attempts
        for _ in range(5):
            self.sec.verify_user_otp(
                approval_id=req["id"],
                user_name=self.user_a,
                otp="999999",
            )
        session = self.sec.get_session_status(req["id"])
        self.assertEqual(session["status"], "rejected")

        commit_res = self.sec.commit_approved_operation(
            approval_id=req["id"],
            memory=self.memory,
        )
        self.assertFalse(commit_res.ok)
        self.assertEqual(len(self.memory.retained_interactions), 0)

    # 13. Successful approval writes to Hindsight
    def test_successful_approval_writes_to_hindsight(self):
        req = self.sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={
                "company": "Northwind Logistics",
                "notes": "Verified security architecture and compliance requirements",
                "contact": "Raj Malhotra",
                "interaction_type": "Working session",
                "happened": "2026-10-01",
                "result": "advanced",
                "outcome": "InfoSec audit scheduled",
                "tactic": "Provided third-party penetration testing report",
            },
        )
        otps = self._get_delivered_otps()
        self.sec.verify_user_otp(approval_id=req["id"], user_name=self.user_a, otp=otps[self.user_a])
        self.sec.verify_user_otp(approval_id=req["id"], user_name=self.user_b, otp=otps[self.user_b])

        commit_res = self.sec.commit_approved_operation(
            approval_id=req["id"],
            memory=self.memory,
        )
        self.assertTrue(commit_res.ok)
        self.assertEqual(len(self.memory.retained_interactions), 1)
        retained = self.memory.retained_interactions[0]
        self.assertEqual(retained["deal"]["slug"], "northwind-logistics")
        self.assertIn("penetration testing report", retained["row"]["tactic"])

    # 14. Existing Prepare workflow still works
    def test_existing_prepare_workflow_still_works(self):
        deal = self.store.get_deal("northwind-logistics")
        groq = MockGroq()
        brief = run_brief(
            groq_client=groq,
            memory=self.memory,
            store=self.store,
            deal=deal,
            question="Prepare the call for Anil Deshpande",
            use_memory=True,
        )
        self.assertTrue(brief.used_memory)
        self.assertGreater(len(brief.memories), 0)
        self.assertIn("Deal Summary", brief.text)

    # 15. Existing Hindsight recall still works
    def test_existing_hindsight_recall_still_works(self):
        recalled_deal = self.memory.recall_deal("northwind-logistics", "stakeholders")
        recalled_playbook = self.memory.recall_playbook("pricing tactics")
        self.assertEqual(len(recalled_deal), 1)
        self.assertEqual(len(recalled_playbook), 1)
        self.assertIn("Priya Shah", recalled_deal[0]["text"])
        self.assertIn("Meridian Health", recalled_playbook[0]["text"])

    # 16. Existing no-memory comparison still works
    def test_existing_no_memory_comparison_still_works(self):
        deal = self.store.get_deal("northwind-logistics")
        groq = MockGroq()
        brief_generic = run_brief(
            groq_client=groq,
            memory=None,
            store=self.store,
            deal=deal,
            question="Prepare the call for Anil Deshpande",
            use_memory=False,
        )
        self.assertFalse(brief_generic.used_memory)
        self.assertEqual(len(brief_generic.memories), 0)
        self.assertIn("Deal Summary", brief_generic.text)

    # 17. Existing Timeline still works
    def test_existing_timeline_still_works(self):
        interactions = self.store.interactions("northwind-logistics")
        self.assertGreaterEqual(len(interactions), 4)
        commitments = self.store.commitments("northwind-logistics")
        self.assertGreaterEqual(len(commitments), 2)
        # Check overdue function works
        overdue_items = [c for c in commitments if is_overdue(c["due_on"], date(2026, 10, 1))]
        self.assertGreaterEqual(len(overdue_items), 2)

    # Additional Security Tests:
    def test_plaintext_otp_is_never_stored_in_database(self):
        req = self.sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={"company": "Northwind Logistics", "notes": "No plaintext test"},
        )
        otps = self._get_delivered_otps()
        # Query raw SQLite table
        with self.store._conn() as conn:
            row = conn.execute("SELECT * FROM approval_sessions WHERE id = ?", (req["id"],)).fetchone()
            row_dict = dict(row)

        for col, val in row_dict.items():
            if val is not None and isinstance(val, str):
                self.assertNotIn(otps[self.user_a], val, f"Plaintext OTP A found in DB column {col}")
                self.assertNotIn(otps[self.user_b], val, f"Plaintext OTP B found in DB column {col}")

    def test_audit_trail_recorded_without_otps(self):
        req = self.sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={"company": "Northwind Logistics", "notes": "Audit log check"},
        )
        otps = self._get_delivered_otps()
        self.sec.verify_user_otp(approval_id=req["id"], user_name=self.user_a, otp=otps[self.user_a])
        self.sec.verify_user_otp(approval_id=req["id"], user_name=self.user_b, otp=otps[self.user_b])
        self.sec.commit_approved_operation(approval_id=req["id"], memory=self.memory)

        audits = self.store.audit_logs(limit=5)
        self.assertGreater(len(audits), 0)
        latest = audits[0]
        self.assertEqual(latest["approval_id"], req["id"])
        self.assertEqual(latest["status"], "Approved")
        self.assertEqual(latest["requesting_user"], self.user_a)
        self.assertEqual(latest["approving_user"], self.user_b)
        self.assertNotIn(otps[self.user_a], str(latest))
        self.assertNotIn(otps[self.user_b], str(latest))

    def test_app_restart_preserves_session_security(self):
        """Simulate application restart by recreating Store and SecurityManager instances."""
        req = self.sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={"company": "Northwind Logistics", "notes": "Pre-restart notes"},
        )
        otps = self._get_delivered_otps()
        self.sec.verify_user_otp(approval_id=req["id"], user_name=self.user_a, otp=otps[self.user_a])

        # Simulate app restart
        restarted_store = Store(self.db_path)
        restarted_sec = SecurityManager(restarted_store, outbox_path=self.outbox_path)

        session = restarted_sec.get_session_status(req["id"])
        self.assertIsNotNone(session)
        self.assertEqual(session["status"], "partially_verified")
        self.assertTrue(session["user_a_verified"])
        self.assertFalse(session["user_b_verified"])

        # Complete second verification on restarted instance
        res_b = restarted_sec.verify_user_otp(
            approval_id=req["id"],
            user_name=self.user_b,
            otp=otps[self.user_b],
        )
        self.assertTrue(res_b.ok)
        self.assertEqual(res_b.status, "approved")

        commit_res = restarted_sec.commit_approved_operation(
            approval_id=req["id"],
            memory=self.memory,
        )
        self.assertTrue(commit_res.ok)

    def test_test_otp_090904_accepted(self):
        import os
        os.environ["DEALRECALL_TEST_OTP"] = "090904"
        self.assertEqual(generate_otp(), "090904")
        req = self.sec.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_LOG_INTERACTION,
            requesting_user=self.user_a,
            payload={"company": "Northwind Logistics", "notes": "Test OTP 090904 verification"},
        )
        res_a = self.sec.verify_user_otp(approval_id=req["id"], user_name=self.user_a, otp="090904")
        self.assertTrue(res_a.ok)
        self.assertTrue(res_a.first_verified)
        self.assertFalse(res_a.second_verified)

        res_b = self.sec.verify_user_otp(approval_id=req["id"], user_name=self.user_b, otp="090904")
        self.assertTrue(res_b.ok)
        self.assertEqual(res_b.status, "approved")

        commit_res = self.sec.commit_approved_operation(approval_id=req["id"], memory=self.memory)
        self.assertTrue(commit_res.ok)


if __name__ == "__main__":
    unittest.main()

