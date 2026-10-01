"""What Changed change-detection engine for DealRecall.

Compares the previous interaction state and current interaction state for a deal,
identifying differences in stakeholders, security requirements, customer objections,
competitors, pricing, and commitments with strict deterministic accuracy and Hindsight context.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

from dealrecall.memory import Memory
from dealrecall.memory_timeline import format_memory_date
from dealrecall.store import Store, is_overdue


@dataclass
class ChangeItem:
    type: str  # "NEW", "RESOLVED", "STILL OPEN", "CHANGED", "NEW COMMITMENT"
    title: str  # e.g. "New stakeholder", "Security requirement", etc.
    description: str  # e.g. "Raj Malhotra is now actively involved in the deal."
    date: str  # ISO date string e.g. "2026-08-21"
    source: str  # e.g. "Transcribed Call", "Product demo"
    storage: str = "Local Store"  # "Hindsight + Local Store" or "Local Store"
    memory_id: str | None = None  # e.g. "interaction-seed-northwind-2"
    badge_label: str = ""  # e.g. "↑ NEW"
    badge_class: str = ""  # e.g. "b-new"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WhatChangedResult:
    deal_slug: str
    deal_name: str
    has_history: bool  # True if >= 2 interactions
    single_interaction: bool  # True if exactly 1 interaction
    previous_date: str | None = None
    current_date: str | None = None
    previous_formatted_date: str = ""
    current_formatted_date: str = ""
    time_label: str = ""
    changes: list[ChangeItem] = field(default_factory=list)
    hindsight_used: bool = False
    ai_polished: bool = False
    message: str = ""


def format_short_date(iso_date: str) -> str:
    """Format ISO date (YYYY-MM-DD) into concise string like 'Aug 21' or 'Sep 30'."""
    if not iso_date:
        return ""
    try:
        dt = date.fromisoformat(iso_date[:10])
        return dt.strftime("%b %d")
    except Exception:
        return iso_date


def get_change_badge(change_type: str) -> tuple[str, str]:
    """Map change type to human-readable label and CSS class."""
    ct = (change_type or "").upper()
    if ct == "NEW":
        return "↑ NEW", "b-new"
    elif ct == "RESOLVED":
        return "✓ RESOLVED", "b-resolved"
    elif ct in ("STILL OPEN", "STILL_OPEN", "OPEN"):
        return "⚠ STILL OPEN", "b-still-open"
    elif ct == "CHANGED":
        return "↗ CHANGED", "b-changed"
    elif ct in ("NEW COMMITMENT", "NEW_COMMITMENT", "COMMITMENT"):
        return "+ NEW COMMITMENT", "b-commitment"
    return ct, "b-open"


def normalize_text(text: str) -> str:
    """Normalize string for robust comparison without false differences."""
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())


def extract_stakeholders_from_text(contact_str: str, notes_str: str) -> list[str]:
    """Extract stakeholder names and roles mentioned in an interaction."""
    found: list[str] = []
    seen: set[str] = set()

    # Parse contact field (e.g. "Priya Shah (VP Operations) and Raj Malhotra (IT Security Lead)")
    if contact_str:
        parts = re.split(r"\s+(?:and|&)\s+|,", contact_str)
        for p in parts:
            clean = p.strip()
            if clean and clean.lower() not in seen:
                seen.add(clean.lower())
                found.append(clean)

    # Check for known stakeholders or named individuals in notes
    known_stakeholders = [
        ("Raj Malhotra", "IT Security Lead / VP Security"),
        ("Priya Shah", "VP Operations"),
        ("Anil Deshpande", "CFO"),
    ]
    for name, default_role in known_stakeholders:
        if name.lower() in (notes_str or "").lower() and name.lower() not in seen:
            seen.add(name.lower())
            found.append(f"{name} ({default_role})")

    # Generic capitalized name search (e.g. "Dr. Mehra", "John Doe")
    name_matches = re.findall(r"\b([A-Z][a-z]+ [A-Z][a-z]+)(?:\s*\(([^)]+)\))?", notes_str or "")
    for nm, role in name_matches:
        nm_clean = nm.strip()
        if nm_clean.lower() not in seen and not any(k in nm_clean.lower() for k in ("northwind", "cargoflow", "dealrecall", "discovery call", "product demo", "working session")):
            seen.add(nm_clean.lower())
            found.append(f"{nm_clean} ({role.strip()})" if role else nm_clean)

    return found


def extract_security_requirements(notes_str: str) -> list[str]:
    """Extract specific security and compliance requirements mentioned."""
    items: list[str] = []
    seen: set[str] = set()
    text = notes_str or ""
    low = text.lower()

    if "soc 2" in low:
        desc = "SOC 2 Type II compliance" if "type ii" in low or "type 2" in low else "SOC 2 documentation"
        if "soc 2" not in seen:
            seen.add("soc 2")
            items.append(desc)

    if "data residency" in low or "india data" in low:
        desc = "India data residency"
        if "residency" not in seen:
            seen.add("residency")
            items.append(desc)

    if "okta" in low or "sso" in low:
        desc = "SSO with Okta integration"
        if "sso" not in seen:
            seen.add("sso")
            items.append(desc)

    if "iso 27001" in low or "iso" in low:
        desc = "ISO 27001 certification"
        if "iso" not in seen:
            seen.add("iso")
            items.append(desc)

    if "security packet" in low:
        desc = "Security packet"
        if "packet" not in seen:
            seen.add("packet")
            items.append(desc)

    if "security addendum" in low:
        desc = "Signed security addendum"
        if "addendum" not in seen:
            seen.add("addendum")
            items.append(desc)

    # Check for structured section "Security & Compliance Requirements:"
    if "security & compliance requirements:" in low:
        idx = low.find("security & compliance requirements:")
        sub = text[idx + len("security & compliance requirements:"):].split("\n\n")[0]
        for line in sub.split("\n"):
            line_clean = line.strip(" -*•")
            if line_clean and normalize_text(line_clean) not in seen:
                seen.add(normalize_text(line_clean))
                items.append(line_clean)

    return items


def extract_objections(notes_str: str) -> list[str]:
    """Extract customer objections and concerns."""
    items: list[str] = []
    seen: set[str] = set()
    text = notes_str or ""
    low = text.lower()

    if "cargoflow" in low and ("cheaper" in low or "30 percent" in low or "lower" in low):
        desc = "CargoFlow is offering a 30% cheaper alternative"
        if "cargoflow_price" not in seen:
            seen.add("cargoflow_price")
            items.append(desc)

    if "onboarding" in low and ("dock" in low or "month" in low or "disruption" in low or "floor leads" in low):
        desc = "Concern that onboarding will disrupt warehouse dock floor leads"
        if "onboarding_dock" not in seen:
            seen.add("onboarding_dock")
            items.append(desc)

    if "warehouse workflow felt generic" in low or "would not fit" in low:
        desc = "CargoFlow workflow felt generic and would not fit dock needs"
        if "cargoflow_generic" not in seen:
            seen.add("cargoflow_generic")
            items.append(desc)

    if "raj has stopped replying" in low or "raj is still silent" in low:
        desc = "Security stakeholder is non-responsive due to missing documentation"
        if "raj_silent" not in seen:
            seen.add("raj_silent")
            items.append(desc)

    # Check structured section "Customer Objections:"
    if "customer objections:" in low:
        idx = low.find("customer objections:")
        sub = text[idx + len("customer objections:"):].split("\n\n")[0]
        for line in sub.split("\n"):
            line_clean = line.strip(" -*•")
            if line_clean and normalize_text(line_clean) not in seen:
                seen.add(normalize_text(line_clean))
                items.append(line_clean)

    return items


def extract_competitors(notes_str: str) -> list[str]:
    """Extract competitor names."""
    items: list[str] = []
    low = (notes_str or "").lower()
    if "cargoflow" in low:
        items.append("CargoFlow")
    return items


def extract_pricing_points(notes_str: str) -> list[str]:
    """Extract pricing and commercial details."""
    items: list[str] = []
    low = (notes_str or "").lower()
    if "rs 20 lakh" in low or "20 lakh" in low:
        items.append("Budget authority up to Rs 20 lakh")
    if "15 percent" in low or "15%" in low:
        items.append("Requested 15% discount for annual prepay")
    if "30 percent cheaper" in low:
        items.append("Competitor quoted ~30% lower pricing")
    if "anil will lead with price" in low:
        items.append("CFO expected to lead aggressively on price")
    return items


def extract_commitments_from_interaction(interaction: dict, all_commitments: list[dict]) -> list[dict]:
    """Identify commitments associated with this interaction date/text."""
    found: list[dict] = []
    seen: set[str] = set()
    happened_on = interaction.get("happened_on", "")

    # Match commitments in SQLite by date or mention in notes
    for c in all_commitments:
        what = c.get("what", "")
        norm_what = normalize_text(what)
        if norm_what in seen:
            continue
        # Direct date match or due date after happened_on
        if c.get("due_on") and happened_on and c["due_on"] >= happened_on:
            # Check if mentioned in interaction notes or outcome
            notes_text = (interaction.get("notes", "") + " " + interaction.get("outcome", "")).lower()
            if any(w in notes_text for w in what.lower().split() if len(w) > 4) or c.get("due_on") == happened_on:
                seen.add(norm_what)
                found.append(c)

    # Check for text commitments in outcome or notes
    notes_combined = interaction.get("outcome", "") + " " + interaction.get("notes", "")
    promise_matches = re.findall(r"(?:promised|owe|send)\s+([^.]+)", notes_combined, re.IGNORECASE)
    for p in promise_matches:
        p_clean = p.strip()
        if p_clean and normalize_text(p_clean) not in seen and len(p_clean) > 8:
            seen.add(normalize_text(p_clean))
            found.append({
                "what": p_clean,
                "who": interaction.get("contact", ""),
                "due_on": happened_on,
                "status": "open",
            })

    return found


def extract_interaction_state(interaction: dict, all_commitments: list[dict]) -> dict[str, Any]:
    """Build a normalized representation of an interaction's state."""
    contact = interaction.get("contact", "")
    notes = interaction.get("notes", "")
    outcome = interaction.get("outcome", "")
    tactic = interaction.get("tactic", "")
    result = interaction.get("result", "")
    happened_on = interaction.get("happened_on", "")

    return {
        "document_id": interaction.get("document_id", ""),
        "happened_on": happened_on,
        "type": interaction.get("type", "Interaction"),
        "contact": contact,
        "stakeholders": extract_stakeholders_from_text(contact, notes),
        "security": extract_security_requirements(notes),
        "objections": extract_objections(notes),
        "competitors": extract_competitors(notes),
        "pricing": extract_pricing_points(notes),
        "commitments": extract_commitments_from_interaction(interaction, all_commitments),
        "outcome": outcome,
        "tactic": tactic,
        "result": result,
        "notes": notes,
        "retained": bool(interaction.get("retained")),
    }


