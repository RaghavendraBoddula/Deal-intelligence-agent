"""Memory Timeline data model and helper functions for DealRecall.

Extracts, categorizes, formats, and filters deal memories from DealRecall's local
CRM ledger and Hindsight memory bank for the interactive Memory Timeline.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

from dealrecall.store import Store


MEMORY_CATEGORIES = (
    "All",
    "Calls",
    "Promises",
    "Security",
    "Objections",
    "Stakeholders",
    "Pricing",
    "Requirements",
)


@dataclass
class DealMemory:
    id: str
    entity_type: str  # "interaction" or "commitment"
    date: str  # ISO date string e.g. "2026-08-21"
    formatted_date: str  # e.g. "Aug 21, 2026"
    title: str  # e.g. "CALL · Raj Malhotra"
    category: str  # primary category: "Call", "Promise", "Security", etc.
    categories: list[str]  # all matching categories for filtering
    statement: str  # short summary statement
    content: str  # full memory content / notes
    contact: str  # contact person or role
    source: str  # e.g. "Transcribed Call", "Commercial Call", "Product Demo", "Promise", "Deal Memory"
    type: str  # original interaction type e.g. "Product demo" or "Promise"
    deal_slug: str
    deal_name: str
    storage: str  # "Hindsight + Local Store", "Local Store", or "Hindsight"
    retained_in_hindsight: bool = False
    document_id: str | None = None
    commitment_id: int | None = None
    outcome: str = ""
    tactic: str = ""
    result: str = ""
    status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def format_memory_date(iso_date: str) -> str:
    """Format ISO date string (YYYY-MM-DD) into readable format like 'Aug 21, 2026'."""
    if not iso_date:
        return ""
    try:
        dt = date.fromisoformat(iso_date[:10])
        return dt.strftime("%b %d, %Y")
    except Exception:
        return iso_date


def detect_categories(text: str, interaction_type: str = "", entity_type: str = "interaction") -> list[str]:
    """Detect matching categories from memory content and type."""
    cats = {"All"}
    low_text = (text or "").lower()
    low_type = (interaction_type or "").lower()

    if entity_type == "commitment" or "promise" in low_text or "promise" in low_type:
        cats.add("Promises")

    if any(k in low_type for k in ("call", "demo", "session", "meeting", "email")) or any(
        k in low_text for k in ("call", "demo", "meeting", "spoke with", "discussed")
    ):
        cats.add("Calls")

    if any(
        k in low_text
        for k in (
            "security",
            "compliance",
            "soc 2",
            "iso",
            "residency",
            "encryption",
            "infosec",
            "okta",
            "sso",
            "penetration test",
        )
    ):
        cats.add("Security")

    if any(
        k in low_text
        for k in (
            "objection",
            "competitor",
            "cargoflow",
            "cheaper",
            "discount",
            "pushback",
            "blocker",
            "concern",
            "worried",
        )
    ):
        cats.add("Objections")

    if any(
        k in low_text
        for k in (
            "raj malhotra",
            "priya shah",
            "anil deshpande",
            "cfo",
            "vp operations",
            "security lead",
            "champion",
            "stakeholder",
        )
    ):
        cats.add("Stakeholders")

    if any(
        k in low_text
        for k in ("price", "pricing", "discount", "lakh", "commercial", "budget", "quote", "cost", "prepay")
    ):
        cats.add("Pricing")

    if any(
        k in low_text
        for k in (
            "requirement",
            "pilot",
            "onboarding",
            "3pl",
            "case study",
            "addendum",
            "specification",
            "sla",
        )
    ):
        cats.add("Requirements")

    return sorted(cats)


def determine_source(item_type: str, document_id: str = "", tactic: str = "", entity_type: str = "interaction") -> str:
    """Determine the accurate source of a memory without inventing one."""
    if entity_type == "commitment":
        return "Promise"

    doc_low = (document_id or "").lower()
    type_low = (item_type or "").lower()
    tactic_low = (tactic or "").lower()

    if doc_low.startswith("call-") or "transcribed" in type_low or "transcribed" in tactic_low:
        return "Transcribed Call"
    if "commercial" in type_low:
        return "Commercial Call"
    if "discovery" in type_low:
        return "Discovery Call"
    if "product demo" in type_low:
        return "Product Demo"
    if "working session" in type_low:
        return "Working Session"
    if "email" in type_low:
        return "Follow-up Email"
    if "call" in type_low:
        return "Call"
    if item_type and item_type.strip():
        return item_type.strip()
    return "Deal Memory"


def extract_short_statement(notes: str, outcome: str = "", max_chars: int = 150) -> str:
    """Extract a concise memory statement for display on timeline cards."""
    clean_notes = (notes or "").strip()
    if not clean_notes and outcome:
        return outcome.strip()

    # If notes start with rich labels from Feature 2 (Security & Compliance: ...)
    for prefix in (
        "Security & Compliance:",
        "Security / compliance requirement:",
        "Objections:",
        "Requirements:",
        "Pricing:",
    ):
        if prefix.lower() in clean_notes.lower():
            idx = clean_notes.lower().find(prefix.lower())
            sub = clean_notes[idx:]
            first_line = sub.split("\n\n")[0].replace("\n", " ").strip()
            if len(first_line) <= max_chars:
                return first_line
            return first_line[: max_chars - 3].rstrip() + "..."

    # Use first sentence or first line
    sentences = re.split(r"(?<=[.!?])\s+", clean_notes)
    first_sentence = sentences[0].replace("\n", " ").strip() if sentences else clean_notes
    if len(first_sentence) <= max_chars:
        return first_sentence
    return first_sentence[: max_chars - 3].rstrip() + "..."


def get_deal_memories(
    store: Store,
    deal_slug: str,
    search_query: str = "",
    category_filter: str = "All",
) -> list[DealMemory]:
    """Retrieve all memories for the specified deal, applying search query and category filters."""
    deal = store.get_deal(deal_slug)
    deal_name = deal["name"] if deal else deal_slug.replace("-", " ").title()

    memories: list[DealMemory] = []

    # 1. Load CRM Interactions (Touchpoints & Calls)
    interactions = store.interactions(deal_slug)
    for row in interactions:
        doc_id = row.get("document_id") or f"row-{row['id']}"
        notes = row.get("notes") or ""
        outcome = row.get("outcome") or ""
        contact = row.get("contact") or "Not recorded"
        itype = row.get("type") or "Touchpoint"
        source = determine_source(itype, doc_id, row.get("tactic") or "", entity_type="interaction")
        categories = detect_categories(f"{notes} {outcome} {contact} {itype}", itype, entity_type="interaction")

        # Primary category badge
        primary_cat = "Call"
        if "Security" in categories:
            primary_cat = "Security"
        elif "Objections" in categories:
            primary_cat = "Objection"
        elif "Pricing" in categories:
            primary_cat = "Pricing"
        elif "Calls" in categories:
            primary_cat = "Call"
        elif "Requirements" in categories:
            primary_cat = "Requirement"

        # Card Title
        contact_brief = contact.split("(")[0].strip() if "(" in contact else contact
        if " and " in contact_brief:
            contact_brief = contact_brief.split(" and ")[-1].strip()
        headline_type = "CALL" if "call" in source.lower() or "demo" in source.lower() or "session" in source.lower() else itype.upper()
        title = f"{headline_type} · {contact_brief}"

        storage = "Hindsight + Local Store" if row.get("retained") else "Local Store"

        statement = extract_short_statement(notes, outcome)

        memories.append(
            DealMemory(
                id=f"interaction-{doc_id}",
                entity_type="interaction",
                date=row.get("happened_on") or "",
                formatted_date=format_memory_date(row.get("happened_on") or ""),
                title=title,
                category=primary_cat,
                categories=categories,
                statement=statement,
                content=notes,
                contact=contact,
                source=source,
                type=itype,
                deal_slug=deal_slug,
                deal_name=deal_name,
                storage=storage,
                retained_in_hindsight=bool(row.get("retained")),
                document_id=doc_id,
                outcome=outcome,
                tactic=row.get("tactic") or "",
                result=row.get("result") or "open",
            )
        )

    # 2. Load Commitments (Promises)
    commitments = store.commitments(deal_slug)
    for c in commitments:
        what = c.get("what") or ""
        who = c.get("who") or "Customer"
        status = c.get("status") or "open"
        due_on = c.get("due_on") or ""
        categories = detect_categories(f"{what} {who}", "Promise", entity_type="commitment")

        title = f"PROMISE · {who}"
        statement = f"Promise to {who}: {what}"

        memories.append(
            DealMemory(
                id=f"commitment-{c['id']}",
                entity_type="commitment",
                date=due_on,
                formatted_date=format_memory_date(due_on),
                title=title,
                category="Promise",
                categories=categories,
                statement=statement,
                content=f"Promise: {what}\nRecipient: {who}\nDue date: {due_on}\nStatus: {status.capitalize()}",
                contact=who,
                source="Promise",
                type="Promise",
                deal_slug=deal_slug,
                deal_name=deal_name,
                storage="Local Store",
                retained_in_hindsight=False,
                commitment_id=c["id"],
                status=status,
            )
        )

    # Sort memories reverse-chronologically by date
    memories.sort(key=lambda m: m.date or "1970-01-01", reverse=True)

    # Apply Category Filter
    if category_filter and category_filter != "All":
        target = category_filter.lower()
        memories = [m for m in memories if any(target in cat.lower() for cat in m.categories)]

    # Apply Search Filter
    if search_query and search_query.strip():
        q = search_query.strip().lower()
        memories = [
            m
            for m in memories
            if (
                q in m.statement.lower()
                or q in m.content.lower()
                or q in m.contact.lower()
                or q in m.source.lower()
                or q in m.title.lower()
                or q in m.outcome.lower()
                or q in m.tactic.lower()
            )
        ]

    return memories
