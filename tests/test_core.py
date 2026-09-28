import tempfile
import unittest
from datetime import date
from pathlib import Path

from dealrecall.agent import dispatch_tool, parse_sections, parse_tool_arguments, strip_think
from dealrecall.seed import memory_items
from dealrecall.store import Store, format_inr, is_overdue, slugify


class ParseTests(unittest.TestCase):
    def test_strip_think_blocks(self):
        text = "<think>secret planning</think>\n1. Deal Summary\nReal brief"
        self.assertNotIn("secret", strip_think(text))
        self.assertIn("Deal Summary", strip_think(text))

    def test_parse_sections_requires_three(self):
        self.assertEqual(parse_sections("1. Only one\nHello"), [])

    def test_parse_sections_splits_bodies(self):
        text = "1. Deal Summary\nStatus is late.\n2. Key Stakeholders\nPriya.\n3. Objection Handling\nPrice."
        sections = parse_sections(text)
        self.assertEqual([number for number, _, _ in sections], [1, 2, 3])
        self.assertIn("Priya", sections[1][2])
        self.assertNotIn("Price", sections[1][2])

    def test_bad_tool_arguments_are_returned_not_raised(self):
        args, error = parse_tool_arguments("{not json")
        self.assertIsNone(args)
        self.assertIn("JSON", error)

    def test_tool_arguments_must_be_an_object(self):
        args, error = parse_tool_arguments("[1, 2]")
        self.assertIsNone(args)
        self.assertIn("object", error)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.dir.name) / "deals.db")

    def tearDown(self):
        self.dir.cleanup()

    def test_sample_pipeline_loads_once(self):
        self.assertEqual(len(self.store.deals()), 4)
        self.assertEqual(len(self.store.interactions()), 13)
        self.assertEqual(len(self.store.pending_retention()), 13)
        again = Store(Path(self.dir.name) / "deals.db")
        self.assertEqual(len(again.interactions()), 13)

    def test_deal_lookup_is_exact(self):
        self.assertIsNone(self.store.get_deal_by_name("Retail"))
        self.assertIsNone(self.store.get_deal_by_name("IT"))
        self.assertEqual(self.store.get_deal_by_name("Kaveri Retail")["slug"], "kaveri-retail")
        self.assertEqual(self.store.get_deal_by_name("  kaveri retail ")["slug"], "kaveri-retail")

    def test_overdue_promises_on_northwind(self):
        open_items = self.store.commitments("northwind-logistics", status="open")
        overdue = [item for item in open_items if is_overdue(item["due_on"], date(2026, 9, 28))]
        self.assertEqual(len(overdue), 2)

    def test_new_deal_does_not_collide_on_substring(self):
        created = self.store.ensure_deal("Northwind")
        self.assertNotEqual(created["slug"], "northwind-logistics")
        self.assertEqual(self.store.ensure_deal("Northwind")["slug"], created["slug"])


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.dir.name) / "deals.db")
        self.memory = FakeMemory()

    def tearDown(self):
        self.dir.cleanup()

    def test_unknown_slug_lists_valid_deals(self):
        payload, memories = dispatch_tool(
            "recall_deal",
            {"deal_slug": "retail", "question": "pricing"},
            memory=self.memory,
            store=self.store,
        )
        self.assertFalse(payload["ok"])
        self.assertIn("northwind-logistics", payload["valid_slugs"])
        self.assertEqual(memories, [])
        self.assertEqual(self.memory.deal_calls, 0)

    def test_unknown_tool_is_an_error_payload(self):
        payload, _ = dispatch_tool("delete_crm", {}, memory=self.memory, store=self.store)
        self.assertFalse(payload["ok"])
        self.assertIn("Unknown tool", payload["error"])

    def test_recall_deal_uses_the_exact_slug(self):
        payload, memories = dispatch_tool(
            "recall_deal",
            {"deal_slug": "northwind-logistics", "question": "what is overdue"},
            memory=self.memory,
            store=self.store,
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(memories[0]["text"], "Priya is waiting on a case study")
        self.assertEqual(self.memory.last_slug, "northwind-logistics")

    def test_open_promises_include_overdue_flag(self):
        payload, _ = dispatch_tool(
            "list_open_promises",
            {"deal_slug": "northwind-logistics"},
            memory=self.memory,
            store=self.store,
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["promises"]), 2)
        for item in payload["promises"]:
            self.assertEqual(item["overdue"], is_overdue(item["due_on"]))


class SeedTests(unittest.TestCase):
    def test_memory_items_are_scoped(self):
        items = memory_items()
        deal_items = [item for item in items if item["tags"] == ["deal:northwind-logistics"]]
        playbook = [item for item in items if item["tags"] == ["playbook"]]
        self.assertEqual(len(deal_items), 5)
        self.assertEqual(len(playbook), 4)
        self.assertTrue(all(item["document_id"] for item in items))

    def test_slug_and_money(self):
        self.assertEqual(slugify("  Northwind Logistics "), "northwind-logistics")
        self.assertEqual(format_inr(1_800_000), "Rs 18L")


class FakeMemory:
    def __init__(self):
        self.deal_calls = 0
        self.last_slug = None

    def recall_deal(self, slug, question):
        self.deal_calls += 1
        self.last_slug = slug
        return [{"text": "Priya is waiting on a case study", "type": "world", "tags": [f"deal:{slug}"]}]

    def recall_playbook(self, question):
        return [{"text": "Meridian refused the discount", "type": "experience", "tags": ["playbook"]}]


if __name__ == "__main__":
    unittest.main()
