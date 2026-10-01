CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {
  --ink: #0F172A;
  --ink-secondary: #334155;
  --ink-soft: #64748B;
  --ink-muted: #94A3B8;
  --paper: #F8FAFC;
  --card: #FFFFFF;
  --line: #E2E8F0;
  --line-strong: #CBD5E1;
  --teal: #0D9488;
  --teal-deep: #0F766E;
  --teal-soft: #F0FDFA;
  --teal-border: #99F6E4;
  --amber: #D97706;
  --amber-soft: #FEF3C7;
  --red: #E11D48;
  --red-soft: #FFF1F2;
  --indigo: #4F46E5;
  --indigo-soft: #EEF2FF;
  --radius: 16px;
}

html, body, .stApp, [class*="css"] {
  font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
  -webkit-font-smoothing: antialiased;
}

.stApp {
  background: var(--paper) !important;
  color: var(--ink) !important;
}

.stApp p, .stApp li, .stApp label, .stApp span, .stApp div[data-testid="stMarkdownContainer"] {
  color: var(--ink);
}

h1, h2, h3, h4 {
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  color: var(--ink) !important;
  letter-spacing: -0.02em;
  font-weight: 700;
}

#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {
  visibility: hidden;
  display: none !important;
}

header[data-testid="stHeader"] {
  background: transparent !important;
}

section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
  display: none !important;
}

.block-container {
  padding-top: 1.5rem !important;
  padding-bottom: 4rem !important;
  max-width: 1160px !important;
}

div[data-testid="stVerticalBlock"] {
  gap: 0.85rem;
}

/* TOPBAR & BRANDING */
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.25rem;
  margin-bottom: 1.25rem;
  padding-bottom: 0.85rem;
  border-bottom: 1px solid var(--line);
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.mark {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, #0F172A 0%, #0D9488 100%);
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 800;
  font-size: 0.88rem;
  letter-spacing: 0.05em;
  box-shadow: 0 4px 12px rgba(13, 148, 136, 0.28);
}

.brand strong {
  display: block;
  font-size: 1.35rem;
  font-weight: 800;
  line-height: 1.15;
  color: var(--ink);
  letter-spacing: -0.02em;
}

.brand span {
  color: var(--ink-soft);
  font-size: 0.84rem;
  font-weight: 500;
}

.status {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.76rem;
  font-weight: 600;
  padding: 0.32rem 0.75rem;
  border-radius: 999px;
  line-height: 1.3;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}

.pill.on {
  background: #ECFDF5;
  color: #047857;
  border: 1px solid #A7F3D0;
}
.pill.on .status-dot {
  background: #10B981;
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.25);
}

.pill.off {
  background: var(--red-soft);
  color: var(--red);
  border: 1px solid #FECDD3;
}
.pill.off .status-dot {
  background: #F43F5E;
}

.pill.neutral {
  background: #FFFFFF;
  color: var(--ink-secondary);
  border: 1px solid var(--line-strong);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.73rem;
}

.hindsight-status {
  display: inline-flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.55rem 0.95rem 0.55rem 0.75rem;
  border-radius: 14px;
  min-width: 220px;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
}
.hindsight-status .status-dot {
  width: 10px;
  height: 10px;
  flex: none;
}
.hindsight-copy {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
}
.hindsight-status strong {
  font-size: 0.92rem;
  font-weight: 800;
  letter-spacing: -0.01em;
}
.hindsight-status em {
  font-style: normal;
  font-size: 0.75rem;
  font-weight: 600;
  opacity: 0.85;
}
.hindsight-status.on {
  background: #0F766E;
  color: #FFFFFF;
  border: 1px solid #115E59;
}
.hindsight-status.on .status-dot {
  background: #6EE7B7;
  box-shadow: 0 0 0 4px rgba(110, 231, 183, 0.28);
}
.hindsight-status.on .hindsight-copy,
.hindsight-status.on strong,
.hindsight-status.on em {
  color: #FFFFFF;
}
.hindsight-status.off {
  background: #BE123C;
  color: #FFFFFF;
  border: 1px solid #9F1239;
}
.hindsight-status.off .status-dot {
  background: #FECDD3;
  box-shadow: 0 0 0 4px rgba(254, 205, 211, 0.28);
}
.hindsight-status.off .hindsight-copy,
.hindsight-status.off strong,
.hindsight-status.off em {
  color: #FFFFFF;
}

