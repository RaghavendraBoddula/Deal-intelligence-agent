import sys
import os

# ─────────────────────────────────────────────────────────────
# AUTO-LAUNCHER: allows `python app.py` to work by
# automatically re-launching through Streamlit's runtime.
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        from streamlit import runtime
        if not runtime.exists():
            from streamlit.web import cli as stcli
            sys.argv = ["streamlit", "run", os.path.abspath(__file__)]
            sys.exit(stcli.main())
    except ImportError:
        pass

import re
import html
import requests
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

# Requires streamlit >= 1.40  (container keys + st.pills)

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY")
HINDSIGHT_BASE_URL = os.getenv("HINDSIGHT_BASE_URL", "https://ui.hindsight.vectorize.io/api")

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

st.set_page_config(
    page_title="DealRecall | Sales Copilot",
    page_icon="🤝",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────
# DESIGN SYSTEM
# Ink navy + paper white, one signal colour (teal) and one
# "attention" colour (amber) reserved for open commitments.
# ─────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

:root {
  --ink: #12243A;
  --ink-soft: #4A5B70;
  --paper: #F5F7FA;
  --card: #FFFFFF;
  --line: #E1E7EF;
  --teal: #0E8A8C;
  --teal-soft: #E3F4F4;
  --amber: #B7791F;
  --amber-soft: #FCF3DF;
  --radius: 16px;
}

html, body, .stApp, [class*="css"] { font-family: 'Plus Jakarta Sans', system-ui, sans-serif; }
.stApp { background: var(--paper); color: var(--ink); }
.stApp p, .stApp li, .stApp label, .stApp span, .stApp div[data-testid="stMarkdownContainer"] { color: var(--ink); }
h1, h2, h3 { font-family: 'Fraunces', Georgia, serif !important; color: var(--ink) !important; letter-spacing: -0.01em; }

/* Chrome */
#MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.6rem; padding-bottom: 4rem; max-width: 1180px; }

/* Hero */
.hero {
  background: linear-gradient(135deg, #12243A 0%, #17466A 60%, #0E8A8C 130%);
  border-radius: 24px; padding: 2.2rem 2.4rem; margin-bottom: 1.4rem;
  display: flex; gap: 2rem; justify-content: space-between; align-items: flex-end; flex-wrap: wrap;
}
.hero h1 { color: #fff !important; font-size: 2.5rem; margin: 0 0 .35rem 0; line-height: 1.1; }
.hero p { color: #C9D8E8 !important; margin: 0; max-width: 34rem; font-size: 1.02rem; line-height: 1.55; }
.hero-stats { display: flex; gap: .8rem; flex-wrap: wrap; }
.stat {
  background: rgba(255,255,255,.10); border: 1px solid rgba(255,255,255,.18);
  border-radius: 14px; padding: .8rem 1.1rem; min-width: 108px; backdrop-filter: blur(4px);
}
.stat b { display: block; font-family: 'Fraunces', serif; font-size: 1.7rem; color: #fff; line-height: 1.1; }
.stat span { color: #B9CCE0 !important; font-size: .8rem; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: .4rem; border-bottom: 1px solid var(--line); overflow-x: auto; }
.stTabs [data-baseweb="tab"] {
  height: 46px; padding: 0 1.1rem; border-radius: 12px 12px 0 0; font-weight: 600; color: var(--ink-soft);
  background: transparent; white-space: nowrap;
}
.stTabs [aria-selected="true"] { color: var(--teal) !important; background: var(--teal-soft); }
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--teal) !important; height: 3px; }
.stTabs [data-baseweb="tab-border"] { display: none; }

/* Inputs */
.stTextInput input, .stTextArea textarea, div[data-baseweb="select"] > div {
  background: var(--card) !important; border: 1.5px solid var(--line) !important;
  border-radius: 12px !important; color: var(--ink) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus { border-color: var(--teal) !important; box-shadow: 0 0 0 3px var(--teal-soft) !important; }
.stTextInput label, .stTextArea label, .stSelectbox label { font-weight: 600 !important; color: var(--ink) !important; }

/* Buttons */
.stButton > button, .stFormSubmitButton > button {
  border-radius: 12px; font-weight: 600; padding: .65rem 1.4rem; border: 1.5px solid var(--line);
  transition: transform .12s ease, box-shadow .12s ease;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"], .stFormSubmitButton > button {
  background: var(--teal); color: #fff !important; border-color: var(--teal);
}
.stButton > button:hover, .stFormSubmitButton > button:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(14,138,140,.25); }
.stButton > button:focus-visible, .stFormSubmitButton > button:focus-visible { outline: 3px solid var(--teal-soft); }

/* Panels */
[class*="st-key-panel"] {
  background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 1.4rem 1.5rem;
  box-shadow: 0 1px 2px rgba(18,36,58,.04);
}
[class*="st-key-sec_"] {
  background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 1.1rem 1.3rem; height: 100%;
}
[class*="st-key-sec_1"] { background: var(--teal-soft); border-color: #BFE4E4; }
[class*="st-key-sec_5"] { background: var(--amber-soft); border-color: #F0DDAE; }
.sec-title { font-family: 'Fraunces', serif; font-weight: 700; font-size: 1.15rem; margin: 0 0 .5rem 0; color: var(--ink); }
[class*="st-key-sec_"] li, [class*="st-key-sec_"] p { line-height: 1.6; font-size: .96rem; }

/* Form */
[data-testid="stForm"] { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 1.4rem 1.5rem; }

/* Memory chips */
.mem { background: var(--card); border: 1px solid var(--line); border-left: 4px solid var(--teal);
  border-radius: 10px; padding: .7rem .9rem; margin-bottom: .55rem; font-size: .9rem; line-height: 1.5; color: var(--ink); }
.mem small { color: var(--ink-soft); font-weight: 700; }

/* Empty state */
.empty { text-align: center; padding: 2.6rem 1rem; color: var(--ink-soft); background: var(--card);
  border: 1.5px dashed var(--line); border-radius: var(--radius); }
.empty b { display: block; color: var(--ink); font-family: 'Fraunces', serif; font-size: 1.2rem; margin-bottom: .3rem; }

/* Timeline */
.tl { position: relative; margin: .5rem 0 0 .6rem; padding-left: 1.6rem; border-left: 2px solid var(--line); }
.tl-item { position: relative; background: var(--card); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 1rem 1.2rem; margin-bottom: 1rem; }
.tl-item::before { content: ""; position: absolute; left: -2.28rem; top: 1.25rem; width: 14px; height: 14px;
  border-radius: 50%; background: var(--teal); border: 3px solid var(--paper); box-shadow: 0 0 0 2px var(--teal); }
.tl-head { display: flex; gap: .6rem; align-items: center; flex-wrap: wrap; margin-bottom: .4rem; }
.tl-contact { font-weight: 700; color: var(--ink); }
.badge { font-size: .76rem; font-weight: 700; padding: .2rem .65rem; border-radius: 999px; }
.b-call { background: #E3F4F4; color: #0A6E70; } .b-demo { background: #E8ECFB; color: #3446A8; }
.b-email { background: #FCF3DF; color: #8A5A0E; } .b-meeting { background: #F3E8FA; color: #6B2E97; }
.tl-item p { margin: .3rem 0; line-height: 1.55; font-size: .94rem; }
.tl-item p b { color: var(--ink-soft); font-weight: 600; }

/* Sidebar */
section[data-testid="stSidebar"] { background: #fff; border-right: 1px solid var(--line); }
.pill { display: inline-block; font-size: .8rem; font-weight: 600; padding: .25rem .7rem; border-radius: 999px; margin: 0 .3rem .4rem 0; }
.on { background: var(--teal-soft); color: #0A6E70; } .off { background: #FBE9E7; color: #A03A2C; }

/* Responsive */
@media (max-width: 768px) {
  .block-container { padding: 1rem .9rem 3rem; }
  .hero { padding: 1.4rem 1.2rem; border-radius: 18px; }
  .hero h1 { font-size: 1.85rem; }
  .stat { min-width: 92px; padding: .65rem .85rem; }
  .stTabs [data-baseweb="tab"] { padding: 0 .75rem; font-size: .9rem; }
  .stButton > button { width: 100%; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# STATE & DEMO DATA
# ─────────────────────────────────────────────────────────────
if "interactions" not in st.session_state:
    st.session_state["interactions"] = [
        {
            "deal_name": "Acme Retail",
            "contact": "Priya Shah (VP Operations)",
            "type": "Discovery Call",
            "notes": "Current manual reporting process takes 6 hours per week. Interested in automation but concerned about onboarding time. Budget around ₹8 lakh annually.",
            "outcome": "Scheduled product demo.",
        },
        {
            "deal_name": "Acme Retail",
            "contact": "Priya Shah & Raj Malhotra (IT Security Lead)",
            "type": "Product Demo",
            "notes": "Priya likes workflow automation. Raj asks about SSO, SOC 2, and data residency. Also evaluating CompetitorFlow, which is cheaper.",
            "outcome": "Promised retail case study to Priya and security docs to Raj.",
        },
        {
            "deal_name": "Acme Retail",
            "contact": "Priya Shah & Raj Malhotra",
            "type": "Follow-up Email",
            "notes": "Promised Priya a retail case study and agreed to send security documentation to Raj before Friday. Pricing objection: they want a discount for annual payment.",
            "outcome": "Awaiting response; preparing for next call.",
        },
    ]

if "last_brief" not in st.session_state:
    st.session_state["last_brief"] = None

QUICK_PROMPTS = {
    "Full prep": "How should I prepare for my next call?",
    "Handle pricing": "They want a discount. How should I handle the pricing conversation?",
    "Beat competitor": "How do I position against the competitor they're evaluating?",
    "Close the loop": "What have I promised that I still owe them?",
}


def deal_names():
    names = sorted({i["deal_name"] for i in st.session_state["interactions"]})
    return names or ["Acme Retail"]


def esc(s):
    return html.escape(str(s or ""))


# ─────────────────────────────────────────────────────────────
# HINDSIGHT + LLM
# ─────────────────────────────────────────────────────────────
def retain_interaction(deal_name, contact, itype, notes, outcome):
    text_payload = f"Deal: {deal_name} | Contact: {contact} | Type: {itype} | Notes: {notes} | Outcome: {outcome}"
    st.session_state["interactions"].append(
        {"deal_name": deal_name, "contact": contact, "type": itype, "notes": notes, "outcome": outcome}
    )
    if HINDSIGHT_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {HINDSIGHT_API_KEY}", "Content-Type": "application/json"}
            res = requests.post(
                f"{HINDSIGHT_BASE_URL}/retain",
                json={"bank_id": "sales_memory", "text": text_payload},
                headers=headers,
                timeout=5,
            )
            res.raise_for_status()
        except Exception as e:
            st.warning(f"Saved locally, but Hindsight couldn't be reached: {e}")


def prepare_brief(deal_name, query):
    retrieved_memories = []

    if HINDSIGHT_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {HINDSIGHT_API_KEY}", "Content-Type": "application/json"}
            res = requests.post(
                f"{HINDSIGHT_BASE_URL}/recall",
                json={"bank_id": "sales_memory", "query": f"{deal_name} {query}"},
                headers=headers,
                timeout=5,
            )
            if res.status_code == 200:
                data = res.json()
                retrieved_memories = [m.get("text") for m in data.get("memories", []) if m.get("text")]
        except Exception:
            st.toast("Hindsight unavailable, using local deal history.", icon="⚠️")

    if not retrieved_memories:
        retrieved_memories = [
            f"[{i['type']}] Contact: {i['contact']} | Notes: {i['notes']} | Outcome: {i['outcome']}"
            for i in st.session_state["interactions"]
            if i["deal_name"].lower() in deal_name.lower()
        ]

    context_str = "\n".join(f"- {m}" for m in retrieved_memories)

    system_prompt = f"""
    You are DealRecall, an expert AI sales copilot.
    Analyze the following historical deal interactions and construct a sharp, highly tactical pre-call brief.

    RECALLED DEAL MEMORIES:
    {context_str}

    Provide your briefing structured EXACTLY as these six numbered sections, each starting on its own line as "N. Title":
    1. Deal Summary: Core objectives and current deal status.
    2. Key Stakeholders & Concerns: Name, role, and main priorities/concerns.
    3. Objection Handling Strategy: Specific objections raised (e.g., pricing, competitors, onboarding) and recommended tactics to win.
    4. Competitor Context: Positioning against competitors mentioned.
    5. Pending Commitments: Open action items or deliverables promised.
    6. Suggested Questions: Exactly 3 strategic questions to ask on the call.
    Use short bullet points under each heading.
    """

    if groq_client:
        try:
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
                temperature=0.2,
            )
            brief = response.choices[0].message.content
        except Exception as e:
            brief = f"⚠️ Groq API error: {e}"
    else:
        brief = "⚠️ **Groq API key missing.** Add `GROQ_API_KEY` to your `.env` file to generate briefings."

    return brief, retrieved_memories


SECTION_RE = re.compile(
    r"^[ \t]*(?:#{1,4}[ \t]*)?([1-6])\.[ \t]*\*{0,2}([^\n*:]+?)\*{0,2}[ \t]*:?[ \t]*\*{0,2}[ \t]*(.*)$",
    re.M,
)


def parse_sections(text):
    matches = list(SECTION_RE.finditer(text))
    if len(matches) < 3:
        return []
    sections = []
    for idx, m in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = (m.group(3) + "\n" + text[m.end():end]).strip()
        sections.append((int(m.group(1)), m.group(2).strip(), body))
    return sections


def render_brief(text):
    sections = parse_sections(text)
    if not sections:
        with st.container(key="panel_raw"):
            st.markdown(text)
        return

    def card(num, title, body):
        with st.container(key=f"sec_{num}"):
            st.markdown(f"<div class='sec-title'>{esc(title)}</div>", unsafe_allow_html=True)
            st.markdown(body)

    card(*sections[0])
    rest = sections[1:]
    for i in range(0, len(rest), 2):
        cols = st.columns(2, gap="medium")
        for col, sec in zip(cols, rest[i:i + 2]):
            with col:
                card(*sec)


# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Connections")
    st.markdown(
        f"<span class='pill {'on' if groq_client else 'off'}'>{'●' if groq_client else '○'} Groq {'connected' if groq_client else 'missing key'}</span>"
        f"<span class='pill {'on' if HINDSIGHT_API_KEY else 'off'}'>{'●' if HINDSIGHT_API_KEY else '○'} Hindsight {'live' if HINDSIGHT_API_KEY else 'local only'}</span>",
        unsafe_allow_html=True,
    )
    st.caption(f"Model: `{GROQ_MODEL}`")
    st.markdown("### How it works")
    st.markdown(
        "1. **Log** every call, demo and email.\n"
        "2. **Recall** pulls the relevant history for a deal.\n"
        "3. **Brief** turns it into a tactical plan before you dial."
    )

# ─────────────────────────────────────────────────────────────
# HERO
# ─────────────────────────────────────────────────────────────
total = len(st.session_state["interactions"])
open_items = sum(
    1 for i in st.session_state["interactions"]
    if any(k in (i["outcome"] + i["notes"]).lower() for k in ("promised", "awaiting", "before friday", "send"))
)
st.markdown(
    f"""
    <div class="hero">
      <div>
        <h1>🤝 DealRecall</h1>
        <p>Walk into every call knowing what was said, what was promised, and what to ask next.</p>
      </div>
      <div class="hero-stats">
        <div class="stat"><b>{len(deal_names())}</b><span>Active deals</span></div>
        <div class="stat"><b>{total}</b><span>Touchpoints</span></div>
        <div class="stat"><b>{open_items}</b><span>Open follow-ups</span></div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab1, tab2, tab3 = st.tabs(["⚡ Prepare for call", "📝 Log interaction", "📜 Deal timeline"])

# ─────────────────────────────────────────────────────────────
# TAB 1 — PREPARE
# ─────────────────────────────────────────────────────────────
def _apply_prompt():
    choice = st.session_state.get("quick_prompt")
    if choice:
        st.session_state["user_query"] = QUICK_PROMPTS[choice]


with tab1:
    with st.container(key="panel_prepare"):
        st.subheader("Get a pre-call briefing")
        c1, c2 = st.columns([1, 2], gap="medium")
        with c1:
            deal_selected = st.selectbox("Deal", deal_names())
        with c2:
            if "user_query" not in st.session_state:
                st.session_state["user_query"] = "How should I prepare for my next call?"
            st.text_input("What do you need help with?", key="user_query")

        st.pills(
            "Quick prompts", list(QUICK_PROMPTS.keys()), key="quick_prompt",
            on_change=_apply_prompt, label_visibility="collapsed",
        )
        go = st.button("Generate briefing", type="primary")

    if go:
        with st.spinner("Recalling deal history and building your plan…"):
            brief, mems = prepare_brief(deal_selected, st.session_state["user_query"])
        st.session_state["last_brief"] = {"deal": deal_selected, "brief": brief, "memories": mems}

    result = st.session_state["last_brief"]
    if result:
        st.markdown(f"### Briefing: {esc(result['deal'])}")
        render_brief(result["brief"])
        with st.expander(f"🔍 Memories used ({len(result['memories'])})"):
            if result["memories"]:
                for n, mem in enumerate(result["memories"], 1):
                    st.markdown(f"<div class='mem'><small>Memory {n}</small><br>{esc(mem)}</div>", unsafe_allow_html=True)
            else:
                st.write("No memories found for this deal.")
    else:
        st.markdown(
            "<div class='empty'><b>Your briefing will appear here</b>Pick a deal, choose a quick prompt, then select Generate briefing.</div>",
            unsafe_allow_html=True,
        )

# ─────────────────────────────────────────────────────────────
# TAB 2 — LOG
# ─────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Log a touchpoint")
    st.caption("The more detail you save now, the sharper your next briefing.")
    with st.form("add_interaction_form", clear_on_submit=True):
        col_a, col_b = st.columns(2, gap="medium")
        with col_a:
            d_name = st.text_input("Company / deal name", value=deal_names()[0])
            contact_person = st.text_input("Contact name and role", placeholder="e.g. Priya Shah (VP Operations)")
        with col_b:
            itype = st.selectbox("Interaction type", ["Call", "Meeting", "Email", "Demo"])
            outcome_text = st.text_input("Outcome / next step", placeholder="e.g. Send proposal by Friday")

        notes_text = st.text_area(
            "Notes",
            height=140,
            placeholder="Objections, stakeholders, competitors, commitments you made…",
        )
        submitted = st.form_submit_button("Save to memory", type="primary")
        if submitted:
            if d_name.strip() and notes_text.strip():
                retain_interaction(d_name.strip(), contact_person, itype, notes_text, outcome_text)
                st.success(f"Saved. {d_name.strip()} now has {sum(1 for i in st.session_state['interactions'] if i['deal_name'] == d_name.strip())} touchpoints in memory.")
            else:
                st.error("Add a company name and notes to save this touchpoint.")

# ─────────────────────────────────────────────────────────────
# TAB 3 — TIMELINE
# ─────────────────────────────────────────────────────────────
def badge_class(t):
    t = t.lower()
    if "demo" in t:
        return "b-demo"
    if "email" in t:
        return "b-email"
    if "meeting" in t:
        return "b-meeting"
    return "b-call"


with tab3:
    st.subheader("Deal timeline")
    filter_deal = st.selectbox("Deal", deal_names(), key="timeline_filter")
    filtered = [i for i in st.session_state["interactions"] if i["deal_name"] == filter_deal]
    if not filtered:
        st.markdown(
            "<div class='empty'><b>No touchpoints yet</b>Log your first interaction to start this deal's timeline.</div>",
            unsafe_allow_html=True,
        )
    else:
        items = "".join(
            f"""
            <div class="tl-item">
              <div class="tl-head">
                <span class="badge {badge_class(it['type'])}">{esc(it['type'])}</span>
                <span class="tl-contact">{esc(it['contact'])}</span>
              </div>
              <p><b>Notes</b><br>{esc(it['notes'])}</p>
              <p><b>Outcome</b><br>{esc(it['outcome'])}</p>
            </div>"""
            for it in reversed(filtered)
        )
        st.markdown(f"<div class='tl'>{items}</div>", unsafe_allow_html=True)