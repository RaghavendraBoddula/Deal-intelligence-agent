"""Unit and integration tests for Feature 2: ⚡ What Changed?

Verifies deterministic change detection, previous/current time window identification,
stakeholder/security/objection/commitment change classifications, source traceability,
empty states, Hindsight fallback, and LLM resilience.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from dealrecall.memory import Memory
from dealrecall.memory_timeline import get_deal_memories
from dealrecall.store import Store
from dealrecall.what_changed import (
    ChangeItem,
    WhatChangedResult,
    compare_interaction_states,
    extract_interaction_state,
    format_short_date,
    get_change_badge,
    get_what_changed,
)


class TestWhatChanged(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tmpdir.name) / "test_what_changed.db"
        self.store = Store(db_path)

        # Setup custom test deal with exact 2-step history
        deal = self.store.ensure_deal("Apex Freight")
        self.slug = deal["slug"]

        # Step 1: Initial Discovery Call (2026-08-12)
        self.store.add_interaction(
            document_id="apex-doc-1",
            deal_slug=self.slug,
            happened_on="2026-08-12",
            contact="Priya Shah (VP Operations)",
            type_="Discovery call",
            notes="Northwind runs four warehouses in Pune and Nagpur. Budget authority up to Rs 20 lakh. Worried onboarding will take floor leads off the dock for a month.",
            outcome="Demo booked for 21 August with operations and IT security.",
            tactic="",
            result="advanced",
        )

        # Step 2: Product Demo introducing Raj Malhotra, SOC 2, CargoFlow, and promises (2026-08-21)
        self.store.add_interaction(
            document_id="apex-doc-2",
            deal_slug=self.slug,
            happened_on="2026-08-21",
            contact="Priya Shah (VP Operations) and Raj Malhotra (IT Security Lead)",
            type_="Product demo",
            notes="Priya liked workflow. Raj Malhotra asked for SSO with Okta, SOC 2 Type II, and data residency in India. CargoFlow is in PoC and is 30 percent cheaper.",
            outcome="Promised Priya a 3PL case study and Raj a security packet.",
            tactic="Showed product workflow.",
            result="advanced",
        )

        self.store.add_commitment(self.slug, "Send 3PL case study", "Priya Shah", "2026-09-04")
        self.store.add_commitment(self.slug, "Send security packet", "Raj Malhotra", "2026-09-04")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_what_changed_loads_for_deal(self):
        """1. What Changed loads successfully for seeded Northwind Logistics."""
        res = get_what_changed(self.store, "northwind-logistics")
        self.assertIsInstance(res, WhatChangedResult)
        self.assertTrue(res.has_history)
        self.assertFalse(res.single_interaction)
        self.assertGreater(len(res.changes), 0)
        self.assertIn("Since your last interaction", res.time_label)

    def test_previous_interaction_identified_correctly(self):
        """2. Previous interaction is identified as the predecessor interaction date."""
        res = get_what_changed(self.store, self.slug)
        self.assertEqual(res.previous_date, "2026-08-12")
        self.assertEqual(res.previous_formatted_date, "Aug 12")

    def test_current_interaction_identified_correctly(self):
        """3. Current interaction is identified as the latest interaction date."""
        res = get_what_changed(self.store, self.slug)
        self.assertEqual(res.current_date, "2026-08-21")
        self.assertEqual(res.current_formatted_date, "Aug 21")

    def test_new_stakeholder_detected(self):
        """4. New stakeholder introduced in current interaction is detected as NEW."""
        res = get_what_changed(self.store, self.slug)
        stakeholder_changes = [
            ch for ch in res.changes if ch.type == "NEW" and "stakeholder" in ch.title.lower()
        ]
        self.assertGreater(len(stakeholder_changes), 0)
        self.assertTrue(any("Raj Malhotra" in ch.description for ch in stakeholder_changes))

    def test_new_objection_detected(self):
        """5. New competitor / objection in current interaction is detected."""
        res = get_what_changed(self.store, self.slug)
        obj_changes = [
            ch for ch in res.changes if "objection" in ch.title.lower() or "competitor" in ch.title.lower()
        ]
        self.assertGreater(len(obj_changes), 0)
        self.assertTrue(any("CargoFlow" in ch.description for ch in obj_changes))

    def test_new_security_requirement_detected(self):
        """6. New security / compliance requirement is detected as NEW."""
        res = get_what_changed(self.store, self.slug)
        sec_changes = [
            ch for ch in res.changes if ch.type == "NEW" and "security" in ch.title.lower()
        ]
        self.assertGreater(len(sec_changes), 0)
        self.assertTrue(any("SOC 2" in ch.description or "Okta" in ch.description for ch in sec_changes))

    def test_new_commitment_detected(self):
        """7. New commitment promised in current interaction is detected."""
        res = get_what_changed(self.store, self.slug)
        comm_changes = [
            ch for ch in res.changes if ch.type == "NEW COMMITMENT"
        ]
        self.assertGreater(len(comm_changes), 0)
        self.assertTrue(any("case study" in ch.description.lower() or "security packet" in ch.description.lower() for ch in comm_changes))

    def test_resolved_item_detected(self):
        """8. Resolved item or fulfilled commitment is detected as RESOLVED."""
        # Add interaction 3 where CargoFlow workflow is rejected as generic
        self.store.add_interaction(
            document_id="apex-doc-3",
            deal_slug=self.slug,
            happened_on="2026-09-02",
            contact="Priya Shah (VP Operations)",
            type_="Working session",
            notes="CargoFlow warehouse workflow felt generic and would not fit dock needs.",
            outcome="Proceed with our workflow.",
            tactic="",
            result="advanced",
        )
        res = get_what_changed(self.store, self.slug)
        resolved_changes = [ch for ch in res.changes if ch.type == "RESOLVED"]
        self.assertGreater(len(resolved_changes), 0)

    def test_still_open_item_detected(self):
        """9. Outstanding security requirements or commitments are detected as STILL OPEN."""
        # Add interaction 3 where security packet remains overdue
        self.store.add_interaction(
            document_id="apex-doc-3",
            deal_slug=self.slug,
            happened_on="2026-09-02",
            contact="Priya Shah (VP Operations)",
            type_="Follow-up email",
            notes="Raj is silent. The security packet promised on 21 August is still not sent and remains overdue.",
            outcome="Waiting on security note.",
            tactic="",
            result="open",
        )
        res = get_what_changed(self.store, self.slug)
        open_changes = [ch for ch in res.changes if ch.type == "STILL OPEN"]
        self.assertGreater(len(open_changes), 0)

    def test_unchanged_item_not_shown_as_changed(self):
        """10. Unchanged item (e.g. Priya Shah being champion in both) is not shown as NEW."""
        res = get_what_changed(self.store, self.slug)
        priya_new = [
            ch for ch in res.changes if ch.type == "NEW" and "Priya Shah" in ch.description and "stakeholder" in ch.title.lower()
        ]
        # Priya was in interaction 1, so she cannot be a "NEW stakeholder" in interaction 2
        self.assertEqual(len(priya_new), 0)

    def test_another_deal_memory_does_not_leak(self):
        """11. Another deal's interactions do not leak into this deal's comparison."""
        res_nw = get_what_changed(self.store, "northwind-logistics")
        # Saffron Hotels / Kaveri Retail facts must not appear in Northwind
        for ch in res_nw.changes:
            self.assertNotIn("Vikram", ch.description)
            self.assertNotIn("banquet", ch.description.lower())
            self.assertNotIn("Kaveri", ch.description)

    def test_dates_taken_from_actual_data(self):
        """12. Dates are strictly derived from actual database records."""
        res = get_what_changed(self.store, self.slug)
        self.assertEqual(res.previous_date, "2026-08-12")
        self.assertEqual(res.current_date, "2026-08-21")
        for ch in res.changes:
            self.assertIn(ch.date, ("2026-08-12", "2026-08-21"))

    def test_source_traceability_preserved(self):
        """13. Every detected change preserves accurate source and document ID."""
        res = get_what_changed(self.store, self.slug)
        for ch in res.changes:
            self.assertIn(ch.source, ("Product demo", "Discovery call", "Interaction"))
            self.assertIsNotNone(ch.memory_id)
            self.assertTrue("apex-doc" in ch.memory_id or "commitment" in ch.memory_id)

    def test_view_memory_links_to_existing_memory_details(self):
        """14. Change memory_id matches a real deal memory from Feature 1."""
        res = get_what_changed(self.store, self.slug)
        deal_memories = get_deal_memories(self.store, self.slug)
        deal_mem_ids = {m.id for m in deal_memories}

        for ch in res.changes:
            if ch.memory_id and not ch.memory_id.startswith("commitment-"):
                self.assertIn(ch.memory_id, deal_mem_ids)

    def test_single_interaction_deal_shows_correct_empty_state(self):
        """15. Deal with only 1 interaction displays clear single-interaction empty state."""
        self.store.ensure_deal("Solo Tech")
        self.store.add_interaction(
            document_id="solo-1",
            deal_slug="solo-tech",
            happened_on="2026-09-01",
            contact="Mark Vance",
            type_="Discovery call",
            notes="First intro call with Mark Vance.",
            outcome="Send deck.",
            tactic="",
            result="open",
        )
        res = get_what_changed(self.store, "solo-tech")
        self.assertFalse(res.has_history)
        self.assertTrue(res.single_interaction)
        self.assertIn("Only one interaction recorded", res.time_label)
        self.assertIn("Start another interaction", res.message)
        self.assertEqual(len(res.changes), 0)

    def test_no_change_scenario_shows_correct_empty_state(self):
        """16. Two identical interactions with no difference show no-change empty state."""
        self.store.ensure_deal("Identical Corp")
        self.store.add_interaction(
            document_id="id-1",
            deal_slug="identical-corp",
            happened_on="2026-09-01",
            contact="Alice Green",
            type_="Follow-up email",
            notes="Checked in on contract review.",
            outcome="Review in progress.",
            tactic="",
            result="open",
        )
        self.store.add_interaction(
            document_id="id-2",
            deal_slug="identical-corp",
            happened_on="2026-09-05",
            contact="Alice Green",
            type_="Follow-up email",
            notes="Checked in on contract review.",
            outcome="Review in progress.",
            tactic="",
            result="open",
        )
        res = get_what_changed(self.store, "identical-corp")
        self.assertTrue(res.has_history)
        self.assertEqual(len(res.changes), 0)
        self.assertIn("No meaningful changes", res.message)

    def test_hindsight_unavailable_fallback_works(self):
        """17. If Hindsight is None or throws, fallback to local store comparison works cleanly."""
        res = get_what_changed(self.store, "northwind-logistics", memory=None)
        self.assertTrue(res.has_history)
        self.assertFalse(res.hindsight_used)
        self.assertGreater(len(res.changes), 0)

        # Also test mock memory that raises an error
        failing_memory = MagicMock()
        failing_memory.recall_deal.side_effect = Exception("Hindsight network timeout")
        res_fallback = get_what_changed(self.store, "northwind-logistics", memory=failing_memory)
        self.assertTrue(res_fallback.has_history)
        self.assertFalse(res_fallback.hindsight_used)
        self.assertGreater(len(res_fallback.changes), 0)

    def test_llm_failure_does_not_break_deterministic_changes(self):
        """18. If Groq client fails or raises, deterministic changes are preserved."""
        failing_groq = MagicMock()
        failing_groq.chat.completions.create.side_effect = Exception("Groq rate limit 429")

        res = get_what_changed(self.store, "northwind-logistics", groq_client=failing_groq)
        self.assertTrue(res.has_history)
        self.assertFalse(res.ai_polished)
        self.assertGreater(len(res.changes), 0)  # Deterministic changes still returned intact


if __name__ == "__main__":
    unittest.main()