/* EXECUTIVE CONTEXT HERO BANNER */
.context {
  background: linear-gradient(135deg, #0F172A 0%, #1E293B 55%, #11364A 100%);
  color: #FFFFFF;
  border-radius: 18px;
  padding: 1.45rem 1.65rem;
  display: flex;
  justify-content: space-between;
  gap: 1.5rem;
  align-items: flex-end;
  flex-wrap: wrap;
  margin: 0.45rem 0 1.25rem;
  box-shadow: 0 10px 25px -4px rgba(15, 23, 42, 0.22), 0 4px 6px -2px rgba(15, 23, 42, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.1);
  position: relative;
  overflow: hidden;
}

.context::before {
  content: "";
  position: absolute;
  top: -40px;
  right: -40px;
  width: 160px;
  height: 160px;
  background: radial-gradient(circle, rgba(45, 212, 191, 0.15) 0%, transparent 70%);
  pointer-events: none;
}

.context .kicker {
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #2DD4BF !important;
  margin-bottom: 0.3rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.context h2, .context h2 * {
  color: #FFFFFF !important;
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  font-size: 1.75rem !important;
  font-weight: 800 !important;
  margin: 0.15rem 0 0.35rem !important;
  letter-spacing: -0.02em !important;
  line-height: 1.2 !important;
}

.context p, .context p * {
  color: #CBD5E1 !important;
  font-size: 0.95rem !important;
  line-height: 1.55 !important;
  margin: 0 !important;
  max-width: 680px !important;
}

.flags {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
}

.context .flag {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #F8FAFC;
  border-radius: 999px;
  padding: 0.42rem 0.85rem;
  font-size: 0.8rem;
  font-weight: 600;
  backdrop-filter: blur(4px);
}

.context .flag.hot {
  background: rgba(245, 158, 11, 0.2);
  border-color: rgba(245, 158, 11, 0.4);
  color: #FDE68A;
}

.context .flag.val {
  background: rgba(16, 185, 129, 0.15);
  border-color: rgba(16, 185, 129, 0.3);
  color: #A7F3D0;
}

/* DEAL PIPELINE CARDS */
.deal-stage {
  display: inline-block;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.2rem 0.55rem;
  border-radius: 6px;
  margin-bottom: 0.45rem;
  line-height: 1.3;
}

.stage-commercial-review {
  background: #EEF2FF;
  color: #4F46E5;
}

.stage-closed-lost {
  background: #FFF1F2;
  color: #E11D48;
}

.stage-closed-won {
  background: #ECFDF5;
  color: #059669;
}

.stage-discovery {
  background: #F0F9FF;
  color: #0284C7;
}

.deal-name {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 700;
  font-size: 1.15rem;
  color: var(--ink);
  margin: 0.15rem 0 0.35rem;
  line-height: 1.3;
}

.deal-meta {
  color: var(--ink-soft);
  font-size: 0.88rem;
  font-weight: 600;
  margin: 0.2rem 0 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.deal-meta .val-bold {
  color: var(--ink);
  font-weight: 700;
}

.deal-meta .hot-inline {
  background: #FEF3C7;
  color: #B45309;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
}

.in-view {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  width: 100%;
  padding: 0.42rem 0.75rem;
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--teal-deep);
  background: #CCFBF1;
  border: 1px solid var(--teal-border);
  border-radius: 10px;
  margin-top: 0.4rem;
}

.in-view-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--teal);
  display: inline-block;
  box-shadow: 0 0 0 2px rgba(13, 148, 136, 0.25);
}

[class*="st-key-dcardon_"] {
  background: linear-gradient(180deg, #F0FDFA 0%, #FFFFFF 100%) !important;
  border: 2px solid var(--teal) !important;
  border-radius: var(--radius) !important;
  padding: 1.1rem 1.1rem 0.95rem !important;
  box-shadow: 0 8px 24px -4px rgba(13, 148, 136, 0.18), 0 2px 6px -1px rgba(13, 148, 136, 0.08) !important;
  transition: all 0.2s ease !important;
}

[class*="st-key-dcardoff_"] {
  background: var(--card) !important;
  border: 1.5px solid var(--line) !important;
  border-radius: var(--radius) !important;
  padding: 1.1rem 1.1rem 0.95rem !important;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03) !important;
  transition: all 0.2s ease !important;
}

