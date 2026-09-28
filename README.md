# DealRecall

A sales copilot that briefs a rep from memory, not from a blank chat. It remembers every touch on a deal, and it remembers which objection-handling tactics won or lost on other deals.

The demo account is **Northwind Logistics**. The CFO call is 30 September 2026. Two promises are already overdue. A cheaper competitor, CargoFlow, demoed last week. The same pricing move lost Kaveri Retail. The opposite move won Meridian Health.

## How Hindsight is used

Memory is the briefing, not a side feature.

| Step | What happens |
| --- | --- |
| Retain | Each call, demo, and email is stored in a bank named `dealrecall`, tagged `deal:<slug>`, with the real date, the company, and the people. Wins and losses also write a playbook lesson tagged `playbook`. |
| Recall | Before it writes, the agent calls `recall_deal`, `recall_playbook`, and `list_open_promises`. Deal recall cannot see other deals. Playbook recall is how a new call learns from an old one. |
| Reflect | A separate action asks the bank itself to reason over that history. The bank mission tells it to cite the deal a tactic came from and to say when it does not know. |

A **Compare with no memory** button asks the same question with the tools turned off. The generic brief is not allowed to invent Priya, Raj, CargoFlow, or the Meridian pilot.

If Groq rejects a tool call, or the model sends bad arguments, the error goes back to the model so it can retry. If function calling fails outright, the agent recalls Hindsight itself and still writes the brief. The expander **How the agent used memory** shows that trace.

## Setup

Python 3.11 or newer.

```bash
pip install -r requirements.txt
copy .env.example .env
```

Fill in `.env`:

- `GROQ_API_KEY` from [Groq](https://groq.com/). Default model is `qwen/qwen3-32b`. `openai/gpt-oss-120b` also works.
- `HINDSIGHT_API_KEY` from [Hindsight Cloud](https://ui.hindsight.vectorize.io). After you register, promo code `MEMHACK99` adds $50 in credits under billing.

```bash
python app.py
```

The first launch retains the sample pipeline (13 interactions and 4 playbook lessons). That call can take a few minutes. Later launches reuse the same document ids, so they update memory instead of duplicating it.

## 60-second demo

1. Open the app on **Northwind Logistics**. Leave the question about the 30 September call with Anil Deshpande.
2. Click **Compare with no memory**. The right side is a generic checklist. The left side should name Priya Shah, Raj Malhotra, the overdue security brief, CargoFlow, and what Meridian did instead of discounting.
3. Open **How the agent used memory** and **Memories used** so the recall is visible.
4. Open **Memory** and recall the deal beside the playbook.
5. Open **Timeline** and show the two overdue promises.
6. To show it learning: open **Log a call**, note that the two-page security brief was sent to Raj, mark that promise kept, then generate the briefing again. The overdue item should be gone and the new fact should be in the brief.

## Layout

- `app.py` — Streamlit UI
- `dealrecall/memory.py` — Hindsight retain, recall, reflect
- `dealrecall/agent.py` — Groq tool loop
- `dealrecall/store.py` — local timeline and promises (SQLite in `data/`)
- `dealrecall/seed.py` — the sample pipeline
- `tests/test_core.py` — deal matching, tool errors, section parsing

```bash
python -m unittest tests.test_core
```

The local database is only the timeline the rep looks at. If a save cannot reach Hindsight, the screen says so. It does not pretend the note was remembered.
