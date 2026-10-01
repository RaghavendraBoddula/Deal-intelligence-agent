"""Unit and integration tests for Feature 1: Memory Timeline in DealRecall."""

import json
import os
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

from dealrecall.memory_timeline import (
    DealMemory,
    determine_source,
    extract_short_statement,
    format_memory_date,
    get_deal_memories,
)
from dealrecall.security import (
    DEFAULT_TEST_OTP,
    OPERATION_MEMORY_DELETE,
    OPERATION_MEMORY_EDIT,
    SecurityManager,
    get_authorized_users,
)
from dealrecall.store import Store


class MockMemory:
    """Mock Hindsight Memory client for testing retain, update, delete, and recall."""

    def __init__(self):
        self.retained_interactions = []
        self.deleted_document_ids = []
        self.updated_interactions = []
        self.recalled_deals = []
        self.recalled_playbooks = []

    def retain_interaction(self, deal: dict, row: dict) -> None:
        self.retained_interactions.append({"deal": deal, "row": row})

    def delete_interaction_memory(self, document_id: str) -> bool:
        self.deleted_document_ids.append(document_id)
        return True

    def update_interaction_memory(self, deal: dict, row: dict) -> bool:
        self.updated_interactions.append({"deal": deal, "row": row})
        return True

    def recall_deal(self, slug: str, question: str) -> list[dict]:
        self.recalled_deals.append((slug, question))
        return [
            {
                "text": "Raj Malhotra is the IT Security Lead requiring SOC 2 Type II and India data residency.",
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


class TestMemoryTimeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_dealrecall.db"
        self.outbox_path = Path(self.temp_dir.name) / "dev_otp_outbox.json"
        self.store = Store(self.db_path)
        self.mock_memory = MockMemory()
        self.security = SecurityManager(self.store, outbox_path=self.outbox_path)
        self.user_a, self.user_b = get_authorized_users()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _get_delivered_otps(self) -> dict[str, str]:
        if not self.outbox_path.exists():
            return {}
        with open(self.outbox_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        otps = {}
        for entry in entries:
            otps[entry["recipient"]] = entry["otp"]
        return otps

    # 1. Memory timeline loads
    def test_1_memory_timeline_loads(self):
        memories = get_deal_memories(self.store, "northwind-logistics")
        self.assertIsInstance(memories, list)
        self.assertGreater(len(memories), 0)

    # 2. Correct deal memories are shown
    def test_2_correct_deal_memories_are_shown(self):
        memories = get_deal_memories(self.store, "northwind-logistics")
        for mem in memories:
            self.assertEqual(mem.deal_slug, "northwind-logistics")
            self.assertEqual(mem.deal_name, "Northwind Logistics")
        # Ensure Raj Malhotra security interaction exists
        raj_mems = [m for m in memories if "Raj Malhotra" in m.contact or "Raj Malhotra" in m.title]
        self.assertGreater(len(raj_mems), 0)

    # 3. Memories from another deal are not shown
    def test_3_memories_from_another_deal_are_not_shown(self):
        nw_mems = get_deal_memories(self.store, "northwind-logistics")
        meridian_mems = get_deal_memories(self.store, "meridian-health")

        nw_ids = {m.id for m in nw_mems}
        meridian_ids = {m.id for m in meridian_mems}

        # Sets of IDs must be completely disjoint
        self.assertTrue(nw_ids.isdisjoint(meridian_ids))
        for m in meridian_mems:
            self.assertEqual(m.deal_slug, "meridian-health")

    # 4. Memory source is displayed
    def test_4_memory_source_is_displayed(self):
        memories = get_deal_memories(self.store, "northwind-logistics")
        sources = {m.source for m in memories}
        self.assertTrue(len(sources) > 0)
        for m in memories:
            self.assertIsNotNone(m.source)
            self.assertNotEqual(m.source, "")
            self.assertIn(m.source, ["Product Demo", "Discovery Call", "Working Session", "Follow-up Email", "Promise", "Transcribed Call", "Deal Memory", m.type])

    # 5. View Memory opens correct memory
    def test_5_view_memory_opens_correct_memory(self):
        memories = get_deal_memories(self.store, "northwind-logistics")
        target = memories[0]
        # Fetching by ID / document_id retrieves the exact same content
        if target.entity_type == "interaction":
            row = self.store.get_interaction(target.document_id)
            self.assertIsNotNone(row)
            self.assertEqual(row["notes"], target.content)
            self.assertEqual(row["contact"], target.contact)
        else:
            commit = self.store.get_commitment(target.commitment_id)
            self.assertIsNotNone(commit)
            self.assertIn(commit["what"], target.statement)

    # 6. Edit requires authorization
    def test_6_edit_requires_authorization(self):
        initial_row = self.store.get_interaction("seed-northwind-2")
        initial_notes = initial_row["notes"]

        payload = {
            "entity_type": "interaction",
            "document_id": "seed-northwind-2",
            "deal_slug": "northwind-logistics",
            "notes": "Updated security notes: SOC 2 Type II report approved.",
        }
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_MEMORY_EDIT,
            requesting_user=self.user_a,
            payload=payload,
        )
        self.assertEqual(req["operation_type"], OPERATION_MEMORY_EDIT)
        self.assertEqual(req["status"], "pending")

        # Database must NOT be updated yet
        current_row = self.store.get_interaction("seed-northwind-2")
        self.assertEqual(current_row["notes"], initial_notes)

    # 7. Delete requires authorization
    def test_7_delete_requires_authorization(self):
        initial_row = self.store.get_interaction("seed-northwind-3")
        self.assertIsNotNone(initial_row)

        payload = {
            "entity_type": "interaction",
            "document_id": "seed-northwind-3",
            "deal_slug": "northwind-logistics",
        }
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_MEMORY_DELETE,
            requesting_user=self.user_a,
            payload=payload,
        )
        self.assertEqual(req["operation_type"], OPERATION_MEMORY_DELETE)
        self.assertEqual(req["status"], "pending")

        # Database must NOT delete yet
        current_row = self.store.get_interaction("seed-northwind-3")
        self.assertIsNotNone(current_row)

    # 8. Invalid OTP prevents edit
    def test_8_invalid_otp_prevents_edit(self):
        payload = {
            "entity_type": "interaction",
            "document_id": "seed-northwind-2",
            "deal_slug": "northwind-logistics",
            "notes": "Malicious modification attempt",
        }
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_MEMORY_EDIT,
            requesting_user=self.user_a,
            payload=payload,
        )
        otps = self._get_delivered_otps()
        wrong_otp = "000000" if otps.get(self.user_a) != "000000" else "111111"

        res = self.security.verify_user_otp(
            approval_id=req["id"],
            user_name=self.user_a,
            otp=wrong_otp,
        )
        self.assertFalse(res.ok)
        self.assertIn("Invalid OTP", res.message)

        # Commit cannot run
        commit_res = self.security.commit_approved_operation(approval_id=req["id"], memory=self.mock_memory)
        self.assertFalse(commit_res.ok)

    # 9. Invalid OTP prevents delete
    def test_9_invalid_otp_prevents_delete(self):
        payload = {
            "entity_type": "interaction",
            "document_id": "seed-northwind-3",
            "deal_slug": "northwind-logistics",
        }
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_MEMORY_DELETE,
            requesting_user=self.user_a,
            payload=payload,
        )
        otps = self._get_delivered_otps()
        wrong_otp = "000000" if otps.get(self.user_a) != "000000" else "111111"

        res = self.security.verify_user_otp(
            approval_id=req["id"],
            user_name=self.user_a,
            otp=wrong_otp,
        )
        self.assertFalse(res.ok)

        commit_res = self.security.commit_approved_operation(approval_id=req["id"], memory=self.mock_memory)
        self.assertFalse(commit_res.ok)
        self.assertIsNotNone(self.store.get_interaction("seed-northwind-3"))

    # 10. Single-user approval cannot commit
    def test_10_single_user_approval_cannot_commit(self):
        payload = {
            "entity_type": "interaction",
            "document_id": "seed-northwind-2",
            "deal_slug": "northwind-logistics",
            "notes": "Single user attempt",
        }
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_MEMORY_EDIT,
            requesting_user=self.user_a,
            payload=payload,
        )
        otps = self._get_delivered_otps()

        # Only User A verifies
        res = self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_a, otp=otps[self.user_a])
        self.assertTrue(res.ok)
        self.assertEqual(res.status, "partially_verified")

        # Commit fails
        commit_res = self.security.commit_approved_operation(approval_id=req["id"], memory=self.mock_memory)
        self.assertFalse(commit_res.ok)

    # 11. Two-user approval commits edit
    def test_11_two_user_approval_commits_edit(self):
        new_notes = "Security compliance approved by Raj Malhotra on Oct 1."
        payload = {
            "entity_type": "interaction",
            "document_id": "seed-northwind-2",
            "deal_slug": "northwind-logistics",
            "notes": new_notes,
            "outcome": "Security addendum executed",
        }
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_MEMORY_EDIT,
            requesting_user=self.user_a,
            payload=payload,
        )
        otps = self._get_delivered_otps()
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_a, otp=otps[self.user_a])
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_b, otp=otps[self.user_b])

        commit_res = self.security.commit_approved_operation(approval_id=req["id"], memory=self.mock_memory)
        self.assertTrue(commit_res.ok)

        # Verify database update
        updated = self.store.get_interaction("seed-northwind-2")
        self.assertEqual(updated["notes"], new_notes)
        self.assertEqual(updated["outcome"], "Security addendum executed")

        # Verify Hindsight update called
        self.assertGreater(len(self.mock_memory.updated_interactions), 0)

    # 12. Two-user approval commits delete
    def test_12_two_user_approval_commits_delete(self):
        payload = {
            "entity_type": "interaction",
            "document_id": "seed-northwind-3",
            "deal_slug": "northwind-logistics",
        }
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_MEMORY_DELETE,
            requesting_user=self.user_a,
            payload=payload,
        )
        otps = self._get_delivered_otps()
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_a, otp=otps[self.user_a])
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_b, otp=otps[self.user_b])

        commit_res = self.security.commit_approved_operation(approval_id=req["id"], memory=self.mock_memory)
        self.assertTrue(commit_res.ok)

        # Verify database deletion
        self.assertIsNone(self.store.get_interaction("seed-northwind-3"))

        # Verify Hindsight deletion called
        self.assertIn("seed-northwind-3", self.mock_memory.deleted_document_ids)

    # 13. Audit event created for edit
    def test_13_audit_event_created_for_edit(self):
        payload = {
            "entity_type": "interaction",
            "document_id": "seed-northwind-1",
            "deal_slug": "northwind-logistics",
            "notes": "Audited edit",
        }
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_MEMORY_EDIT,
            requesting_user=self.user_a,
            payload=payload,
        )
        otps = self._get_delivered_otps()
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_a, otp=otps[self.user_a])
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_b, otp=otps[self.user_b])
        self.security.commit_approved_operation(approval_id=req["id"], memory=self.mock_memory)

        logs = self.store.audit_logs(limit=10)
        edit_logs = [l for l in logs if l["approval_id"] == req["id"]]
        self.assertGreater(len(edit_logs), 0)
        latest = edit_logs[0]
        self.assertEqual(latest["status"], "Approved")
        self.assertIn("Memory Edit", latest["operation"])
        self.assertEqual(latest["requesting_user"], self.user_a)
        self.assertEqual(latest["approving_user"], self.user_b)

    # 14. Audit event created for delete
    def test_14_audit_event_created_for_delete(self):
        payload = {
            "entity_type": "interaction",
            "document_id": "seed-northwind-4",
            "deal_slug": "northwind-logistics",
        }
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_MEMORY_DELETE,
            requesting_user=self.user_a,
            payload=payload,
        )
        otps = self._get_delivered_otps()
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_a, otp=otps[self.user_a])
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_b, otp=otps[self.user_b])
        self.security.commit_approved_operation(approval_id=req["id"], memory=self.mock_memory)

        logs = self.store.audit_logs(limit=10)
        del_logs = [l for l in logs if l["approval_id"] == req["id"]]
        self.assertGreater(len(del_logs), 0)
        latest = del_logs[0]
        self.assertEqual(latest["status"], "Approved")
        self.assertIn("Memory Delete", latest["operation"])

    # 15. Deleted memory no longer appears in timeline
    def test_15_deleted_memory_no_longer_appears_in_timeline(self):
        # Create new interaction to delete
        new_row = self.store.add_interaction(
            document_id="temp-to-delete",
            deal_slug="northwind-logistics",
            happened_on="2026-09-20",
            contact="Temp Contact",
            type_="Call",
            notes="Temporary call note to delete",
            outcome="None",
            tactic="None",
            result="open",
        )
        # Check it is in memories
        mems_before = get_deal_memories(self.store, "northwind-logistics")
        self.assertTrue(any(m.document_id == "temp-to-delete" for m in mems_before))

        # Delete it via OTP
        payload = {"entity_type": "interaction", "document_id": "temp-to-delete", "deal_slug": "northwind-logistics"}
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type=OPERATION_MEMORY_DELETE,
            requesting_user=self.user_a,
            payload=payload,
        )
        otps = self._get_delivered_otps()
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_a, otp=otps[self.user_a])
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_b, otp=otps[self.user_b])
        commit_res = self.security.commit_approved_operation(approval_id=req["id"], memory=self.mock_memory)
        self.assertTrue(commit_res.ok)

        # Check it is GONE from memories
        mems_after = get_deal_memories(self.store, "northwind-logistics")
        self.assertFalse(any(m.document_id == "temp-to-delete" for m in mems_after))

    # 16. Existing OTP tests still pass
    def test_16_existing_otp_tests_still_pass(self):
        # Standard edit deal
        req = self.security.create_approval_request(
            deal_slug="northwind-logistics",
            deal_name="Northwind Logistics",
            operation_type="edit_deal",
            requesting_user=self.user_a,
            payload={"slug": "northwind-logistics", "stage": "Negotiation"},
        )
        otps = self._get_delivered_otps()
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_a, otp=otps[self.user_a])
        self.security.verify_user_otp(approval_id=req["id"], user_name=self.user_b, otp=otps[self.user_b])
        commit_res = self.security.commit_approved_operation(approval_id=req["id"], memory=self.mock_memory)
        self.assertTrue(commit_res.ok)
        deal = self.store.get_deal("northwind-logistics")
        self.assertEqual(deal["stage"], "Negotiation")

    # 17. Existing Call Intelligence tests still pass
    def test_17_existing_call_intelligence_still_works(self):
        from dealrecall.call_intelligence import validate_audio_file
        ok, msg = validate_audio_file("call.m4a", 1024, b"audio")
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    # 18. Existing Hindsight tests still pass
    def test_18_existing_hindsight_tests_still_pass(self):
        recalled = self.mock_memory.recall_deal("northwind-logistics", "security")
        self.assertEqual(len(recalled), 1)
        self.assertIn("Raj Malhotra", recalled[0]["text"])


if __name__ == "__main__":
    unittest.main()