[class*="st-key-dcardoff_"]:hover {
  border-color: var(--line-strong) !important;
  transform: translateY(-2px) !important;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.06) !important;
}

[class*="st-key-dcardoff_"] button {
  background: #F8FAFC !important;
  color: var(--ink-secondary) !important;
  border: 1px solid var(--line-strong) !important;
  border-radius: 10px !important;
  padding: 0.42rem 0.75rem !important;
  font-size: 0.8rem !important;
  font-weight: 600 !important;
  width: 100% !important;
  text-align: center !important;
  margin-top: 0.4rem !important;
  transition: all 0.15s ease !important;
}

[class*="st-key-dcardoff_"] button:hover {
  background: var(--ink) !important;
  color: #FFFFFF !important;
  border-color: var(--ink) !important;
  transform: none !important;
}

/* STREAMLIT SEGMENTED CONTROL (TABS) FIX */
[data-testid="stSegmentedControl"] {
  background: #E2E8F0 !important;
  border-radius: 14px !important;
  padding: 4px !important;
  border: 1px solid #CBD5E1 !important;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.04) !important;
  margin-bottom: 1.25rem !important;
  width: 100% !important;
}

[data-testid="stSegmentedControl"] > div,
[data-testid="stSegmentedControl"] [data-baseweb="button-group"] {
  background: transparent !important;
  gap: 4px !important;
  width: 100% !important;
}

[data-testid="stSegmentedControl"] button {
  flex: 1 1 0% !important;
  background: transparent !important;
  color: #475569 !important;
  border: none !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
  font-size: 0.92rem !important;
  padding: 0.55rem 1.2rem !important;
  transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1) !important;
  box-shadow: none !important;
  outline: none !important;
}

[data-testid="stSegmentedControl"] button:hover {
  background: rgba(255, 255, 255, 0.6) !important;
  color: #0F172A !important;
}

[data-testid="stSegmentedControl"] button[aria-checked="true"],
[data-testid="stSegmentedControl"] button[aria-selected="true"],
[data-testid="stSegmentedControl"] button[data-checked="true"] {
  background: #FFFFFF !important;
  color: #0F172A !important;
  font-weight: 700 !important;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06) !important;
  border: none !important;
  outline: none !important;
}

[data-testid="stSegmentedControl"] button:focus,
[data-testid="stSegmentedControl"] button:active {
  outline: none !important;
  border: none !important;
  box-shadow: none !important;
}

[data-testid="stSegmentedControl"] button[aria-checked="true"]:focus,
[data-testid="stSegmentedControl"] button[aria-checked="true"]:active {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06) !important;
}

/* STREAMLIT PILLS (QUICK PROMPTS) FIX */
[data-testid="stPills"] {
  margin-top: 0.55rem !important;
  margin-bottom: 1.1rem !important;
}

[data-testid="stPills"] > div {
  gap: 0.5rem !important;
  flex-wrap: wrap !important;
}

[data-testid="stPills"] button {
  background: #F1F5F9 !important;
  color: #334155 !important;
  border: 1px solid #CBD5E1 !important;
  border-radius: 9999px !important;
  padding: 0.45rem 1rem !important;
  font-size: 0.82rem !important;
  font-weight: 600 !important;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
  transition: all 0.15s ease !important;
  outline: none !important;
}

[data-testid="stPills"] button:hover {
  background: #E2E8F0 !important;
  color: #0F172A !important;
  border-color: #94A3B8 !important;
  transform: translateY(-1px) !important;
}

[data-testid="stPills"] button[aria-checked="true"],
[data-testid="stPills"] button[aria-selected="true"],
[data-testid="stPills"] button[data-checked="true"] {
  background: #0F172A !important;
  color: #FFFFFF !important;
  border-color: #0F172A !important;
  box-shadow: 0 2px 5px rgba(15, 23, 42, 0.2) !important;
}

/* FORM CONTROLS & INPUTS */
[data-baseweb="input"] {
  background: #FFFFFF !important;
  border: 1.5px solid var(--line-strong) !important;
  border-radius: 12px !important;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}

[data-baseweb="input"]:focus-within {
  border-color: var(--teal) !important;
  box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.15) !important;
}

[data-baseweb="base-input"] {
  background: transparent !important;
  border: none !important;
}

.stTextInput input {
  background: transparent !important;
  border: none !important;
  color: var(--ink) !important;
  font-size: 0.95rem !important;
  font-weight: 500 !important;
  padding: 0.65rem 0.75rem !important;
  box-shadow: none !important;
}

