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
from datetime import date, datetime, timezone
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from groq import Groq

from dealrecall.agent import BriefError, friendly_service_error, groq_model, parse_sections, run_brief
from dealrecall.call_intelligence import (
    CallAnalysis,
    ExtractionError,
    TranscriptionError,
    analyze_call_transcript,
    build_transcribed_interaction_payload,
    transcribe_audio,
)
from dealrecall.memory import Memory
from dealrecall.memory_timeline import MEMORY_CATEGORIES, DealMemory, get_deal_memories
from dealrecall.security import (
    OPERATION_LOG_INTERACTION,
    OPERATION_MEMORY_DELETE,
    OPERATION_MEMORY_EDIT,
    OPERATION_TRANSCRIBED_CALL_SAVE,
    SecurityManager,
    get_authorized_users,
)
from dealrecall.store import Store, format_inr, is_overdue
from dealrecall.theme import CSS
from dealrecall.what_changed import (
    ChangeItem,
    WhatChangedResult,
    format_short_date,
    get_change_badge,
    get_what_changed,
)

load_dotenv()

ROOT = Path(__file__).resolve().parent
store = Store(ROOT / "data" / "dealrecall.db")
security_manager = SecurityManager(store)

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
    ["Prepare", "Timeline", "Log a call", "Call Intelligence", "Memory"],
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