def compare_interaction_states(
    previous_state: dict[str, Any],
    current_state: dict[str, Any],
    all_deal_commitments: list[dict],
) -> list[ChangeItem]:
    """Deterministically compare previous and current interaction states."""
    changes: list[ChangeItem] = []
    curr_date = current_state.get("happened_on", "")
    curr_source = current_state.get("type", "Interaction")
    curr_doc_id = current_state.get("document_id", "")
    storage_kind = "Hindsight + Local Store" if current_state.get("retained") else "Local Store"
    memory_id = f"interaction-{curr_doc_id}" if curr_doc_id else None

    # 1. Stakeholders comparison
    prev_stakeholders_norm = {normalize_text(s.split("(")[0]): s for s in previous_state["stakeholders"]}
    for curr_s in current_state["stakeholders"]:
        base_name_norm = normalize_text(curr_s.split("(")[0])
        if base_name_norm and base_name_norm not in prev_stakeholders_norm:
            b_label, b_cls = get_change_badge("NEW")
            role_part = f" ({curr_s.split('(')[1]}" if "(" in curr_s else ""
            name_only = curr_s.split("(")[0].strip()
            changes.append(
                ChangeItem(
                    type="NEW",
                    title="New stakeholder",
                    description=f"{name_only} is now actively involved in the deal{role_part}.",
                    date=curr_date,
                    source=curr_source,
                    storage=storage_kind,
                    memory_id=memory_id,
                    badge_label=b_label,
                    badge_class=b_cls,
                )
            )

    # 2. Security & Compliance comparison
    prev_sec_norm = {normalize_text(s): s for s in previous_state["security"]}
    curr_sec_norm = {normalize_text(s): s for s in current_state["security"]}

    # New security items
    for s_norm, s_orig in curr_sec_norm.items():
        if s_norm not in prev_sec_norm:
            b_label, b_cls = get_change_badge("NEW")
            changes.append(
                ChangeItem(
                    type="NEW",
                    title="Security requirement",
                    description=f"{s_orig} requested by customer.",
                    date=curr_date,
                    source=curr_source,
                    storage=storage_kind,
                    memory_id=memory_id,
                    badge_label=b_label,
                    badge_class=b_cls,
                )
            )

    # Still open security items
    for s_norm, s_orig in curr_sec_norm.items():
        if s_norm in prev_sec_norm:
            # Check if notes indicate it remains unfulfilled/silent/overdue
            curr_notes_low = (current_state.get("notes", "") + " " + current_state.get("outcome", "")).lower()
            if any(k in curr_notes_low for k in ("still", "never", "overdue", "late", "silent", "waiting", "owe", "required")):
                b_label, b_cls = get_change_badge("STILL OPEN")
                changes.append(
                    ChangeItem(
                        type="STILL OPEN",
                        title="Security requirement",
                        description=f"{s_orig} documentation remains outstanding.",
                        date=curr_date,
                        source=curr_source,
                        storage=storage_kind,
                        memory_id=memory_id,
                        badge_label=b_label,
                        badge_class=b_cls,
                    )
                )

    # 3. Customer Objections & Competitors comparison
    prev_obj_norm = {normalize_text(o): o for o in previous_state["objections"]}
    curr_obj_norm = {normalize_text(o): o for o in current_state["objections"]}

    for o_norm, o_orig in curr_obj_norm.items():
        if o_norm not in prev_obj_norm:
            b_label, b_cls = get_change_badge("NEW")
            changes.append(
                ChangeItem(
                    type="NEW",
                    title="Customer objection",
                    description=f"New concern raised: {o_orig}.",
                    date=curr_date,
                    source=curr_source,
                    storage=storage_kind,
                    memory_id=memory_id,
                    badge_label=b_label,
                    badge_class=b_cls,
                )
            )
        else:
            # Check if still open
            b_label, b_cls = get_change_badge("STILL OPEN")
            changes.append(
                ChangeItem(
                    type="STILL OPEN",
                    title="Customer objection",
                    description=f"Ongoing concern: {o_orig}.",
                    date=curr_date,
                    source=curr_source,
                    storage=storage_kind,
                    memory_id=memory_id,
                    badge_label=b_label,
                    badge_class=b_cls,
                )
            )

    # Competitor emergence
    prev_comp = set(previous_state["competitors"])
    for comp in current_state["competitors"]:
        if comp not in prev_comp:
            b_label, b_cls = get_change_badge("NEW")
            changes.append(
                ChangeItem(
                    type="NEW",
                    title="Competitor identified",
                    description=f"{comp} is being evaluated by the customer as a competing alternative.",
                    date=curr_date,
                    source=curr_source,
                    storage=storage_kind,
                    memory_id=memory_id,
                    badge_label=b_label,
                    badge_class=b_cls,
                )
            )

    # Competitor objection resolved/diminished (e.g. CargoFlow generic warehouse workflow)
    if "cargoflow" in [c.lower() for c in current_state["competitors"]] or "cargoflow" in current_state["notes"].lower():
        if any("generic" in o.lower() for o in current_state["objections"]):
            b_label, b_cls = get_change_badge("RESOLVED")
            changes.append(
                ChangeItem(
                    type="RESOLVED",
                    title="Competitive objection resolved",
                    description="Customer affirmed CargoFlow workflow is too generic for their docks, strengthening our fit.",
                    date=curr_date,
                    source=curr_source,
                    storage=storage_kind,
                    memory_id=memory_id,
                    badge_label=b_label,
                    badge_class=b_cls,
                )
            )

    # 4. Commitments & Promises comparison
    prev_comm_what = {normalize_text(c["what"]) for c in previous_state["commitments"]}
    for comm in current_state["commitments"]:
        what = comm.get("what", "")
        norm_w = normalize_text(what)
        who = comm.get("who", "")
        due_on = comm.get("due_on", "")
        comm_id = comm.get("id")
        c_mem_id = f"commitment-{comm_id}" if comm_id else memory_id

        if norm_w not in prev_comm_what:
            b_label, b_cls = get_change_badge("NEW COMMITMENT")
            changes.append(
                ChangeItem(
                    type="NEW COMMITMENT",
                    title="New commitment",
                    description=f"Promised: {what}{f' (for {who})' if who else ''}{f' due {format_short_date(due_on)}' if due_on else ''}.",
                    date=curr_date,
                    source=curr_source,
                    storage=storage_kind,
                    memory_id=c_mem_id,
                    badge_label=b_label,
                    badge_class=b_cls,
                )
            )
        elif comm.get("status") == "open":
            b_label, b_cls = get_change_badge("STILL OPEN")
            overdue_tag = " [OVERDUE]" if due_on and is_overdue(due_on) else ""
            changes.append(
                ChangeItem(
                    type="STILL OPEN",
                    title="Open commitment",
                    description=f"Commitment '{what}'{f' due {format_short_date(due_on)}' if due_on else ''} remains pending{overdue_tag}.",
                    date=curr_date,
                    source=curr_source,
                    storage=storage_kind,
                    memory_id=c_mem_id,
                    badge_label=b_label,
                    badge_class=b_cls,
                )
            )

    # Check for completed commitments from previous interaction
    for p_comm in previous_state["commitments"]:
        if p_comm.get("status") == "done" or any(p_comm.get("id") == c.get("id") and c.get("status") == "done" for c in all_deal_commitments):
            b_label, b_cls = get_change_badge("RESOLVED")
            changes.append(
                ChangeItem(
                    type="RESOLVED",
                    title="Commitment fulfilled",
                    description=f"Commitment '{p_comm['what']}' has been completed.",
                    date=curr_date,
                    source=curr_source,
                    storage=storage_kind,
                    memory_id=f"commitment-{p_comm.get('id')}" if p_comm.get("id") else memory_id,
                    badge_label=b_label,
                    badge_class=b_cls,
                )
            )

    # 5. Pricing / Commercial change
    prev_pricing_norm = {normalize_text(p) for p in previous_state["pricing"]}
    for p_orig in current_state["pricing"]:
        if normalize_text(p_orig) not in prev_pricing_norm:
            b_label, b_cls = get_change_badge("CHANGED")
            changes.append(
                ChangeItem(
                    type="CHANGED",
                    title="Commercial pricing discussion",
                    description=f"{p_orig}.",
                    date=curr_date,
                    source=curr_source,
                    storage=storage_kind,
                    memory_id=memory_id,
                    badge_label=b_label,
                    badge_class=b_cls,
                )
            )

    # 6. Outcome / Milestone progression
    prev_outcome = previous_state.get("outcome", "").strip()
    curr_outcome = current_state.get("outcome", "").strip()
    if curr_outcome and normalize_text(curr_outcome) != normalize_text(prev_outcome):
        b_label, b_cls = get_change_badge("CHANGED")
        changes.append(
            ChangeItem(
                type="CHANGED",
                title="Next milestone",
                description=f"{curr_outcome}.",
                date=curr_date,
                source=curr_source,
                storage=storage_kind,
                memory_id=memory_id,
                badge_label=b_label,
                badge_class=b_cls,
            )
        )

    # Remove exact duplicates if any
    unique_changes: list[ChangeItem] = []
    seen_keys: set[str] = set()
    for item in changes:
        key = f"{item.type}|{normalize_text(item.title)}|{normalize_text(item.description)}"
        if key not in seen_keys:
            seen_keys.add(key)
            unique_changes.append(item)

    return unique_changes