.stTextInput input:focus {
  box-shadow: none !important;
  border: none !important;
}

.stTextArea textarea {
  background: #FFFFFF !important;
  border: 1.5px solid var(--line-strong) !important;
  border-radius: 12px !important;
  color: var(--ink) !important;
  font-size: 0.95rem !important;
  padding: 0.75rem 0.85rem !important;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}

.stTextArea textarea:focus {
  border-color: var(--teal) !important;
  box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.15) !important;
}

div[data-baseweb="select"] > div {
  background: #FFFFFF !important;
  border: 1.5px solid var(--line-strong) !important;
  border-radius: 12px !important;
  color: var(--ink) !important;
}

.stTextInput label, .stTextArea label, .stSelectbox label, .stDateInput label, .stMultiSelect label {
  font-weight: 600 !important;
  color: var(--ink) !important;
  font-size: 0.88rem !important;
  margin-bottom: 0.35rem !important;
}

/* BUTTONS */
.stButton > button, .stFormSubmitButton > button {
  border-radius: 11px !important;
  font-weight: 700 !important;
  padding: 0.65rem 1.35rem !important;
  font-size: 0.92rem !important;
  letter-spacing: 0.01em !important;
  transition: all 0.2s ease !important;
  border: 1.5px solid var(--line-strong) !important;
}

.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"], .stFormSubmitButton > button {
  background: linear-gradient(135deg, #0D9488 0%, #0F766E 100%) !important;
  color: #FFFFFF !important;
  border-color: #0F766E !important;
  box-shadow: 0 2px 6px rgba(13, 148, 136, 0.25) !important;
}

.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button:hover {
  transform: translateY(-1px) !important;
  box-shadow: 0 4px 12px rgba(13, 148, 136, 0.35) !important;
}

.stButton > button:not([kind="primary"]) {
  background: #FFFFFF !important;
  color: var(--ink-secondary) !important;
  border: 1.5px solid var(--line-strong) !important;
}

.stButton > button:not([kind="primary"]):hover {
  background: #F8FAFC !important;
  color: var(--ink) !important;
  border-color: var(--ink-soft) !important;
  transform: translateY(-1px) !important;
}

[class*="st-key-brief_go"] button {
  font-size: 1.08rem !important;
  padding: 0.95rem 1.4rem !important;
  min-height: 3.35rem;
  width: 100% !important;
  box-shadow: 0 8px 18px rgba(13, 148, 136, 0.32) !important;
}
[class*="st-key-brief_compare"] button {
  width: 100% !important;
  min-height: 3.35rem;
  font-weight: 600 !important;
  background: #FFFFFF !important;
}

.stButton > button:focus-visible, .stFormSubmitButton > button:focus-visible {
  outline: 3px solid rgba(13, 148, 136, 0.25) !important;
}

