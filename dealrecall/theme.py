CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

:root {
  --ink: #12243A;
  --ink-soft: #4A5B70;
  --paper: #F4F6F8;
  --card: #FFFFFF;
  --line: #E1E7EF;
  --teal: #0E8A8C;
  --teal-deep: #0A6E70;
  --teal-soft: #E5F4F4;
  --amber: #8A5A0E;
  --amber-soft: #FCF3DF;
  --red: #A03A2C;
  --red-soft: #FBE9E7;
  --radius: 16px;
}

html, body, .stApp, [class*="css"] { font-family: 'Plus Jakarta Sans', system-ui, sans-serif; }
.stApp { background: var(--paper); color: var(--ink); }
.stApp p, .stApp li, .stApp label, .stApp span, .stApp div[data-testid="stMarkdownContainer"] { color: var(--ink); }
h1, h2, h3 { font-family: 'Fraunces', Georgia, serif !important; color: var(--ink) !important; letter-spacing: -0.02em; }

#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none; }
.block-container { padding-top: 1.25rem; padding-bottom: 4rem; max-width: 1120px; }
div[data-testid="stVerticalBlock"] { gap: 0.7rem; }

.topbar {
  display: flex; justify-content: space-between; align-items: center; gap: 1rem;
  margin-bottom: 1rem;
}
.brand { display: flex; align-items: center; gap: 0.75rem; }
.mark {
  width: 36px; height: 36px; border-radius: 10px; background: var(--ink); color: #fff;
  display: grid; place-items: center; font-weight: 700; font-size: 0.78rem; letter-spacing: 0.04em;
}
.brand strong { display: block; font-family: 'Fraunces', serif; font-size: 1.25rem; line-height: 1.1; }
.brand span { color: var(--ink-soft); font-size: 0.82rem; }
.status { display: flex; gap: 0.4rem; flex-wrap: wrap; justify-content: flex-end; }
.pill { display: inline-block; font-size: .78rem; font-weight: 700; padding: .28rem .7rem; border-radius: 999px; }
.on { background: var(--teal-soft); color: var(--teal-deep); }
.off { background: var(--red-soft); color: var(--red); }
.neutral { background: #fff; color: var(--ink-soft); border: 1px solid var(--line); }

.context {
  background: var(--ink); color: #fff; border-radius: 18px; padding: 1.15rem 1.3rem;
  display: flex; justify-content: space-between; gap: 1.2rem; align-items: flex-end; flex-wrap: wrap;
  margin: 0.35rem 0 0.2rem;
}
.context h2 { color: #fff !important; font-size: 1.7rem; margin: 0.15rem 0 0.2rem; }
.context p, .context .kicker, .context .quiet { color: #C9D8E8 !important; margin: 0; }
.context .kicker { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
.flags { display: flex; gap: 0.45rem; flex-wrap: wrap; }
.context .flag {
  background: rgba(255,255,255,.1); border: 1px solid rgba(255,255,255,.16);
  color: #fff; border-radius: 999px; padding: 0.35rem 0.7rem; font-size: 0.78rem; font-weight: 700;
}
.flag.hot { background: #F6D58A; color: #5C3B04; border-color: transparent; }

.deal-stage {
  font-size: 0.68rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-soft); margin: 0;
}
.deal-name { font-family: 'Fraunces', serif; font-weight: 700; font-size: 1.12rem; margin: 0.15rem 0 0; line-height: 1.2; }
.deal-meta { color: var(--ink-soft); font-size: 0.82rem; margin: 0.28rem 0 0.15rem; }
.deal-meta .hot-inline { color: var(--amber); font-weight: 700; }
.in-view { font-size: 0.75rem; font-weight: 700; color: var(--teal-deep); margin-top: 0.35rem; }

[class*="st-key-dcardon_"] {
  background: var(--teal-soft); border: 1.5px solid #9ed4d4; border-radius: 16px; padding: 0.85rem 0.95rem 0.75rem;
}
[class*="st-key-dcardoff_"] {
  background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 0.85rem 0.95rem 0.7rem;
}
[class*="st-key-dcardoff_"] button {
  background: transparent !important; color: var(--teal-deep) !important; border: none !important;
  padding: 0.15rem 0 !important; font-weight: 700; text-align: left;
}
[class*="st-key-dcardoff_"] button:hover { color: var(--ink) !important; }

[data-testid="stSegmentedControl"] { width: 100%; }
[data-testid="stSegmentedControl"] button { font-weight: 700; }

.stTextInput input, .stTextArea textarea, div[data-baseweb="select"] > div,
[data-baseweb="input"] {
  background: var(--card) !important; border: 1.5px solid var(--line) !important;
  border-radius: 12px !important; color: var(--ink) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus { border-color: var(--teal) !important; box-shadow: 0 0 0 3px var(--teal-soft) !important; }
.stTextInput label, .stTextArea label, .stSelectbox label, .stDateInput label, .stMultiSelect label {
  font-weight: 600 !important; color: var(--ink) !important; font-size: 0.86rem !important;
}

.stButton > button, .stFormSubmitButton > button {
  border-radius: 12px; font-weight: 700; padding: .6rem 1.15rem; border: 1.5px solid var(--line);
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"], .stFormSubmitButton > button {
  background: var(--teal); color: #fff !important; border-color: var(--teal);
}
.stButton > button:focus-visible, .stFormSubmitButton > button:focus-visible { outline: 3px solid var(--teal-soft); }

[class*="st-key-panel"] {
  background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 1.15rem 1.25rem 1.2rem;
}
.form-label {
  font-family: 'Fraunces', serif; font-weight: 700; font-size: 1.05rem; margin: 0.35rem 0 0.15rem;
}
[data-testid="stForm"] {
  background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 1.15rem 1.25rem;
}

[class*="st-key-mem-"],
[class*="st-key-gen-"] {
  background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 1rem 1.1rem; height: 100%;
}
[class*="st-key-mem-1"] { background: var(--teal-soft); border-color: #BFE4E4; }
[class*="st-key-mem-5"] { background: var(--amber-soft); border-color: #F0DDAE; }
.sec-title { font-family: 'Fraunces', serif; font-weight: 700; font-size: 1.08rem; margin: 0 0 .4rem 0; }
[class*="st-key-mem-"] li, [class*="st-key-mem-"] p,
[class*="st-key-gen-"] li, [class*="st-key-gen-"] p { line-height: 1.55; font-size: .94rem; }

.ready {
  background: var(--teal-soft); color: var(--teal-deep); border-radius: 12px;
  padding: 0.55rem 0.85rem; font-weight: 700; margin: 0.15rem 0 0.55rem;
}
.col-label { font-family: 'Fraunces', serif; font-weight: 700; font-size: 1.2rem; margin: .2rem 0 .55rem; }
.col-label span { display: block; font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 500; font-size: .8rem; color: var(--ink-soft); margin-top: 0.15rem; }

.mem { background: var(--card); border: 1px solid var(--line); border-left: 4px solid var(--teal);
  border-radius: 12px; padding: .75rem .9rem; margin-bottom: .5rem; font-size: .9rem; line-height: 1.5; }
.mem small { color: var(--ink-soft); font-weight: 700; letter-spacing: .03em; }
.mem.play { border-left-color: #C48A1A; }

.empty { text-align: left; padding: 1.3rem 1.3rem; color: var(--ink-soft); background: var(--card);
  border: 1.5px dashed var(--line); border-radius: var(--radius); }
.empty b { display: block; color: var(--ink); font-family: 'Fraunces', serif; font-size: 1.2rem; margin-bottom: .3rem; }
.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.7rem; margin-top: 0.8rem; }
.step { background: var(--paper); border-radius: 12px; padding: 0.8rem 0.85rem; }
.step b { display: block; font-size: 0.78rem; letter-spacing: 0.04em; text-transform: uppercase; color: var(--teal-deep); margin-bottom: 0.25rem; }
.step span { color: var(--ink); font-size: 0.9rem; line-height: 1.45; }

.promise-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 0.6rem; margin: 0.2rem 0 0.4rem; }
.promise { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: .8rem .95rem; }
.promise strong { display: block; margin-top: 0.35rem; line-height: 1.35; }
.section-label { font-family: 'Fraunces', serif; font-size: 1.15rem; font-weight: 700; margin: 0.6rem 0 0.35rem; }

.tl { position: relative; margin: .4rem 0 0 .55rem; padding-left: 1.5rem; border-left: 2px solid var(--line); }
.tl-item { position: relative; background: var(--card); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 0.95rem 1.1rem; margin-bottom: 0.85rem; }
.tl-item::before { content: ""; position: absolute; left: -2.15rem; top: 1.15rem; width: 12px; height: 12px;
  border-radius: 50%; background: var(--teal); border: 3px solid var(--paper); }
.tl-head { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; margin-bottom: .35rem; }
.tl-contact { font-weight: 700; }
.tl-item .tl-date { color: var(--ink-soft); font-size: .8rem; font-weight: 600; }
.badge { font-size: .72rem; font-weight: 700; padding: .18rem .55rem; border-radius: 999px; }
.b-call { background: #E3F4F4; color: #0A6E70; }
.b-demo { background: #E8ECFB; color: #3446A8; }
.b-email { background: #FCF3DF; color: #8A5A0E; }
.b-meeting { background: #F3E8FA; color: #6B2E97; }
.b-over { background: var(--red-soft); color: var(--red); }
.b-open { background: var(--amber-soft); color: var(--amber); }
.b-done { background: var(--teal-soft); color: var(--teal-deep); }
.tl-item p { margin: .28rem 0; line-height: 1.55; font-size: .92rem; }
.tl-item p b { color: var(--ink-soft); font-weight: 600; }

div[data-testid="stExpander"] {
  background: var(--card); border: 1px solid var(--line); border-radius: 14px;
}

@media (max-width: 800px) {
  .block-container { padding: 0.8rem 0.75rem 3rem; }
  .context h2 { font-size: 1.35rem; }
  .steps { grid-template-columns: 1fr; }
  .topbar { align-items: flex-start; flex-direction: column; }
  .stButton > button, .stFormSubmitButton > button { width: 100%; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
"""