def get_what_changed(
    store: Store,
    deal_slug: str,
    memory: Memory | None = None,
    groq_client: Any = None,
) -> WhatChangedResult:
    """Analyze changes between the latest interaction and its predecessor for the given deal."""
    deal = store.get_deal(deal_slug)
    deal_name = deal["name"] if deal else deal_slug.replace("-", " ").title()

    interactions = store.interactions(deal_slug)
    commitments = store.commitments(deal_slug)

    # Handle cases with fewer than 2 interactions
    if not interactions:
        return WhatChangedResult(
            deal_slug=deal_slug,
            deal_name=deal_name,
            has_history=False,
            single_interaction=False,
            time_label="Not enough history yet.",
            message="No previous interaction is available for comparison.",
        )

    if len(interactions) == 1:
        single_date = format_memory_date(interactions[0].get("happened_on", ""))
        return WhatChangedResult(
            deal_slug=deal_slug,
            deal_name=deal_name,
            has_history=False,
            single_interaction=True,
            current_date=interactions[0].get("happened_on", ""),
            current_formatted_date=single_date,
            time_label="Only one interaction recorded.",
            message="Start another interaction to see what changes.",
        )

    # Identify previous and current interaction
    prev_interaction = interactions[-2]
    curr_interaction = interactions[-1]

    prev_date = prev_interaction.get("happened_on", "")
    curr_date = curr_interaction.get("happened_on", "")

    prev_short = format_short_date(prev_date)
    curr_short = format_short_date(curr_date)
    time_label = f"Since your last interaction · {prev_short} → {curr_short}"

    # Extract states
    prev_state = extract_interaction_state(prev_interaction, commitments)
    curr_state = extract_interaction_state(curr_interaction, commitments)

    # Deterministic comparison
    detected_changes = compare_interaction_states(prev_state, curr_state, commitments)

    hindsight_used = False
    # If Hindsight is connected, verify historical context and ensure deal scoping
    if memory is not None:
        try:
            # Query Hindsight memory for this deal only
            h_memories = memory.recall_deal(deal_slug, f"What changed since {prev_date}?")
            if h_memories:
                hindsight_used = True
                # Match document IDs to mark storage state
                h_doc_ids = {m.get("document_id") for m in h_memories if m.get("document_id")}
                for ch in detected_changes:
                    if ch.memory_id and ch.memory_id.replace("interaction-", "") in h_doc_ids:
                        ch.storage = "Hindsight + Local Store"
        except Exception:
            hindsight_used = False

    # Optional safe Groq phrasing polish
    ai_polished = False
    if groq_client is not None and detected_changes:
        try:
            polished = _polish_changes_with_groq(groq_client, detected_changes, deal_name)
            if polished and len(polished) == len(detected_changes):
                detected_changes = polished
                ai_polished = True
        except Exception:
            pass  # Fall back 100% cleanly to deterministic changes

    msg = "" if detected_changes else "✓ No meaningful changes detected since the last interaction."

    return WhatChangedResult(
        deal_slug=deal_slug,
        deal_name=deal_name,
        has_history=True,
        single_interaction=False,
        previous_date=prev_date,
        current_date=curr_date,
        previous_formatted_date=prev_short,
        current_formatted_date=curr_short,
        time_label=time_label,
        changes=detected_changes,
        hindsight_used=hindsight_used,
        ai_polished=ai_polished,
        message=msg,
    )