/* CONTAINERS & CARDS */
[class*="st-key-panel_"] {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.35rem 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

[data-testid="stForm"] {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.35rem 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.form-label {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 700;
  font-size: 1.05rem;
  color: var(--ink);
  margin: 0.5rem 0 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

/* BRIEFINGS & MEMORY CARDS */
[class*="st-key-mem-"],
[class*="st-key-gen-"] {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.25rem 1.35rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
  height: 100%;
}

[class*="st-key-mem-1"] {
  background: var(--teal-soft);
  border-color: var(--teal-border);
  border-left: 4px solid var(--teal);
}

[class*="st-key-mem-5"] {
  background: var(--amber-soft);
  border-color: #FDE68A;
  border-left: 4px solid var(--amber);
}

.sec-title {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 800;
  font-size: 1.08rem;
  color: var(--ink);
  margin: 0 0 0.55rem 0;
  letter-spacing: -0.01em;
}

[class*="st-key-mem-"] li, [class*="st-key-mem-"] p,
[class*="st-key-gen-"] li, [class*="st-key-gen-"] p {
  line-height: 1.6;
  font-size: 0.94rem;
  color: var(--ink-secondary);
}

.ready {
  background: #ECFDF5;
  color: #047857;
  border: 1px solid #A7F3D0;
  border-radius: 10px;
  padding: 0.55rem 0.95rem;
  font-weight: 700;
  font-size: 0.86rem;
  margin: 0.15rem 0 0.75rem;
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

.col-label {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 800;
  font-size: 1.25rem;
  color: var(--ink);
  margin: 0.2rem 0 0.75rem;
  letter-spacing: -0.01em;
}

.col-label span {
  display: block;
  font-weight: 500;
  font-size: 0.82rem;
  color: var(--ink-soft);
  margin-top: 0.2rem;
}
.col-label.with { color: var(--teal-deep); }
.col-label.without { color: var(--ink-secondary); }

.compare-intro {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0.85rem 1rem 0.35rem;
  margin: 0.35rem 0 0.85rem;
}
.compare-intro p {
  margin: 0.55rem 0 0.7rem;
  color: var(--ink-secondary);
  font-size: 0.95rem;
  line-height: 1.5;
}
[class*="st-key-cmp_with"] {
  background: var(--teal-soft);
  border: 1px solid var(--teal-border);
  border-radius: 16px;
  padding: 0.95rem 1rem 0.4rem;
}
[class*="st-key-cmp_without"] {
  background: #F8FAFC;
  border: 1px solid var(--line-strong);
  border-radius: 16px;
  padding: 0.95rem 1rem 0.4rem;
}

.picked {
  background: #FFFFFF;
  border: 1px solid var(--teal-border);
  border-left: 4px solid var(--teal);
  border-radius: 14px;
  padding: 0.85rem 1rem 0.75rem;
  margin: 0.9rem 0 0.4rem;
}
.picked strong {
  display: block;
  font-size: 1rem;
  color: var(--teal-deep);
}
.picked > span {
  display: block;
  margin-top: 0.2rem;
  color: var(--ink-soft);
  font-size: 0.86rem;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.7rem;
}
.stApp .chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: var(--teal-soft);
  color: var(--teal-deep);
  border: 1px solid var(--teal-border);
  border-radius: 999px;
  padding: 0.28rem 0.55rem 0.28rem 0.7rem;
  font-size: 0.78rem;
  font-weight: 700;
}
.chip b {
  background: #FFFFFF;
  color: var(--ink);
  border-radius: 999px;
  min-width: 1.25rem;
  text-align: center;
  padding: 0.05rem 0.35rem;
  font-size: 0.75rem;
}

.mem {
  background: var(--card);
  border: 1px solid var(--line);
  border-left: 4px solid var(--teal);
  border-radius: 12px;
  padding: 0.85rem 1rem;
  margin-bottom: 0.65rem;
  font-size: 0.92rem;
  line-height: 1.55;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
}

.mem small {
  color: var(--ink-soft);
  font-weight: 700;
  letter-spacing: 0.04em;
  font-size: 0.74rem;
}

.mem.play {
  border-left-color: var(--amber);
  background: #FFFDF8;
}

/* EMPTY STATE */
.empty {
  text-align: left;
  padding: 1.65rem 1.65rem;
  color: var(--ink-soft);
  background: var(--card);
  border: 1.5px dashed var(--line-strong);
  border-radius: var(--radius);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}

.empty b {
  display: block;
  color: var(--ink);
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 1.25rem;
  font-weight: 800;
  margin-bottom: 0.4rem;
  letter-spacing: -0.01em;
}

.steps {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.85rem;
  margin-top: 1.15rem;
}

.step {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.95rem 1rem;
  transition: all 0.15s ease;
}

.step:hover {
  border-color: var(--line-strong);
  background: #F1F5F9;
}

.step b {
  display: block;
  font-size: 0.78rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--teal-deep);
  margin-bottom: 0.35rem;
  font-weight: 700;
}

.step span {
  color: var(--ink-secondary);
  font-size: 0.88rem;
  line-height: 1.45;
}

/* TIMELINE & PROMISES */
.promise-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 0.75rem;
  margin: 0.35rem 0 1.25rem;
}

.promise {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0.95rem 1.1rem;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
  transition: all 0.15s ease;
}

.promise:hover {
  border-color: var(--line-strong);
  transform: translateY(-1px);
}

.promise strong {
  display: block;
  margin-top: 0.45rem;
  font-size: 0.95rem;
  color: var(--ink);
  line-height: 1.4;
}

.promise .tl-date {
  display: block;
  color: var(--ink-soft);
  font-size: 0.8rem;
  font-weight: 500;
  margin-top: 0.35rem;
}

.section-label {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 1.25rem;
  font-weight: 800;
  color: var(--ink);
  margin: 0.75rem 0 0.4rem;
  letter-spacing: -0.01em;
}

.tl {
  position: relative;
  margin: 0.75rem 0 0 0.85rem;
  padding-left: 1.75rem;
  border-left: 2px solid var(--line);
}

.tl-item {
  position: relative;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.1rem 1.25rem;
  margin-bottom: 1rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}

.tl-item::before {
  content: "";
  position: absolute;
  left: -2.35rem;
  top: 1.35rem;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--teal);
  border: 3px solid var(--paper);
  box-shadow: 0 0 0 2px var(--line);
}

