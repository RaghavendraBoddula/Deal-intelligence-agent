"""Hindsight bank: retain deal facts, recall them, reflect across the playbook."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone

from dealrecall.seed import memory_items
from dealrecall.store import Store

BANK_DEFAULT = "dealrecall"
BASE_URL_DEFAULT = "https://api.hindsight.vectorize.io"

REFLECT_MISSION = (
    "I am the memory of a B2B sales team. I remember stakeholders, objections, "
    "competitors, prices, and promises on each deal, and I remember which tactics "
    "won or lost on other deals. I cite the deal and the person. I do not invent "
    "facts that were never retained. When I recommend a tactic I name the deal "
    "where it worked or failed."
)

RETAIN_MISSION = (
    "Extract stakeholders with their roles, objections, competitor names, prices, "
    "promises with due dates, tactics that were tried, and whether the deal advanced, "
    "was won, or was lost. Keep company and person names exactly as written."
)

DIRECTIVES = [
    (
        "cite-the-deal",
        "Cite the deal and the person a fact came from. If a fact is not in memory, say it is not in memory. Never invent a stakeholder, a price, a competitor, or a promise.",
        10,
    ),
    (
        "prefer-won-tactics",
        "When recommending how to handle an objection, prefer a tactic that won or lost on a past deal over generic sales advice, and name that deal.",
        9,
    ),
]


class Memory:
    def __init__(self, api_key: str, base_url: str, bank_id: str, timeout: float = 600):
        from hindsight_client import Hindsight

        self.bank_id = bank_id
        self.client = Hindsight(base_url=base_url, api_key=api_key, timeout=timeout)

    @classmethod
    def from_env(cls) -> "Memory | None":
        api_key = os.getenv("HINDSIGHT_API_KEY", "").strip()
        if not api_key:
            return None
        return cls(
            api_key=api_key,
            base_url=os.getenv("HINDSIGHT_BASE_URL", BASE_URL_DEFAULT).strip() or BASE_URL_DEFAULT,
            bank_id=os.getenv("HINDSIGHT_BANK_ID", BANK_DEFAULT).strip() or BANK_DEFAULT,
        )

    def ensure_bank(self) -> list[str]:
        warnings: list[str] = []
        self.client.create_bank(
            bank_id=self.bank_id,
            name="DealRecall",
            reflect_mission=REFLECT_MISSION,
            retain_mission=RETAIN_MISSION,
            observations_mission=(
                "Consolidate which objection-handling tactics win or lose, and what "
                "each stakeholder on a deal cares about."
            ),
            enable_observations=True,
        )
        try:
            self.client.update_bank_config(
                self.bank_id,
                disposition_skepticism=2,
                disposition_literalism=4,
                disposition_empathy=3,
            )
        except Exception as exc:
            warnings.append(f"Bank disposition was left at the default ({exc}).")
        warnings.extend(self._ensure_directives())
        return warnings

    def _ensure_directives(self) -> list[str]:
        warnings: list[str] = []
        existing: set[str] = set()
        try:
            listed = self.client.list_directives(bank_id=self.bank_id)
            items = getattr(listed, "items", None) or getattr(listed, "directives", None) or listed
            if isinstance(items, list):
                for item in items:
                    name = item.get("name") if isinstance(item, dict) else getattr(item, "name", None)
                    if name:
                        existing.add(name)
        except Exception as exc:
            warnings.append(f"Could not list directives ({exc}).")
        for name, content, priority in DIRECTIVES:
            if name in existing:
                continue
            try:
                self.client.create_directive(
                    bank_id=self.bank_id,
                    name=name,
                    content=content,
                    priority=priority,
                    is_active=True,
                )
            except Exception as exc:
                warnings.append(f"Directive {name} was not saved ({exc}).")
        return warnings

    def install_sample(self, store: Store) -> int:
        items = memory_items()
        self.client.retain_batch(bank_id=self.bank_id, items=items, retain_async=False)
        store.mark_retained([item["document_id"] for item in items if item["document_id"].startswith("seed-")])
        store.meta_set("hindsight_seeded", "1")
        return len(items)

    def retain_interaction(self, deal: dict, row: dict) -> None:
        entities = [{"text": deal["name"], "type": "ORG"}]
        if row.get("contact"):
            entities.append({"text": row["contact"], "type": "PERSON"})
        self.client.retain(
            bank_id=self.bank_id,
            content=_interaction_text(deal, row),
            context=f"sales interaction on {deal['name']}",
            timestamp=_as_datetime(row["happened_on"]),
            document_id=row["document_id"],
            tags=[f"deal:{deal['slug']}"],
            metadata={
                "deal": deal["name"],
                "deal_slug": deal["slug"],
                "type": row.get("type") or "",
                "result": row.get("result") or "",
            },
            entities=entities,
            resolve_entities=False,
            retain_async=False,
        )
        if row.get("tactic") or row.get("result") in {"won", "lost"}:
            self.client.retain(
                bank_id=self.bank_id,
                content=_lesson_text(deal, row),
                context="sales playbook lesson from a logged outcome",
                timestamp=_as_datetime(row["happened_on"]),
                document_id=f"lesson-{row['document_id']}",
                tags=["playbook"],
                metadata={"kind": "playbook", "deal": deal["name"], "deal_slug": deal["slug"]},
                resolve_entities=False,
                retain_async=False,
            )

def _safe_run_coroutine(coro):
    import asyncio
    import concurrent.futures
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return asyncio.run(coro)
    except Exception:
        return None


    def delete_interaction_memory(self, document_id: str) -> bool:
        """Safely delete interaction document and its lesson from Hindsight bank if supported."""
        deleted = False
        try:
            if hasattr(self.client, "documents") and hasattr(self.client.documents, "delete_document"):
                res = self.client.documents.delete_document(bank_id=self.bank_id, document_id=document_id)
                if inspect.iscoroutine(res):
                    _safe_run_coroutine(res)
                deleted = True
                try:
                    res_l = self.client.documents.delete_document(bank_id=self.bank_id, document_id=f"lesson-{document_id}")
                    if inspect.iscoroutine(res_l):
                        _safe_run_coroutine(res_l)
                except Exception:
                    pass
        except Exception:
            deleted = False
        return deleted

    def update_interaction_memory(self, deal: dict, row: dict) -> bool:
        """Safely update interaction in Hindsight by re-retaining with updated content."""
        try:
            self.delete_interaction_memory(row["document_id"])
            self.retain_interaction(deal, row)
            return True
        except Exception:
            return False

    def sync_pending(self, store: Store) -> int:
        pending = store.pending_retention()
        kept: list[str] = []
        for row in pending:
            deal = store.get_deal(row["deal_slug"])
            if not deal:
                continue
            self.retain_interaction(deal, row)
            kept.append(row["document_id"])
        store.mark_retained(kept)
        return len(kept)

    def recall_deal(self, slug: str, question: str) -> list[dict]:
        deal_name = slug.replace("-", " ")
        with self._request_timeout(45):
            return self._recall(
                f"{deal_name}: {question}",
                tags=[f"deal:{slug}"],
                tags_match="any_strict",
            )

    def recall_playbook(self, question: str) -> list[dict]:
        with self._request_timeout(45):
            return self._recall(
                question,
                tags=["playbook"],
                tags_match="any_strict",
            )

    def reflect(self, deal_name: str, question: str) -> str:
        with self._request_timeout(45):
            answer = self.client.reflect(
                bank_id=self.bank_id,
                query=(
                    f"You are briefing a sales rep before a call on {deal_name}. {question} "
                    "Use this deal's facts and tactics learned from other deals. "
                    "Name the deal each tactic came from."
                ),
                budget="mid",
                context="pre-call briefing",
            )
        return (getattr(answer, "text", None) or "").strip()

    @contextmanager
    def _request_timeout(self, seconds: float):
        """Keep the long seed timeout, but fail a hung recall before the demo stalls."""
        client = self.client
        previous = getattr(client, "_timeout", None)
        if previous is not None:
            client._timeout = seconds
        try:
            yield
        finally:
            if previous is not None:
                client._timeout = previous

    def _recall(self, query: str, *, tags: list[str], tags_match: str) -> list[dict]:
        response = self.client.recall(
            bank_id=self.bank_id,
            query=query,
            budget="mid",
            max_tokens=1600,
            tags=tags,
            tags_match=tags_match,
        )
        memories = []
        for result in response.results or []:
            text = getattr(result, "text", None)
            if not text:
                continue
            metadata = getattr(result, "metadata", None) or {}
            if not isinstance(metadata, dict):
                metadata = {}
            memories.append(
                {
                    "text": text,
                    "type": getattr(result, "type", "") or "",
                    "tags": list(getattr(result, "tags", None) or []),
                    "metadata": {str(key): str(value) for key, value in metadata.items() if value is not None},
                }
            )
        return memories


def _as_datetime(day: str) -> datetime:
    parsed = datetime.fromisoformat(day)
    return parsed.replace(tzinfo=timezone.utc)


def _interaction_text(deal: dict, row: dict) -> str:
    value = deal.get("value_inr") or 0
    value_bit = f" Value discussed: Rs {value // 100000} lakh." if value else ""
    tactic = row.get("tactic") or "None recorded."
    return (
        f"Deal: {deal['name']} ({deal.get('segment') or 'unspecified'}).{value_bit}\n"
        f"Date: {row['happened_on']}. Type: {row.get('type') or 'Note'}.\n"
        f"Contacts: {row.get('contact') or 'not recorded'}.\n"
        f"Notes: {row.get('notes') or ''}\n"
        f"Outcome: {row.get('outcome') or ''}\n"
        f"Tactic tried: {tactic}\n"
        f"Result: {row.get('result') or 'open'}."
    )


def _lesson_text(deal: dict, row: dict) -> str:
    return (
        f"Playbook lesson from {deal['name']} on {row['happened_on']}. "
        f"Result: {row.get('result') or 'open'}. "
        f"Tactic: {row.get('tactic') or 'not recorded'}. "
        f"What happened: {row.get('notes') or ''} "
        f"Outcome: {row.get('outcome') or ''}."
    )