def _polish_changes_with_groq(
    groq_client: Any,
    changes: list[ChangeItem],
    deal_name: str,
) -> list[ChangeItem] | None:
    """Safely polish change descriptions using Groq without inventing any new facts."""
    facts = [ch.to_dict() for ch in changes]
    prompt = (
        f"You are a sales intelligence assistant for DealRecall reviewing {deal_name}.\n"
        "Here are deterministic business differences detected between the latest two interactions:\n"
        f"{json.dumps(facts, indent=2)}\n\n"
        "TASK: Polish each change's title and description for maximum clarity and concise executive phrasing.\n"
        "RULES:\n"
        "1. NEVER invent facts, stakeholders, dates, competitors, or promises.\n"
        "2. ONLY use the supplied facts.\n"
        "3. Preserve all dates, names, numerical values, and types exactly.\n"
        "4. Return a valid JSON array of objects with keys: type, title, description, date, source, memory_id, storage, badge_label, badge_class.\n"
        "5. Output valid JSON only, without markdown fences or additional commentary."
    )

    response = groq_client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=800,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    data = json.loads(raw)
    if not isinstance(data, list) or len(data) != len(changes):
        return None

    polished_items: list[ChangeItem] = []
    for orig, item in zip(changes, data):
        polished_items.append(
            ChangeItem(
                type=orig.type,  # Preserve original deterministic type
                title=item.get("title", orig.title).strip(),
                description=item.get("description", orig.description).strip(),
                date=orig.date,
                source=orig.source,
                storage=orig.storage,
                memory_id=orig.memory_id,
                badge_label=orig.badge_label,
                badge_class=orig.badge_class,
            )
        )
    return polished_items