.tl-head {
  display: flex;
  gap: 0.55rem;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 0.65rem;
}

.tl-contact {
  font-weight: 700;
  color: var(--ink);
  font-size: 0.92rem;
}

.tl-item .tl-date {
  color: var(--ink-soft);
  font-size: 0.82rem;
  font-weight: 500;
}

.badge {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.22rem 0.6rem;
  border-radius: 999px;
  letter-spacing: 0.02em;
}

.b-call { background: #E3F4F4; color: #0A6E70; }
.b-demo { background: #EEF2FF; color: #4338CA; }
.b-email { background: #FEF3C7; color: #B45309; }
.b-meeting { background: #F3E8FA; color: #7E22CE; }
.b-over { background: var(--red-soft); color: var(--red); }
.b-open { background: var(--amber-soft); color: var(--amber); }
.b-done { background: #ECFDF5; color: #047857; }

.tl-callout {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.65rem 0.85rem;
  margin-top: 0.6rem;
  font-size: 0.88rem;
  line-height: 1.5;
}

.tl-callout.tactic {
  background: #FFFBEB;
  border-color: #FEF3C7;
  color: #78350F;
}

.tl-callout.outcome {
  background: #F0FDF4;
  border-color: #DCFCE7;
  color: #14532D;
}

.tl-callout b {
  display: block;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.2rem;
  color: var(--ink-soft);
}

.tl-callout.tactic b { color: #B45309; }
.tl-callout.outcome b { color: #15803D; }

.tl-item p {
  margin: 0.35rem 0;
  line-height: 1.6;
  font-size: 0.92rem;
  color: var(--ink-secondary);
}

.tl-item p b {
  color: var(--ink);
  font-weight: 600;
}

div[data-testid="stExpander"] {
  background: var(--card) !important;
  border: 1.5px solid var(--line) !important;
  border-radius: 14px !important;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
}

/* Two-Person Approval Modal & Security UI */
.approval-card {
  background: var(--card);
  border: 1.5px solid var(--line-strong);
  border-radius: var(--radius);
  padding: 1.5rem;
  margin: 1.2rem 0;
  box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04);
}

.approval-header {
  border-bottom: 1px solid var(--line);
  padding-bottom: 1rem;
  margin-bottom: 1.2rem;
}

.approval-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--ink);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.approval-desc {
  font-size: 0.88rem;
  color: var(--ink-soft);
  margin-top: 0.35rem;
}

.approval-status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.85rem;
  margin: 1rem 0;
}

.approval-user-item {
  background: var(--paper);
  border: 1.5px solid var(--line);
  border-radius: 12px;
  padding: 0.85rem 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.approval-user-item.verified {
  border-color: var(--teal-border);
  background: var(--teal-soft);
}

.approval-user-item.waiting {
  border-color: var(--amber-soft);
  background: #FFFBEB;
}

.approval-user-name {
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--ink);
}

.approval-user-role {
  font-size: 0.75rem;
  color: var(--ink-soft);
}

.approval-tag {
  font-size: 0.78rem;
  font-weight: 700;
  padding: 0.25rem 0.65rem;
  border-radius: 9999px;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

.approval-tag.verified {
  background: #CCFBF1;
  color: var(--teal-deep);
}

.approval-tag.waiting {
  background: var(--amber-soft);
  color: var(--amber);
}

.approval-timer {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ink-soft);
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.approval-timer.urgent {
  color: var(--red);
}

/* Security Audit Trail */
.audit-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.75rem 1rem;
  margin-bottom: 0.65rem;
}

.audit-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.35rem;
}

.audit-deal {
  font-weight: 700;
  font-size: 0.95rem;
  color: var(--ink);
}

.audit-meta {
  font-size: 0.8rem;
  color: var(--ink-soft);
  line-height: 1.4;
}

.badge.status-approved {
  background: #CCFBF1 !important;
  color: #0F766E !important;
  border: 1px solid #99F6E4 !important;
}

.badge.status-rejected, .badge.status-expired, .badge.status-cancelled {
  background: #FEE2E2 !important;
  color: #991B1B !important;
  border: 1px solid #FECACA !important;
}

/* MEMORY TIMELINE STYLING */
.mem-timeline {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  margin-top: 1rem;
}

.mem-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 1.1rem 1.25rem;
  transition: all 0.18s ease-in-out;
  position: relative;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

.mem-card:hover {
  border-color: var(--teal-border);
  box-shadow: 0 4px 12px rgba(13, 148, 136, 0.08);
}

.mem-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.mem-date {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ink-soft);
}

.mem-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.01em;
}

.mem-statement {
  font-size: 0.92rem;
  line-height: 1.5;
  color: var(--ink);
  margin: 0.45rem 0 0.75rem;
}

.mem-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding-top: 0.55rem;
  border-top: 1px dashed var(--line);
}

