import tempfile
import unittest
from datetime import date
from pathlib import Path

from dealrecall.agent import (
    BriefError,
    dispatch_tool,
    friendly_service_error,
    parse_sections,
    parse_tool_arguments,
    run_brief,
    strip_think,
)
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
        security = next(item for item in playbook if item["document_id"] == "seed-playbook-security")
        self.assertEqual(security["metadata"]["deal"], "Meridian Health")
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


class BriefFlowTests(unittest.TestCase):
    SAMPLE = (
        "1. Deal Summary\nWaiting on security.\n"
        "2. Stakeholders\nPriya Shah is the champion.\n"
        "3. Objections\nSecurity and price.\n"
        "4. Competitor\nCargoFlow is cheaper.\n"
        "5. Open Promises\nSecurity brief for Raj.\n"
        "6. Recommended Questions\n- What does Anil need?\n- Has Raj read the note?\n- Is the case study enough?\n"
    )

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.dir.name) / "deals.db")
        self.deal = self.store.get_deal("northwind-logistics")
        self.memory = ScriptedMemory(
            [
                {
                    "text": "Raj Malhotra is waiting on a security brief.",
                    "type": "world",
                    "tags": ["deal:northwind-logistics"],
                    "metadata": {"deal": "Northwind Logistics"},
                }
            ],
            [
                {
                    "text": "Meridian Health refused a discount and won at list price.",
                    "type": "experience",
                    "tags": ["playbook"],
                    "metadata": {},
                }
            ],
        )
        self.groq = ScriptedGroq(self.SAMPLE)

    def tearDown(self):
        self.dir.cleanup()

    def test_memory_brief_recalls_then_generates(self):
        labels = []
        brief = run_brief(
            groq_client=self.groq,
            memory=self.memory,
            store=self.store,
            deal=self.deal,
            question="How should I prepare for the 30 September call?",
            use_memory=True,
            on_progress=labels.append,
        )
        self.assertEqual(self.memory.deal_calls, 1)
        self.assertEqual(self.memory.play_calls, 1)
        self.assertEqual(len(self.groq.calls), 1)
        self.assertNotIn("tools", self.groq.calls[0])
        sent = self.groq.calls[0]["messages"][1]["content"]
        self.assertIn("Raj Malhotra is waiting on a security brief.", sent)
        self.assertIn("Meridian Health refused a discount", sent)
        self.assertEqual(brief.memories[0]["source"], "Northwind Logistics")
        self.assertEqual(brief.memories[0]["relevance"], "High")
        self.assertEqual(brief.memories[1]["source"], "Cross-deal playbook")
        self.assertIn("Hindsight memory recalled", [step["label"] for step in brief.trace])
        self.assertIn("Recalling deal history…", labels)
        self.assertIn("Building your pre-call brief…", labels)
        self.assertIn("Priya Shah", brief.text)

    def test_same_flow_twice(self):
        for _ in range(2):
            brief = run_brief(
                groq_client=self.groq,
                memory=self.memory,
                store=self.store,
                deal=self.deal,
                question="Prepare the call",
                use_memory=True,
            )
            self.assertTrue(brief.used_memory)
            self.assertGreaterEqual(len(brief.memories), 2)

    def test_no_memory_brief_does_not_receive_history(self):
        brief = run_brief(
            groq_client=self.groq,
            memory=self.memory,
            store=self.store,
            deal=self.deal,
            question="Prepare the call",
            use_memory=False,
        )
        self.assertEqual(self.memory.deal_calls, 0)
        blob = " ".join(message["content"] for message in self.groq.calls[0]["messages"])
        self.assertNotIn("Raj Malhotra is waiting", blob)
        self.assertNotIn("Meridian Health refused", blob)
        self.assertIn("Northwind Logistics", blob)
        self.assertFalse(brief.used_memory)

    def test_hindsight_timeout_does_not_call_groq(self):
        self.memory.boom = True
        with self.assertRaises(BriefError) as caught:
            run_brief(
                groq_client=self.groq,
                memory=self.memory,
                store=self.store,
                deal=self.deal,
                question="Prepare the call",
                use_memory=True,
            )
        self.assertIn("did not respond in time", caught.exception.message)
        self.assertNotIn("Traceback", caught.exception.message)
        self.assertEqual(self.groq.calls, [])

    def test_empty_hindsight_does_not_invent_a_brief(self):
        self.memory.deal_items = []
        self.memory.play_items = []
        with self.assertRaises(BriefError) as caught:
            run_brief(
                groq_client=self.groq,
                memory=self.memory,
                store=self.store,
                deal=self.deal,
                question="Prepare the call",
                use_memory=True,
            )
        self.assertIn("no memories", caught.exception.message)
        self.assertEqual(self.groq.calls, [])

    def test_empty_groq_response(self):
        self.groq.content = "   "
        with self.assertRaises(BriefError) as caught:
            run_brief(
                groq_client=self.groq,
                memory=self.memory,
                store=self.store,
                deal=self.deal,
                question="Prepare the call",
                use_memory=True,
            )
        self.assertIn("empty brief", caught.exception.message)

    def test_friendly_errors_hide_traces(self):
        self.assertIn("key was rejected", friendly_service_error(RuntimeError("401 unauthorized"), "Hindsight"))
        message = friendly_service_error(ConnectionError("failed to establish a connection"), "Hindsight")
        self.assertIn("Hindsight is unavailable right now", message)
        self.assertNotIn("Traceback", friendly_service_error(RuntimeError('Traceback (most recent call last):\n  File "x.py"'), "Groq"))


class ScriptedMemory:
    def __init__(self, deal_items, play_items):
        self.deal_items = deal_items
        self.play_items = play_items
        self.deal_calls = 0
        self.play_calls = 0
        self.boom = False

    def recall_deal(self, slug, question):
        self.deal_calls += 1
        if self.boom:
            raise TimeoutError("request timed out")
        return list(self.deal_items)

    def recall_playbook(self, question):
        self.play_calls += 1
        return list(self.play_items)


class ScriptedGroq:
    def __init__(self, content):
        self.content = content
        self.calls = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = type("Message", (), {"content": self.content})()
        choice = type("Choice", (), {"message": message})()
        return type("Response", (), {"choices": [choice]})()


if __name__ == "__main__":
    unittest.main()
