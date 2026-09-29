import sys
import os

if __name__ == "__main__":
    try:
        from streamlit import runtime

        if not runtime.exists():
            from streamlit.web import cli as stcli

            sys.argv = ["streamlit", "run", os.path.abspath(__file__)]
            sys.exit(stcli.main())
    except ImportError:
        pass

import html
import uuid
from datetime import date
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from groq import Groq

from dealrecall.agent import BriefError, friendly_service_error, groq_model, parse_sections, run_brief
from dealrecall.memory import Memory
from dealrecall.store import Store, format_inr, is_overdue
from dealrecall.theme import CSS

load_dotenv()

ROOT = Path(__file__).resolve().parent
store = Store(ROOT / "data" / "dealrecall.db")

st.set_page_config(
    page_title="DealRecall | Sales Copilot",
    page_icon="DR",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(CSS, unsafe_allow_html=True)

QUICK_PROMPTS = {
    "Prep the call": "How should I prepare for the commercial call with Anil Deshpande on 30 September?",
    "Handle pricing": "They want a discount because a competitor is cheaper. What should I do, based on deals we already won or lost?",
    "Close the loop": "What have we promised that is still open, and what happens if we walk in without it?",
    "Who is missing": "Which stakeholders are not in the room yet, and what did we learn about that on other deals?",
}


def esc(value) -> str:
    return html.escape(str(value or ""))


def groq_client():
    key = os.getenv("GROQ_API_KEY", "").strip()
    return Groq(api_key=key, timeout=90.0) if key else None


def connect_memory() -> Memory | None:
    return Memory.from_env()


def pretty_date(iso: str) -> str:
    parsed = date.fromisoformat(str(iso)[:10])
    return f"{parsed.day} {parsed.strftime('%b %Y')}"


def money(value: int) -> str:
    if not value:
        return "Value not set"
    return format_inr(value).replace("Rs ", "₹")


def badge_class(label: str) -> str:
    text = label.lower()
    if "demo" in text:
        return "b-demo"
    if "email" in text:
        return "b-email"
    if "meeting" in text or "session" in text or "commercial" in text:
        return "b-meeting"
    return "b-call"


def render_brief(text: str, key_prefix: str) -> None:
    sections = parse_sections(text)
    if not sections:
        st.markdown(text)
        return
    used: set[str] = set()

    def card(num: int, title: str, body: str) -> None:
        key = f"{key_prefix}-{num}"
        while key in used:
            key += "x"
        used.add(key)
        with st.container(key=key):
            st.markdown(f"<div class='sec-title'>{esc(title)}</div>", unsafe_allow_html=True)
            st.markdown(body)

    card(*sections[0])
    rest = sections[1:]
    for index in range(0, len(rest), 2):
        cols = st.columns(2, gap="medium")
        for col, section in zip(cols, rest[index : index + 2]):
            with col:
                card(*section)


def render_memories(memories: list[dict]) -> None:
    if not memories:
        st.caption("No memories came back.")
        return
    for item in memories:
        kind = (item.get("type") or "memory").upper()
        css = "mem play" if "playbook" in item.get("tags", []) else "mem"
        source = item.get("source") or "Hindsight"
        relevance = item.get("relevance") or "Supporting"
        st.markdown(
            f"<div class='{css}'><small>{esc(kind)} · {esc(source)} · Relevance {esc(relevance)}</small>"
            f"<br>{esc(item.get('text'))}</div>",
            unsafe_allow_html=True,
        )


def render_selection(brief) -> None:
    detail = ""
    for step in brief.trace or []:
        if step.get("label") == "Relevant memories selected":
            detail = step.get("detail") or ""
            break
    if not detail:
        detail = f"{len(brief.memories)} memories selected"
    counts: dict[str, int] = {}
    for item in brief.memories:
        source = item.get("source") or "Hindsight"
        counts[source] = counts.get(source, 0) + 1
    chips = "".join(
        f"<span class='chip'>{esc(name)}<b>{count}</b></span>" for name, count in counts.items()
    )
    st.markdown(
        "<div class='picked'>"
        f"<strong>{esc(detail)}</strong>"
        "<span>Groq only saw this short list. Open the list below to read each memory.</span>"
        f"<div class='chips'>{chips}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_trace(trace: list[dict]) -> None:
    if not trace:
        return
    with st.expander("How the agent used memory"):
        for number, step in enumerate(trace, 1):
            status = "done" if step.get("ok") else "failed"
            detail = step.get("detail") or ""
            st.markdown(f"{number}. **{esc(step.get('label') or step.get('tool') or 'Step')}** — {status}")
            if detail:
                st.caption(detail)


def prepare_bank(memory: Memory | None) -> None:
    if memory is None:
        return
    if "bank_ready" not in st.session_state:
        with st.spinner("Connecting the Hindsight bank…"):
            try:
                st.session_state["bank_warnings"] = memory.ensure_bank()
                st.session_state["bank_ready"] = True
                st.session_state.pop("seed_error", None)
            except Exception as exc:
                st.session_state["bank_error"] = str(exc)
                return
    if st.session_state.get("bank_error"):
        return
    if store.meta_get("hindsight_seeded") == "1":
        if "synced_pending" not in st.session_state:
            try:
                st.session_state["synced_count"] = memory.sync_pending(store)
            except Exception as exc:
                st.session_state["sync_error"] = str(exc)
            st.session_state["synced_pending"] = True
        return
    if st.session_state.get("seed_error"):
        return
    with st.spinner("Teaching Hindsight the sample pipeline. The first run can take a few minutes…"):
        try:
            st.session_state["seed_count"] = memory.install_sample(store)
            st.session_state.pop("seed_error", None)
        except Exception as exc:
            st.session_state["seed_error"] = str(exc)


memory = connect_memory()
client = groq_client()
prepare_bank(memory)

hindsight_on = memory is not None and bool(st.session_state.get("bank_ready"))
seeded = store.meta_get("hindsight_seeded") == "1"
deals = store.deals()
open_promises = store.commitments(status="open")
overdue = [item for item in open_promises if is_overdue(item["due_on"])]
overdue_by_slug: dict[str, int] = {}
for item in overdue:
    overdue_by_slug[item["deal_slug"]] = overdue_by_slug.get(item["deal_slug"], 0) + 1

pipeline = sorted(deals, key=lambda deal: (deal["slug"] != "northwind-logistics", deal["name"]))
if "active_slug" not in st.session_state or not any(deal["slug"] == st.session_state["active_slug"] for deal in deals):
    st.session_state["active_slug"] = pipeline[0]["slug"] if pipeline else ""
if not pipeline:
    st.error("No deals in the local pipeline.")
    st.stop()
selected = next(deal for deal in deals if deal["slug"] == st.session_state["active_slug"])
selected_overdue = overdue_by_slug.get(selected["slug"], 0)
selected_notes = len(store.interactions(selected["slug"]))

memory_state = "on" if hindsight_on else "off"
memory_label = "Hindsight live" if hindsight_on else "Hindsight off"
if hindsight_on and not seeded:
    memory_state = "off"
    memory_label = "Memory not loaded"
groq_state = "on" if client else "off"
groq_label = "Groq connected" if client else "Groq missing"

st.markdown(
    f"""
    <div class="topbar">
      <div class="brand">
        <div class="mark">DR</div>
        <div>
          <strong>DealRecall</strong>
          <span>Brief the call from what the deal already said, and from what won last time.</span>
        </div>
      </div>
      <div class="status">
        <span class="hindsight-status {memory_state}">
          <span class="status-dot"></span>
          <span class="hindsight-copy">
            <strong>{memory_label}</strong>
            <em>{"Past deals can be recalled" if memory_state == "on" else "Memory briefs are unavailable"}</em>
          </span>
        </span>
        <span class="pill {groq_state}"><span class="status-dot"></span>{groq_label}</span>
        <span class="pill neutral">{esc(groq_model())}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

flash = st.session_state.pop("flash", None)
if flash:
    level, text = flash
    if level == "ok":
        st.success(text)
    elif level == "warn":
        st.warning(text)
    else:
        st.error(text)

if st.session_state.get("bank_error"):
    st.error(f"Hindsight could not be reached: {st.session_state['bank_error']}")
    if st.button("Retry connection"):
        st.session_state.pop("bank_error", None)
        st.session_state.pop("bank_ready", None)
        st.rerun()

if st.session_state.get("seed_error"):
    st.error(
        "The sample pipeline was not retained. Briefings will have nothing to recall until this succeeds. "
        f"{st.session_state['seed_error']}"
    )
    if st.button("Retry loading sample pipeline"):
        st.session_state.pop("seed_error", None)
        st.rerun()

for warning in st.session_state.get("bank_warnings") or []:
    st.caption(warning)

card_cols = st.columns(len(pipeline))
for column, deal in zip(card_cols, pipeline):
    hot = overdue_by_slug.get(deal["slug"], 0)
    hot_html = f" · <span class='hot-inline'>{hot} overdue</span>" if hot else ""
    value = money(deal["value_inr"])
    active = deal["slug"] == selected["slug"]
    stage_cls = "stage-" + deal["stage"].lower().replace(" ", "-")
    with column:
        with st.container(key=("dcardon_" if active else "dcardoff_") + deal["slug"]):
            st.markdown(
                f"<span class='deal-stage {stage_cls}'>{esc(deal['stage'])}</span>"
                f"<div class='deal-name'>{esc(deal['name'])}</div>"
                f"<div class='deal-meta'><span class='val-bold'>{esc(value)}</span>{hot_html}</div>",
                unsafe_allow_html=True,
            )
            if active:
                st.markdown("<div class='in-view'><span class='in-view-dot'></span>Active Deal</div>", unsafe_allow_html=True)
            elif st.button("Open Deal", key=f"sel_{deal['slug']}"):
                st.session_state["active_slug"] = deal["slug"]
                st.rerun()

if selected["slug"] == "northwind-logistics":
    story = "CFO call with Anil Deshpande is 30 September. Priya Shah is the champion. Raj Malhotra is waiting on security."
elif selected["stage"] == "Closed won":
    story = "Closed. Tactics from this deal are what the next briefing should reuse."
elif selected["stage"] == "Closed lost":
    story = "Lost. The miss stays in the playbook so the next deal does not repeat it."
else:
    story = selected["segment"]

flag_html = ""
if selected_overdue:
    flag_html += f"<span class='flag hot'>⚠️ {selected_overdue} overdue</span>"
flag_html += f"<span class='flag'>💬 {selected_notes} touchpoints</span>"
if selected["value_inr"]:
    flag_html += f"<span class='flag val'>💰 {esc(money(selected['value_inr']))}</span>"

st.markdown(
    f"""
    <div class="context">
      <div>
        <div class="kicker"><span class="in-view-dot"></span>{esc(selected['stage'])}</div>
        <h2>{esc(selected['name'])}</h2>
        <p>{esc(story)}</p>
      </div>
      <div class="flags">{flag_html}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

view = st.segmented_control(
    "Section",
    ["Prepare", "Timeline", "Log a call", "Memory"],
    default="Prepare",
    key="nav",
    label_visibility="collapsed",
)
if view is None:
    view = "Prepare"


def apply_prompt() -> None:
    choice = st.session_state.get("quick_prompt")
    if choice:
        st.session_state["user_query"] = QUICK_PROMPTS[choice]


if view == "Prepare":
    with st.container(key="panel_prepare"):
        if "user_query" not in st.session_state:
            st.session_state["user_query"] = QUICK_PROMPTS["Prep the call"]
        st.text_input("What do you need before the call?", key="user_query")
        st.pills(
            "Quick prompts",
            list(QUICK_PROMPTS.keys()),
            key="quick_prompt",
            on_change=apply_prompt,
            label_visibility="collapsed",
        )
        go_col, compare_col = st.columns([1.7, 1], gap="medium")
        with go_col:
            go = st.button(
                "Brief from Memory",
                type="primary",
                key="brief_go",
                disabled=not (client and hindsight_on),
                use_container_width=True,
            )
        with compare_col:
            compare = st.button(
                "Compare with no memory",
                key="brief_compare",
                disabled=not client,
                use_container_width=True,
            )
        if not client:
            st.caption("Add GROQ_API_KEY to .env. AI generation is unavailable until then.")
        elif not hindsight_on:
            st.caption(
                "Hindsight is unavailable right now. Your saved deal information is still available, "
                "but memory-based preparation could not be generated."
            )

    question = st.session_state["user_query"].strip()

    if (go or compare) and not question:
        st.error("Ask something before generating a briefing.")
    elif go or compare:
        memory_brief = None
        generic_brief = None
        memory_error = None
        generic_error = None
        try:
            with st.status("Recalling deal history…", expanded=True) as status:
                def on_progress(label: str) -> None:
                    status.update(label=label)

                if go or (compare and hindsight_on and memory is not None):
                    try:
                        memory_brief = run_brief(
                            groq_client=client,
                            memory=memory,
                            store=store,
                            deal=selected,
                            question=question,
                            use_memory=True,
                            on_progress=on_progress,
                        )
                    except BriefError as exc:
                        memory_error = exc.message
                if compare and client:
                    try:
                        generic_brief = run_brief(
                            groq_client=client,
                            memory=None,
                            store=store,
                            deal=selected,
                            question=question,
                            use_memory=False,
                            on_progress=on_progress,
                        )
                    except BriefError as exc:
                        generic_error = exc.message
                if memory_brief:
                    status.update(label="Memory-powered briefing ready", state="complete")
                elif memory_error and not generic_brief:
                    status.update(label="Preparation could not be finished", state="error")
        except Exception:
            memory_error = memory_error or (
                "Preparation could not be finished. The deal record is still available. Try Brief from Memory again."
            )
        if memory_brief or generic_brief:
            st.session_state["brief"] = {
                "deal": selected["slug"],
                "question": question,
                "memory": memory_brief,
                "generic": generic_brief,
            }
        if memory_error:
            st.error(memory_error)
        if generic_error:
            st.error(generic_error)

    result = st.session_state.get("brief")
    if result and result["deal"] == selected["slug"]:
        memory_brief = result["memory"]
        generic_brief = result["generic"]
        if memory_brief and generic_brief:
            st.markdown(
                "<div class='compare-intro'>"
                "<div class='ready'>Memory-powered briefing ready</div>"
                "<p>Same question, two briefs. <b>With Hindsight</b> uses recalled history from this deal and other deals. "
                "<b>Without memory</b> only has the company, stage, and value.</p>"
                "</div>",
                unsafe_allow_html=True,
            )
            mem_col, gen_col = st.columns(2, gap="medium")
            with mem_col:
                with st.container(key="cmp_with"):
                    st.markdown(
                        "<div class='col-label with'>With Hindsight"
                        "<span>People, objections, open promises, and lessons from other deals</span></div>",
                        unsafe_allow_html=True,
                    )
                    render_brief(memory_brief.text, "mem")
            with gen_col:
                with st.container(key="cmp_without"):
                    st.markdown(
                        "<div class='col-label without'>Without memory"
                        "<span>No past calls and no other deals</span></div>",
                        unsafe_allow_html=True,
                    )
                    render_brief(generic_brief.text, "gen")
        elif memory_brief:
            st.markdown(
                "<div class='ready'>Memory-powered briefing ready</div>",
                unsafe_allow_html=True,
            )
            st.markdown(f"### {esc(selected['name'])}")
            render_brief(memory_brief.text, "mem")
        elif generic_brief:
            st.markdown(f"### Generic briefing: {esc(selected['name'])}")
            render_brief(generic_brief.text, "gen")

        if memory_brief:
            render_selection(memory_brief)
            render_trace(memory_brief.trace)
            with st.expander(f"Read the {len(memory_brief.memories)} selected memories"):
                render_memories(memory_brief.memories)
            if hindsight_on and st.button("Ask Hindsight to reflect"):
                with st.spinner("Hindsight is reasoning over the bank…"):
                    try:
                        st.session_state["reflection"] = {
                            "slug": selected["slug"],
                            "text": memory.reflect(selected["name"], question),
                        }
                    except Exception as exc:
                        st.error(friendly_service_error(exc, "Hindsight"))
            reflection = st.session_state.get("reflection")
            if reflection and reflection.get("slug") == selected["slug"] and memory_brief:
                st.markdown("#### Hindsight reflect")
                st.markdown(reflection["text"])
    else:
        st.markdown(
            f"<div class='empty'><b>Brief {esc(selected['name'])} from memory</b>"
            "The generic brief only knows the company name. Memory can name the people, the open promises, and the tactic that won on another deal."
            "<div class='steps'>"
            "<div class='step'><b>1. Ask</b><span>Leave the question, or pick a prompt.</span></div>"
            "<div class='step'><b>2. Compare</b><span>Same question, with Hindsight and without it.</span></div>"
            "<div class='step'><b>3. Show the trace</b><span>Open the tool calls so the recall is visible.</span></div>"
            "</div></div>",
            unsafe_allow_html=True,
        )


elif view == "Log a call":
    st.markdown("<div class='section-label'>Log a touchpoint</div>", unsafe_allow_html=True)
    st.caption(f"This saves on {selected['name']} and retains the same note in Hindsight.")
    open_for_deal = store.commitments(selected["slug"], status="open")
    promise_labels = {
        f"{item['what']} (due {item['due_on']})": item["id"] for item in open_for_deal
    }

    with st.form("log_form", clear_on_submit=True):
        st.markdown("<div class='form-label'>Conversation</div>", unsafe_allow_html=True)
        new_company = st.text_input("New company", placeholder="Leave blank to use the deal in view")
        col_a, col_b = st.columns(2, gap="medium")
        with col_a:
            contact = st.text_input("Contact name and role", placeholder="Priya Shah (VP Operations)")
            happened = st.date_input("When it happened", value=date.today())
            result_label = st.selectbox("Result", ["Advanced", "Still open", "Won", "Lost"])
        with col_b:
            interaction_type = st.selectbox(
                "Interaction type",
                ["Discovery call", "Product demo", "Follow-up email", "Working session", "Commercial call"],
            )
            outcome = st.text_input("Outcome / next step", placeholder="Commercial call with the CFO on 30 September")
            tactic = st.text_input(
                "Tactic you tried",
                placeholder="Sent a two-page security brief 48 hours ahead",
            )
        notes = st.text_area(
            "Notes",
            height=140,
            placeholder="Who said what, which competitor came up, what you promised.",
        )
        st.markdown("<div class='form-label'>Promise</div>", unsafe_allow_html=True)
        p1, p2, p3 = st.columns([2, 1, 1])
        with p1:
            promise_what = st.text_input("Promise", label_visibility="collapsed", placeholder="What you promised")
        with p2:
            promise_who = st.text_input("To whom", label_visibility="collapsed", placeholder="Who")
        with p3:
            promise_due = st.date_input("Due", label_visibility="collapsed", value=date.today())
        kept = st.multiselect("Mark promises kept", list(promise_labels))
        submitted = st.form_submit_button("Save to memory", type="primary")

    if submitted:
        company = new_company.strip() or selected["name"]
        if not company or not notes.strip():
            st.error("Add notes, and a company name.")
        else:
            deal = store.ensure_deal(company)
            result_map = {"Advanced": "advanced", "Still open": "open", "Won": "won", "Lost": "lost"}
            result = result_map[result_label]
            kept_ids = []
            if not new_company.strip():
                kept_ids = [promise_labels[label] for label in kept]
            kept_text = ""
            if kept_ids:
                kept_text = " Promises marked kept: " + "; ".join(kept) + "."
                for commitment_id in kept_ids:
                    store.set_commitment_status(commitment_id, "done")
            if promise_what.strip():
                store.add_commitment(deal["slug"], promise_what, promise_who or "Unspecified", promise_due.isoformat())
            if result == "won":
                store.set_stage(deal["slug"], "Closed won")
            elif result == "lost":
                store.set_stage(deal["slug"], "Closed lost")
            row = store.add_interaction(
                document_id=f"log-{uuid.uuid4().hex}",
                deal_slug=deal["slug"],
                happened_on=happened.isoformat(),
                contact=contact.strip(),
                type_=interaction_type,
                notes=notes.strip() + kept_text,
                outcome=outcome.strip(),
                tactic=tactic.strip(),
                result=result,
            )
            st.session_state["active_slug"] = deal["slug"]
            if memory is None or not st.session_state.get("bank_ready"):
                st.session_state["flash"] = (
                    "warn",
                    "Saved on this machine only. Hindsight is not connected, so the next briefing cannot recall it.",
                )
            else:
                try:
                    with st.spinner("Retaining this interaction in Hindsight…"):
                        memory.retain_interaction(deal, row)
                    store.mark_retained([row["document_id"]])
                    st.session_state["flash"] = ("ok", f"Saved. {deal['name']} can be recalled on the next briefing.")
                except Exception as exc:
                    st.session_state["flash"] = ("warn", f"Saved locally. Hindsight did not retain it: {exc}")
            st.rerun()


elif view == "Timeline":
    deal_promises = store.commitments(selected["slug"])
    if deal_promises:
        st.markdown("<div class='section-label'>Promises</div>", unsafe_allow_html=True)
        cards = []
        for item in deal_promises:
            overdue_item = item["status"] == "open" and is_overdue(item["due_on"])
            badge = "b-over" if overdue_item else "b-done" if item["status"] == "done" else "b-open"
            label = "Overdue" if overdue_item else item["status"].capitalize()
            cards.append(
                f"<div class='promise'><span class='badge {badge}'>{label}</span> "
                f"<strong>{esc(item['what'])}</strong>"
                f"<span class='tl-date'>To {esc(item['who'])} · due {esc(pretty_date(item['due_on']))}</span></div>"
            )
        st.markdown(f"<div class='promise-row'>{''.join(cards)}</div>", unsafe_allow_html=True)
    rows = store.interactions(selected["slug"])
    if not rows:
        st.markdown(
            "<div class='empty'><b>No touchpoints yet</b>Log the first conversation to start this timeline.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<div class='section-label'>Touchpoints</div>", unsafe_allow_html=True)
        result_badge = {
            "won": ("Won", "b-done"),
            "lost": ("Lost", "b-over"),
            "open": ("Open", "b-open"),
            "advanced": ("Advanced", "b-call"),
        }
        items = []
        for item in reversed(rows):
            tactic = f"<div class='tl-callout tactic'><b>Tactic Tried</b>{esc(item['tactic'])}</div>" if item["tactic"] else ""
            outcome = f"<div class='tl-callout outcome'><b>Outcome / Next Steps</b>{esc(item['outcome'])}</div>" if item["outcome"] else ""
            result_label, result_class = result_badge.get(item["result"], ("", ""))
            result_html = f"<span class='badge {result_class}'>{result_label}</span>" if result_label else ""
            items.append(
                "<div class='tl-item'>"
                "<div class='tl-head'>"
                f"<span class='badge {badge_class(item['type'])}'>{esc(item['type'])}</span>"
                f"{result_html}"
                f"<span class='tl-date'>{esc(pretty_date(item['happened_on']))}</span>"
                f"<span class='tl-contact'>{esc(item['contact'])}</span>"
                "</div>"
                f"<p><b>Notes</b><br>{esc(item['notes'])}</p>"
                f"{outcome}{tactic}"
                "</div>"
            )
        st.html("<div class='tl'>" + "".join(items) + "</div>")

elif view == "Memory":
    st.markdown("<div class='section-label'>What Hindsight holds</div>", unsafe_allow_html=True)
    st.caption("Deal facts stay on this deal. Lessons from wins and losses live in the playbook.")
    if not hindsight_on:
        st.markdown(
            "<div class='empty'><b>Hindsight is not connected</b>"
            "Add HINDSIGHT_API_KEY to your .env file. The timeline still works without it. Briefings from memory do not.</div>",
            unsafe_allow_html=True,
        )
    else:
        if st.button("Recall this deal and the playbook", type="primary"):
            with st.spinner("Recalling…"):
                try:
                    st.session_state["memory_view"] = {
                        "slug": selected["slug"],
                        "deal": memory.recall_deal(selected["slug"], "stakeholders objections competitors promises pricing"),
                        "playbook": memory.recall_playbook(
                            "which tactics won or lost on pricing, security reviews, competitors, and missing buyers"
                        ),
                    }
                except Exception as exc:
                    st.error(f"Recall failed: {exc}")
        recalled = st.session_state.get("memory_view")
        if recalled and recalled["slug"] == selected["slug"]:
            deal_col, play_col = st.columns(2, gap="medium")
            with deal_col:
                st.markdown(
                    "<div class='col-label'>This deal<span>Tagged so other accounts cannot leak in</span></div>",
                    unsafe_allow_html=True,
                )
                render_memories(recalled["deal"])
            with play_col:
                st.markdown(
                    "<div class='col-label'>Playbook<span>What already won or lost somewhere else</span></div>",
                    unsafe_allow_html=True,
                )
                render_memories(recalled["playbook"])
        else:
            st.markdown(
                "<div class='empty'><b>Nothing recalled yet</b>Load this deal to see the facts and the lessons side by side.</div>",
                unsafe_allow_html=True,
            )