.mem-badges {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
}

.mem-source-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background: #F1F5F9;
  color: #334155;
  border: 1px solid #CBD5E1;
}

.mem-storage-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  font-size: 0.73rem;
  font-weight: 600;
}

.mem-storage-badge.hindsight {
  background: #F0FDFA;
  color: #0F766E;
  border: 1px solid #99F6E4;
}

.mem-storage-badge.local {
  background: #F8FAFC;
  color: #475569;
  border: 1px solid #E2E8F0;
}

.mem-detail-card {
  background: var(--card);
  border: 1px solid var(--teal-border);
  border-radius: 14px;
  padding: 1.25rem 1.4rem;
  margin: 1rem 0;
  box-shadow: 0 8px 24px rgba(13, 148, 136, 0.1);
}

/* WHAT CHANGED FEATURE 2 STYLES */
.wc-container {
  background: var(--card);
  border: 1.5px solid var(--line-strong);
  border-radius: 16px;
  padding: 1.25rem 1.4rem;
  margin-bottom: 1.25rem;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
}

.wc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.85rem;
  border-bottom: 1px solid var(--line);
  padding-bottom: 0.75rem;
}

.wc-title {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 1.15rem;
  font-weight: 800;
  color: var(--ink);
  display: flex;
  align-items: center;
  gap: 0.45rem;
  letter-spacing: -0.01em;
}

.wc-time-badge {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--teal-deep);
  background: var(--teal-soft);
  border: 1px solid var(--teal-border);
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
}

.wc-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.9rem 1.1rem;
  margin-bottom: 0.75rem;
  transition: all 0.15s ease;
}

.wc-card:hover {
  border-color: var(--line-strong);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.03);
}

.wc-card.c-new { border-left: 4px solid #10B981; }
.wc-card.c-still-open { border-left: 4px solid #F59E0B; }
.wc-card.c-resolved { border-left: 4px solid #059669; }
.wc-card.c-changed { border-left: 4px solid #8B5CF6; }
.wc-card.c-commitment { border-left: 4px solid #0D9488; }

.wc-card-head {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin-bottom: 0.35rem;
}

.wc-card-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--ink);
}

.wc-card-desc {
  font-size: 0.9rem;
  line-height: 1.55;
  color: var(--ink-secondary);
  margin-bottom: 0.5rem;
}

.wc-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
  font-size: 0.78rem;
  color: var(--ink-soft);
}

.b-new {
  background: #ECFDF5;
  color: #047857;
  border: 1px solid #A7F3D0;
}

.b-still-open {
  background: #FFFBEB;
  color: #B45309;
  border: 1px solid #FDE68A;
}

.b-resolved {
  background: #F0FDF4;
  color: #15803D;
  border: 1px solid #BBF7D0;
}

.b-changed {
  background: #F5F3FF;
  color: #6D28D9;
  border: 1px solid #DDD6FE;
}

.b-commitment {
  background: #F0FDFA;
  color: #0F766E;
  border: 1px solid #99F6E4;
}

@media (max-width: 840px) {
  .block-container { padding: 0.85rem 0.85rem 3rem !important; }
  .context h2 { font-size: 1.4rem !important; }
  .steps { grid-template-columns: 1fr; }
  .topbar { align-items: flex-start; flex-direction: column; }
  .stButton > button, .stFormSubmitButton > button { width: 100% !important; }
}

@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}
</style>
"""