def render_approval_modal(pending_approval_id: str, fallback_slug: str) -> None:
    session = security_manager.get_session_status(pending_approval_id)
    if not session:
        st.session_state.pop("pending_approval_id", None)
        st.rerun()
        return

    status = session.get("status")
    if status == "expired":
        st.error("Approval expired — change was not saved.")
        if st.button("Return to editor / form", key="ret_expired"):
            st.session_state.pop("pending_approval_id", None)
            st.rerun()
        return
    elif status in ("rejected", "cancelled"):
        st.error(f"Approval was {status} — change was not saved.")
        if st.button("Return to editor / form", key="ret_rejected"):
            st.session_state.pop("pending_approval_id", None)
            st.rerun()
        return

    u_a = session["requesting_user"]
    u_b = session["required_second_user"]
    u_a_done = session["user_a_verified"]
    u_b_done = session["user_b_verified"]

    now_utc = datetime.now(timezone.utc)
    expires_utc = datetime.fromisoformat(session["expires_at"])
    remaining_seconds = max(0, int((expires_utc - now_utc).total_seconds()))

    if remaining_seconds <= 0:
        security_manager.get_session_status(pending_approval_id)
        st.rerun()
        return

    mins = remaining_seconds // 60
    secs = remaining_seconds % 60
    timer_text = f"{mins:02d}:{secs:02d}"

    if not u_a_done and not u_b_done:
        state_text = "Two-person approval required"
    elif u_a_done and u_b_done:
        state_text = "Both users verified — saving change"
    else:
        state_text = "1 of 2 users verified"

    op_type = session.get("operation_type", "")
    op_labels = {
        "memory_edit": "✏️ Edit Deal Memory",
        "memory_delete": "🗑️ Delete Deal Memory",
        "call_log_save": "📞 Log Call / Touchpoint",
        "transcribed_call_save": "🎙️ Save Transcribed Call",
    }
    op_display = op_labels.get(op_type, op_type.replace("_", " ").title())

    st.markdown(
        f"""
        <div class="approval-card">
          <div class="approval-header">
            <div class="approval-title">🔐 Confirm Sensitive Change</div>
            <div class="approval-desc">
              This change requires approval from two authorized users before persisting to deal memory.
            </div>
          </div>
          <div style="margin-bottom: 0.85rem; font-size: 0.9rem;">
            <strong>Operation:</strong> <span style="color: var(--teal-deep); font-weight: 600;">{esc(op_display)}</span> · <strong>Requester:</strong> {esc(u_a)} · <strong>Deal:</strong> {esc(session.get('deal_name') or fallback_slug)}<br>
            <strong>State:</strong> <span style="color: var(--teal-deep); font-weight: 600;">{esc(state_text)}</span>
          </div>
          <div class="approval-status-grid">
            <div class="approval-user-item {'verified' if u_a_done else 'waiting'}">
              <div>
                <div class="approval-user-name">{esc(u_a)}</div>
                <div class="approval-user-role">Requester</div>
              </div>
              <span class="approval-tag {'verified' if u_a_done else 'waiting'}">
                {'✓ Verified' if u_a_done else '○ Waiting'}
              </span>
            </div>
            <div class="approval-user-item {'verified' if u_b_done else 'waiting'}">
              <div>
                <div class="approval-user-name">{esc(u_b)}</div>
                <div class="approval-user-role">Second Approver</div>
              </div>
              <span class="approval-tag {'verified' if u_b_done else 'waiting'}">
                {'✓ Verified' if u_b_done else '○ Waiting'}
              </span>
            </div>
          </div>
          <div style="margin: 0.5rem 0 1rem;">
            <span class="approval-timer {'urgent' if remaining_seconds < 60 else ''}">
              ⏳ Expires in: <strong>{timer_text}</strong>
            </span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    active_default_idx = 0 if not u_a_done else 1
    verif_col1, verif_col2 = st.columns([1, 1], gap="medium")
    with verif_col1:
        verifying_user = st.radio(
            "Verifying as authorized user:",
            [u_a, u_b],
            index=active_default_idx,
            horizontal=True,
            key="approval_verifying_user",
        )
    with verif_col2:
        otp_val = st.text_input(
            "OTP (6 digits)",
            max_chars=6,
            placeholder="090904",
            key="approval_otp_field",
        )

    act_col1, act_col2 = st.columns([1, 1], gap="medium")
    with act_col1:
        verify_submit = st.button("Verify OTP", type="primary", use_container_width=True, key="btn_verify_otp")
    with act_col2:
        cancel_submit = st.button("Cancel Change", use_container_width=True, key="btn_cancel_change")

    st.caption("ℹ️ Test OTP: 090904 (or check data/dev_otp_outbox.json / run 'python -m dealrecall.dev_outbox').")

    if verify_submit:
        cleaned_otp = otp_val.strip()
        if len(cleaned_otp) != 6 or not cleaned_otp.isdigit():
            st.error("Please enter a valid 6-digit numeric OTP.")
        else:
            verif_res = security_manager.verify_user_otp(
                approval_id=pending_approval_id,
                user_name=verifying_user,
                otp=cleaned_otp,
            )
            if not verif_res.ok:
                st.error(verif_res.message)
                if verif_res.status in ("rejected", "expired"):
                    st.session_state.pop("pending_approval_id", None)
                    st.rerun()
            elif verif_res.status == "partially_verified":
                st.success(verif_res.message)
                st.rerun()
            elif verif_res.status == "approved":
                commit_res = security_manager.commit_approved_operation(
                    approval_id=pending_approval_id,
                    memory=memory if (hindsight_on and memory) else None,
                )
                st.session_state.pop("pending_approval_id", None)
                st.session_state.pop("staged_call_form", None)
                st.session_state.pop("ci_transcript", None)
                st.session_state.pop("ci_analysis", None)
                st.session_state.pop("active_memory_detail", None)
                st.session_state.pop("edit_memory_id", None)
                st.session_state.pop("delete_memory_id", None)
                if commit_res.ok:
                    deal_title = commit_res.deal["name"] if commit_res.deal else selected.get("name", fallback_slug)
                    if commit_res.deal:
                        st.session_state["active_slug"] = commit_res.deal["slug"]
                    op_type = session.get("operation_type", "")
                    if op_type == "memory_delete":
                        st.session_state["flash"] = ("ok", f"Memory deleted. Authorized by {u_a} and {u_b}.")
                    elif op_type == "memory_edit":
                        st.session_state["flash"] = ("ok", f"Memory updated. Authorized by {u_a} and {u_b}.")
                    elif commit_res.hindsight_retained:
                        st.session_state["flash"] = ("ok", f"Saved. {deal_title} change approved by {u_a} and {u_b} and updated in Hindsight.")
                    else:
                        st.session_state["flash"] = ("ok", f"Saved. {deal_title} change approved by {u_a} and {u_b} in local store.")
                else:
                    st.session_state["flash"] = ("error", f"Operation failed: {commit_res.message}")
                st.rerun()

    if cancel_submit:
        security_manager.cancel_approval(approval_id=pending_approval_id)
        st.session_state.pop("pending_approval_id", None)
        st.session_state.pop("active_memory_detail", None)
        st.session_state.pop("edit_memory_id", None)
        st.session_state.pop("delete_memory_id", None)
        st.session_state["flash"] = ("warn", "Change was cancelled and NOT saved.")
        st.rerun()


def render_memory_detail_card(active_mem, selected: dict, key_prefix: str = "") -> None:
    """Render memory details, edit form, or delete confirmation card."""
    is_editing = st.session_state.get("edit_memory_id") == active_mem.id
    is_deleting = st.session_state.get("delete_memory_id") == active_mem.id

    if is_editing:
        # Edit Memory Form
        st.markdown("<div class='mem-detail-card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='section-label'>✏️ Edit Memory · {esc(active_mem.title)}</div>", unsafe_allow_html=True)
        st.caption("Editing this memory requires Two-Person OTP authorization from Kovid and Vedanth before changes are saved.")

        with st.form(f"{key_prefix}edit_memory_form"):
            ef_c1, ef_c2 = st.columns(2, gap="medium")
            with ef_c1:
                edit_contact = st.text_input("Contact / Stakeholder", value=active_mem.contact)
                edit_date = st.text_input("Date", value=active_mem.date)
            with ef_c2:
                edit_type = st.text_input("Interaction Type / Category", value=active_mem.type)
                edit_outcome = st.text_input("Outcome / Next Milestone", value=active_mem.outcome)

            edit_content = st.text_area("Memory Content / Notes", value=active_mem.content, height=120)
            edit_tactic = st.text_input("Tactic Tried (optional)", value=active_mem.tactic)

            btn_c1, btn_c2 = st.columns([1.5, 1], gap="medium")
            with btn_c1:
                save_edit_btn = st.form_submit_button("🔒 Save Changes (Requires Two-Person OTP)", type="primary", use_container_width=True)
            with btn_c2:
                cancel_edit_btn = st.form_submit_button("Cancel", use_container_width=True)

        if save_edit_btn:
            payload = {
                "entity_type": active_mem.entity_type,
                "document_id": active_mem.document_id,
                "commitment_id": active_mem.commitment_id,
                "deal_slug": selected["slug"],
                "deal_name": selected["name"],
                "notes": edit_content.strip(),
                "contact": edit_contact.strip(),
                "happened_on": edit_date.strip(),
                "type": edit_type.strip(),
                "outcome": edit_outcome.strip(),
                "tactic": edit_tactic.strip(),
                "what": edit_content.strip(),
                "who": edit_contact.strip(),
                "due_on": edit_date.strip(),
            }
            u_a, _ = get_authorized_users()
            appr_req = security_manager.create_approval_request(
                deal_slug=selected["slug"],
                deal_name=selected["name"],
                operation_type=OPERATION_MEMORY_EDIT,
                requesting_user=u_a,
                payload=payload,
            )
            st.session_state["pending_approval_id"] = appr_req["id"]
            st.rerun()

        if cancel_edit_btn:
            st.session_state.pop("edit_memory_id", None)
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    elif is_deleting:
        # Delete Memory Confirmation
        st.markdown("<div class='mem-detail-card' style='border-color: #FECACA; background: #FFF1F2;'>", unsafe_allow_html=True)
        st.markdown(f"<div class='section-label' style='color: var(--red);'>⚠️ Confirm Memory Deletion</div>", unsafe_allow_html=True)
        st.markdown(
            f"Are you sure you want to delete this memory? <b>This will permanently remove it from DealRecall local store and Hindsight.</b><br>"
            f"This action is protected and requires Two-Person OTP authorization from Kovid and Vedanth.",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='tl-callout' style='margin: 0.75rem 0; background: #FFFFFF;'>"
            f"<b>Memory:</b> {esc(active_mem.title)}<br>"
            f"<b>Date:</b> {esc(active_mem.formatted_date)} · <b>Source:</b> {esc(active_mem.source)}<br>"
            f"<b>Statement:</b> {esc(active_mem.statement)}"
            f"</div>",
            unsafe_allow_html=True,
        )
        del_c1, del_c2 = st.columns([1.5, 1], gap="medium")
        with del_c1:
            if st.button("🔒 Confirm & Request Authorization", type="primary", use_container_width=True, key=f"{key_prefix}btn_confirm_del_req"):
                payload = {
                    "entity_type": active_mem.entity_type,
                    "document_id": active_mem.document_id,
                    "commitment_id": active_mem.commitment_id,
                    "deal_slug": selected["slug"],
                    "deal_name": selected["name"],
                    "notes": active_mem.content,
                    "contact": active_mem.contact,
                }
                u_a, _ = get_authorized_users()
                appr_req = security_manager.create_approval_request(
                    deal_slug=selected["slug"],
                    deal_name=selected["name"],
                    operation_type=OPERATION_MEMORY_DELETE,
                    requesting_user=u_a,
                    payload=payload,
                )
                st.session_state["pending_approval_id"] = appr_req["id"]
                st.rerun()
        with del_c2:
            if st.button("Cancel", use_container_width=True, key=f"{key_prefix}btn_cancel_del_req"):
                st.session_state.pop("delete_memory_id", None)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    else:
        # Memory Details Card
        st.markdown("<div class='mem-detail-card'>", unsafe_allow_html=True)
        st.markdown(
            f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom: 0.75rem;'>"
            f"<div class='section-label' style='margin:0;'>MEMORY DETAILS</div>"
            f"<span class='mem-storage-badge {'hindsight' if active_mem.retained_in_hindsight else 'local'}'>{esc(active_mem.storage)}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='font-size: 1.05rem; font-weight: 700; color: var(--ink); margin-bottom: 0.35rem;'>{esc(active_mem.title)}</div>"
            f"<div style='font-size: 0.82rem; color: var(--ink-soft); margin-bottom: 0.85rem;'>"
            f"<b>Date:</b> {esc(active_mem.formatted_date)} · "
            f"<b>Category:</b> {esc(active_mem.category)} · "
            f"<b>Source:</b> {esc(active_mem.source)} · "
            f"<b>Related Deal:</b> {esc(active_mem.deal_name)}"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='background: var(--paper); border: 1px solid var(--line); border-radius: 8px; padding: 0.85rem; font-size: 0.92rem; line-height: 1.6; white-space: pre-wrap; margin-bottom: 0.85rem;'>"
            f"{esc(active_mem.content)}"
            f"</div>",
            unsafe_allow_html=True,
        )
        if active_mem.outcome:
            st.markdown(f"<div class='tl-callout outcome'><b>Outcome / Next Milestone</b>{esc(active_mem.outcome)}</div>", unsafe_allow_html=True)
        if active_mem.tactic:
            st.markdown(f"<div class='tl-callout tactic'><b>Tactic Tried</b>{esc(active_mem.tactic)}</div>", unsafe_allow_html=True)

        act_c1, act_c2, act_c3 = st.columns([1, 1, 1], gap="medium")
        with act_c1:
            if st.button("✏️ Edit Memory", use_container_width=True, key=f"{key_prefix}btn_open_edit_mem"):
                st.session_state["edit_memory_id"] = active_mem.id
                st.session_state.pop("delete_memory_id", None)
                st.rerun()
        with act_c2:
            if st.button("🗑️ Delete Memory", use_container_width=True, key=f"{key_prefix}btn_open_del_mem"):
                st.session_state["delete_memory_id"] = active_mem.id
                st.session_state.pop("edit_memory_id", None)
                st.rerun()
        with act_c3:
            if st.button("✖️ Close Details", use_container_width=True, key=f"{key_prefix}btn_close_mem_detail"):
                st.session_state.pop("active_memory_detail", None)
                st.session_state.pop("edit_memory_id", None)
                st.session_state.pop("delete_memory_id", None)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# Global Two-Person OTP Approval Intercept:
# Whenever a sensitive operation (call log, speech-to-text, memory edit, memory delete)
# has been requested, intercept and present the approval modal immediately across all views.
pending_approval_id = st.session_state.get("pending_approval_id")
if pending_approval_id:
    render_approval_modal(pending_approval_id, selected["slug"])
    st.stop()


if view == "Prepare":
    with st.container(key="panel_prepare"):
        # ----------------------------------------------------
        # FEATURE 2: ⚡ WHAT CHANGED?
        # ----------------------------------------------------
        wc_res = get_what_changed(
            store=store,
            deal_slug=selected["slug"],
            memory=memory if (hindsight_on and memory) else None,
            groq_client=client,
        )

        st.markdown(
            f"<div class='wc-container'>"
            f"  <div class='wc-header'>"
            f"    <div class='wc-title'>⚡ WHAT CHANGED?</div>"
            f"    <div class='wc-time-badge'>{esc(wc_res.time_label)}</div>"
            f"  </div>",
            unsafe_allow_html=True,
        )

        # Check if Memory Details should be displayed right in Prepare
        active_mem_id = st.session_state.get("active_memory_detail")
        if active_mem_id:
            all_deal_mems = get_deal_memories(store, selected["slug"])
            active_mem = next((m for m in all_deal_mems if m.id == active_mem_id), None)
            if active_mem:
                render_memory_detail_card(active_mem, selected, key_prefix="prep_")

        if not wc_res.has_history:
            st.markdown(
                f"<div class='empty' style='margin: 0.5rem 0; padding: 1rem 1.25rem;'>"
                f"<b>{esc(wc_res.time_label)}</b>"
                f"{esc(wc_res.message)}"
                f"</div>",
                unsafe_allow_html=True,
            )
        elif not wc_res.changes:
            st.markdown(
                f"<div class='empty' style='margin: 0.5rem 0; padding: 1rem 1.25rem;'>"
                f"<b>✓ No meaningful changes</b>"
                f"{esc(wc_res.message)}"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            if not hindsight_on or not memory:
                st.caption("ℹ️ Historical memory unavailable. Showing changes from local DealRecall records only.")

            total_changes = len(wc_res.changes)
            show_all_key = f"wc_show_all_{selected['slug']}"
            show_all = st.session_state.get(show_all_key, False)
            displayed_changes = wc_res.changes if (show_all or total_changes <= 3) else wc_res.changes[:3]

            for idx, ch in enumerate(displayed_changes):
                type_class = (
                    "c-new" if ch.type == "NEW"
                    else "c-still-open" if ch.type in ("STILL OPEN", "STILL_OPEN", "OPEN")
                    else "c-resolved" if ch.type == "RESOLVED"
                    else "c-changed" if ch.type == "CHANGED"
                    else "c-commitment"
                )
                b_label, b_cls = get_change_badge(ch.type)

                st.markdown(
                    f"<div class='wc-card {type_class}'>"
                    f"  <div class='wc-card-head'>"
                    f"    <span class='badge {b_cls}'>{esc(b_label)}</span>"
                    f"    <span class='wc-card-title'>{esc(ch.title)}</span>"
                    f"  </div>"
                    f"  <div class='wc-card-desc'>{esc(ch.description)}</div>"
                    f"  <div class='wc-card-foot'>"
                    f"    <span>Source: <b>{esc(ch.source)}</b> · {esc(format_short_date(ch.date))}</span>"
                    f"    <span class='mem-storage-badge {'hindsight' if 'hindsight' in ch.storage.lower() else 'local'}'>{esc(ch.storage)}</span>"
                    f"  </div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                if ch.memory_id:
                    vm_c1, _ = st.columns([1.5, 4])
                    with vm_c1:
                        if st.button("View Memory", key=f"wc_vm_{idx}_{ch.memory_id}", use_container_width=True):
                            st.session_state["active_memory_detail"] = ch.memory_id
                            st.session_state.pop("edit_memory_id", None)
                            st.session_state.pop("delete_memory_id", None)
                            st.rerun()

            if total_changes > 3:
                c_tog1, _ = st.columns([1.8, 3])
                with c_tog1:
                    if show_all:
                        if st.button("Show fewer changes", key=f"wc_btn_fewer_{selected['slug']}"):
                            st.session_state[show_all_key] = False
                            st.rerun()
                    else:
                        if st.button(f"Show all {total_changes} changes", key=f"wc_btn_all_{selected['slug']}"):
                            st.session_state[show_all_key] = True
                            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<div style='height: 0.8rem;'></div>", unsafe_allow_html=True)
        if "user_query" not in st.session_state:
            st.session_state["user_query"] = ""
        st.text_area(
            "Ask a custom question",
            placeholder="Ask anything about this deal...",
            key="user_query",
            label_visibility="collapsed"
        )
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
    pending_approval_id = st.session_state.get("pending_approval_id")

    if pending_approval_id:
        render_approval_modal(pending_approval_id, selected["slug"])
    else:
        st.markdown("<div class='section-label'>Log a touchpoint</div>", unsafe_allow_html=True)
        st.caption(f"This saves on {selected['name']} and retains the same note in Hindsight after two-person approval.")
        open_for_deal = store.commitments(selected["slug"], status="open")
        promise_labels = {
            f"{item['what']} (due {item['due_on']})": item["id"] for item in open_for_deal
        }

        staged = st.session_state.get("staged_call_form", {})
        default_company = staged.get("company", "")
        default_contact = staged.get("contact", "")
        default_notes = staged.get("notes", "")
        default_outcome = staged.get("outcome", "")
        default_tactic = staged.get("tactic", "")
        default_p_what = staged.get("promise_what", "")
        default_p_who = staged.get("promise_who", "")

        with st.form("log_form", clear_on_submit=False):
            st.markdown("<div class='form-label'>Conversation</div>", unsafe_allow_html=True)
            new_company = st.text_input("New company", value=default_company, placeholder="Leave blank to use the deal in view")
            col_a, col_b = st.columns(2, gap="medium")
            with col_a:
                contact = st.text_input("Contact name and role", value=default_contact, placeholder="Priya Shah (VP Operations)")
                happened = st.date_input("When it happened", value=date.today())
                result_label = st.selectbox("Result", ["Advanced", "Still open", "Won", "Lost"])
            with col_b:
                interaction_type = st.selectbox(
                    "Interaction type",
                    ["Discovery call", "Product demo", "Follow-up email", "Working session", "Commercial call"],
                )
                outcome = st.text_input("Outcome / next step", value=default_outcome, placeholder="Commercial call with the CFO on 30 September")
                tactic = st.text_input(
                    "Tactic you tried",
                    value=default_tactic,
                    placeholder="Sent a two-page security brief 48 hours ahead",
                )
            notes = st.text_area(
                "Notes",
                value=default_notes,
                height=140,
                placeholder="Who said what, which competitor came up, what you promised.",
            )
            st.markdown("<div class='form-label'>Promise</div>", unsafe_allow_html=True)
            p1, p2, p3 = st.columns([2, 1, 1])
            with p1:
                promise_what = st.text_input("Promise", value=default_p_what, label_visibility="collapsed", placeholder="What you promised")
            with p2:
                promise_who = st.text_input("To whom", value=default_p_who, label_visibility="collapsed", placeholder="Who")
            with p3:
                promise_due = st.date_input("Due", label_visibility="collapsed", value=date.today())
            kept = st.multiselect("Mark promises kept", list(promise_labels))
            submitted = st.form_submit_button("Save to memory", type="primary")

        if submitted:
            company = new_company.strip() or selected["name"]
            if not company or not notes.strip():
                st.error("Add notes, and a company name.")
            else:
                result_map = {"Advanced": "advanced", "Still open": "open", "Won": "won", "Lost": "lost"}
                result = result_map[result_label]
                kept_ids = []
                if not new_company.strip():
                    kept_ids = [promise_labels[label] for label in kept]

                user_a, _ = get_authorized_users()
                payload = {
                    "company": company,
                    "contact": contact.strip(),
                    "happened": happened.isoformat(),
                    "result": result,
                    "interaction_type": interaction_type,
                    "notes": notes.strip(),
                    "outcome": outcome.strip(),
                    "tactic": tactic.strip(),
                    "kept_ids": kept_ids,
                    "kept_labels": kept,
                    "promise_what": promise_what.strip(),
                    "promise_who": promise_who.strip(),
                    "promise_due": promise_due.isoformat() if promise_due else "",
                    "document_id": f"log-{uuid.uuid4().hex}",
                }
                st.session_state["staged_call_form"] = payload
                appr_req = security_manager.create_approval_request(
                    deal_slug=selected["slug"],
                    deal_name=company,
                    operation_type=OPERATION_LOG_INTERACTION,
                    requesting_user=user_a,
                    payload=payload,
                )
                st.session_state["pending_approval_id"] = appr_req["id"]
                st.rerun()


elif view == "Call Intelligence":
    st.markdown("<div class='section-label'>Call Intelligence</div>", unsafe_allow_html=True)
    st.caption(f"Transcribe and analyze phone recordings for {selected['name']}, review insights, and approve to memory.")

    pending_id = st.session_state.get("pending_approval_id")
    if pending_id:
        render_approval_modal(pending_id, selected["slug"])
    else:
        # Step 1: Audio Upload or Demo Recording
        st.markdown("<div class='form-label'>1. Audio Recording</div>", unsafe_allow_html=True)
        col_up1, col_up2 = st.columns([2.5, 1], gap="medium")
        with col_up1:
            uploaded_audio = st.file_uploader(
                "Upload Phone Call Recording (.mp3, .wav, .m4a, .mp4, .webm)",
                type=["mp3", "wav", "m4a", "mp4", "webm"],
                key="ci_uploader",
                label_visibility="collapsed",
            )
        with col_up2:
            st.markdown("<div style='height: 2px;'></div>", unsafe_allow_html=True)
            use_sample = st.button("📂 Load Demo Recording", use_container_width=True, help="Loads Northwind Security review recording")

        if use_sample:
            sample_path = ROOT / "data" / "sample_call.wav"
            if sample_path.exists():
                st.session_state["ci_active_audio_bytes"] = sample_path.read_bytes()
                st.session_state["ci_active_filename"] = "northwind_security_call.wav"
                st.session_state["ci_active_filesize"] = len(st.session_state["ci_active_audio_bytes"])
                st.session_state.pop("ci_transcript", None)
                st.session_state.pop("ci_analysis", None)
                st.rerun()

        if uploaded_audio is not None:
            if st.session_state.get("ci_active_filename") != uploaded_audio.name:
                st.session_state["ci_active_audio_bytes"] = uploaded_audio.getvalue()
                st.session_state["ci_active_filename"] = uploaded_audio.name
                st.session_state["ci_active_filesize"] = uploaded_audio.size
                st.session_state.pop("ci_transcript", None)
                st.session_state.pop("ci_analysis", None)

        active_bytes = st.session_state.get("ci_active_audio_bytes")
        active_filename = st.session_state.get("ci_active_filename")

        if active_bytes and active_filename:
            f_size_kb = len(active_bytes) / 1024
            st.markdown(
                f"<div class='tl-callout' style='margin-bottom: 0.8rem;'>"
                f"<b>Selected Recording:</b> {esc(active_filename)} · "
                f"<b>Size:</b> {f_size_kb:.1f} KB · "
                f"<b>Format:</b> {Path(active_filename).suffix.upper()} · "
                f"<b>Deal:</b> {esc(selected['name'])}"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.audio(active_bytes)

            col_tr1, col_tr2 = st.columns([1.5, 1], gap="medium")
            with col_tr1:
                transcribe_btn = st.button("🎙️ Transcribe Call", type="primary", use_container_width=True, key="btn_transcribe")
            with col_tr2:
                if st.button("Clear Recording", use_container_width=True):
                    st.session_state.pop("ci_active_audio_bytes", None)
                    st.session_state.pop("ci_active_filename", None)
                    st.session_state.pop("ci_active_filesize", None)
                    st.session_state.pop("ci_transcript", None)
                    st.session_state.pop("ci_analysis", None)
                    st.rerun()

            if transcribe_btn:
                with st.spinner("Transcribing call with Groq Whisper... Please wait."):
                    try:
                        t_res = transcribe_audio(active_bytes, filename=active_filename, groq_client=client)
                        st.session_state["ci_transcript"] = t_res.to_dict()
                        st.session_state.pop("ci_analysis", None)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Transcription failed: {exc}")

        # Step 2: Transcript Display & AI Analysis Trigger
        transcript_data = st.session_state.get("ci_transcript")
        if transcript_data:
            st.markdown("<div class='form-label' style='margin-top: 1.5rem;'>2. Transcript</div>", unsafe_allow_html=True)
            edited_transcript = st.text_area(
                "Full Transcript",
                value=transcript_data.get("text", ""),
                height=150,
                key="ci_transcript_text_display",
                label_visibility="collapsed",
            )
            col_t1, col_t2, col_t3 = st.columns(3)
            with col_t1:
                st.caption(f"**Duration:** {transcript_data.get('duration', 0):.1f}s")
            with col_t2:
                st.caption(f"**Language:** {transcript_data.get('language', 'en').upper()}")
            with col_t3:
                st.caption(f"**Provider:** {transcript_data.get('provider', 'Groq Whisper')}")

            col_an1, col_an2 = st.columns([1.5, 1], gap="medium")
            with col_an1:
                analyze_btn = st.button("✨ Analyze Call with AI", type="primary", use_container_width=True, key="btn_analyze_call")
            with col_an2:
                if st.button("Re-transcribe", use_container_width=True):
                    st.session_state.pop("ci_transcript", None)
                    st.session_state.pop("ci_analysis", None)
                    st.rerun()

            if analyze_btn:
                with st.spinner("Extracting structured sales intelligence with Groq..."):
                    try:
                        analysis_res = analyze_call_transcript(edited_transcript, deal_context=selected, groq_client=client)
                        st.session_state["ci_analysis"] = analysis_res.to_dict()
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Call analysis failed: {exc}")

        # Step 3: Human Review & Edit (Section 9)
        analysis_data = st.session_state.get("ci_analysis")
        if analysis_data:
            st.markdown("<div class='form-label' style='margin-top: 1.5rem;'>3. Call Analysis Review</div>", unsafe_allow_html=True)
            st.caption("Review and edit the extracted sales intelligence before requesting two-person authorization. Nothing is committed until approved.")

            with st.form("ci_review_form"):
                cr1, cr2 = st.columns(2, gap="medium")
                with cr1:
                    rev_contact = st.text_input("Contact", value=analysis_data.get("contact") or "Raj Malhotra")
                    rev_interaction_type = st.selectbox(
                        "Interaction type",
                        ["Working session", "Commercial call", "Discovery call", "Product demo", "Follow-up email"],
                        index=0,
                    )
                with cr2:
                    rev_role = st.text_input("Role / Title", value=analysis_data.get("role") or "VP Security")
                    rev_outcome = st.text_input("Outcome / Next Milestone", value=analysis_data.get("outcome") or "Commercial review scheduled")

                col_sec, col_req = st.columns(2, gap="medium")
                with col_sec:
                    sec_list = analysis_data.get("security_requirements") or []
                    rev_security = st.text_area("Security & Compliance Requirements", value="\n".join(sec_list), height=90)
                    obj_list = analysis_data.get("objections") or []
                    rev_objections = st.text_area("Customer Objections", value="\n".join(obj_list), height=80)
                with col_req:
                    req_list = analysis_data.get("requirements") or []
                    rev_reqs = st.text_area("Customer Requirements", value="\n".join(req_list), height=90)
                    comp_list = analysis_data.get("competitors") or []
                    price_list = analysis_data.get("pricing") or []
                    rev_competitors = st.text_input("Competitors", value=", ".join(comp_list))
                    rev_pricing = st.text_input("Pricing / Commercials", value=", ".join(price_list))

                st.markdown("<div class='form-label' style='font-size: 0.82rem;'>Commitment / Promise</div>", unsafe_allow_html=True)
                promises = analysis_data.get("promises") or []
                p_what_default = promises[0].get("what", "") if promises else "Send signed security addendum"
                p_who_default = promises[0].get("who", "") if promises else rev_contact
                p_due_default = promises[0].get("due_on", "") if promises else "2026-10-05"

                cp1, cp2, cp3 = st.columns([2, 1, 1])
                with cp1:
                    rev_p_what = st.text_input("Promise", value=p_what_default, label_visibility="collapsed")
                with cp2:
                    rev_p_who = st.text_input("To whom", value=p_who_default, label_visibility="collapsed")
                with cp3:
                    rev_p_due = st.date_input("Due date", value=date.today(), label_visibility="collapsed")

                rev_notes = st.text_area("Notes Summary", value=analysis_data.get("notes") or "", height=90)
                rev_follow_up = st.text_input("Suggested Follow-up", value=analysis_data.get("follow_up") or "")

                appr_save_btn = st.form_submit_button("🔒 Approve & Save to Memory", type="primary")

            if appr_save_btn:
                updated_analysis = {
                    "contact": rev_contact.strip(),
                    "role": rev_role.strip(),
                    "interaction_type": rev_interaction_type,
                    "outcome": rev_outcome.strip(),
                    "security_requirements": [s.strip() for s in rev_security.split("\n") if s.strip()],
                    "objections": [s.strip() for s in rev_objections.split("\n") if s.strip()],
                    "requirements": [s.strip() for s in rev_reqs.split("\n") if s.strip()],
                    "competitors": [s.strip() for s in rev_competitors.split(",") if s.strip()],
                    "pricing": [s.strip() for s in rev_pricing.split(",") if s.strip()],
                    "promises": [{"what": rev_p_what.strip(), "who": rev_p_who.strip(), "due_on": rev_p_due.isoformat()}] if rev_p_what.strip() else [],
                    "notes": rev_notes.strip(),
                    "follow_up": rev_follow_up.strip(),
                }
                payload = build_transcribed_interaction_payload(
                    deal_slug=selected["slug"],
                    deal_name=selected["name"],
                    analysis=updated_analysis,
                    happened_date=date.today().isoformat(),
                )
                payload["document_id"] = f"call-{uuid.uuid4().hex}"

                user_a, _ = get_authorized_users()
                appr_req = security_manager.create_approval_request(
                    deal_slug=selected["slug"],
                    deal_name=selected["name"],
                    operation_type=OPERATION_TRANSCRIBED_CALL_SAVE,
                    requesting_user=user_a,
                    payload=payload,
                )
                st.session_state["pending_approval_id"] = appr_req["id"]
                st.rerun()


elif view == "Timeline":
    tl_mode = st.segmented_control(
        "Timeline Display Mode",
        ["🧠 Memory Timeline", "📜 CRM Touchpoints & Promises"],
        default="🧠 Memory Timeline",
        key="tl_mode_toggle",
        label_visibility="collapsed",
    )

    if tl_mode == "🧠 Memory Timeline":
        st.markdown(
            f"<div class='section-label' style='display:flex; justify-content:space-between; align-items:center;'>"
            f"<span>🧠 Memory Timeline</span>"
            f"<span style='font-size: 0.8rem; font-weight: 500; color: var(--ink-soft);'>Deal: {esc(selected['name'])}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.caption("Everything DealRecall remembers about this deal · Sourced from transcribed calls, interactions, and Hindsight memory")

        # Search bar and Category filter pills
        scol1, scol2 = st.columns([1.3, 2], gap="medium")
        with scol1:
            search_query = st.text_input(
                "Search memories...",
                placeholder="🔍 Search keywords, stakeholders, requirements, objections...",
                key="mt_search_input",
                label_visibility="collapsed",
            )
        with scol2:
            cat_filter = st.pills(
                "Filter by topic:",
                MEMORY_CATEGORIES,
                default="All",
                key="mt_category_pills",
                label_visibility="collapsed",
            ) or "All"

        # Active Modal / Detail View Handling
        active_mem_id = st.session_state.get("active_memory_detail")
        all_deal_mems = get_deal_memories(store, selected["slug"])
        active_mem = next((m for m in all_deal_mems if m.id == active_mem_id), None) if active_mem_id else None

        if active_mem:
            render_memory_detail_card(active_mem, selected, key_prefix="")

        # Retrieve and display memories matching search and category filter
        filtered_memories = get_deal_memories(
            store,
            selected["slug"],
            search_query=search_query,
            category_filter=cat_filter,
        )

        if not filtered_memories:
            st.markdown(
                f"<div class='empty'><b>No memories found</b>"
                f"No deal memories match your current search or category filter.</div>",
                unsafe_allow_html=True,
            )
        else:
            for mem in filtered_memories:
                storage_cls = "hindsight" if mem.retained_in_hindsight else "local"
                st.markdown(
                    f"<div class='mem-card'>"
                    f"  <div class='mem-head'>"
                    f"    <div class='mem-date'>{esc(mem.formatted_date)}</div>"
                    f"    <span class='badge {badge_class(mem.category)}'>{esc(mem.category)}</span>"
                    f"  </div>"
                    f"  <div class='mem-title'>{esc(mem.title)}</div>"
                    f"  <div class='mem-statement'>{esc(mem.statement)}</div>"
                    f"  <div class='mem-foot'>"
                    f"    <div class='mem-badges'>"
                    f"      <span class='mem-source-badge'>Source: {esc(mem.source)}</span>"
                    f"      <span class='mem-storage-badge {storage_cls}'>{esc(mem.storage)}</span>"
                    f"    </div>"
                    f"  </div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                col_btn_view, _ = st.columns([1.5, 4])
                with col_btn_view:
                    if st.button("View Memory", key=f"btn_view_{mem.id}", use_container_width=True):
                        st.session_state["active_memory_detail"] = mem.id
                        st.session_state.pop("edit_memory_id", None)
                        st.session_state.pop("delete_memory_id", None)
                        st.rerun()

    else:
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

# Security Audit Trail (Section 10)
audit_entries = store.audit_logs(limit=10)
if audit_entries:
    with st.expander("🛡️ Security Audit Trail (Two-Person Approvals)", expanded=False):
        st.caption("Immutable ledger of all sensitive change approval requests and outcomes.")
        for item in audit_entries:
            st_class = item["status"].lower().replace(" ", "-")
            appr_by = item.get("approving_user") or "None"
            ts_display = item["timestamp"][:19].replace("T", " ")
            details_line = f"<div style='font-size: 0.78rem; color: var(--ink-muted); margin-top: 0.2rem;'>{esc(item['details'])}</div>" if item.get("details") else ""
            st.markdown(
                f"""
                <div class="audit-card">
                  <div class="audit-head">
                    <span class="audit-deal">{esc(item.get('deal_name') or item.get('deal_slug') or 'CRM')}</span>
                    <span class="badge status-{st_class}">{esc(item['status'])}</span>
                  </div>
                  <div class="audit-meta">
                    <b>Operation:</b> {esc(item['operation'])} ·
                    <b>Requested by:</b> {esc(item['requesting_user'])} ·
                    <b>Approved by:</b> {esc(appr_by)} ·
                    <b>Time:</b> {esc(ts_display)} UTC
                    {details_line}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

