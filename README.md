# DealRecall

A sales copilot that briefs a rep from memory, not from a blank chat. It remembers every touch on a deal, and it remembers which objection-handling tactics won or lost on other deals.

The demo account is **Northwind Logistics**. The CFO call is 30 September 2026. Two promises are already overdue. A cheaper competitor, CargoFlow, demoed last week. The same pricing move lost Kaveri Retail. The opposite move won Meridian Health.

## How Hindsight is used

Memory is the briefing, not a side feature.

| Step | What happens |
| --- | --- |
| Retain | Each call, demo, and email is stored in a bank named `dealrecall`, tagged `deal:<slug>`, with the real date, the company, and the people. Wins and losses also write a playbook lesson tagged `playbook`. |
| Recall | **Brief from Memory** recalls the selected deal, then recalls playbook lessons from other deals. About 8–12 of those memories are sent to Groq. The rest stay in Hindsight. |
| Reflect | A separate action asks the bank itself to reason over that history. The bank mission tells it to cite the deal a tactic came from and to say when it does not know. |

**Compare with no memory** asks the same question with no Hindsight memories. That brief only has the company, segment, stage, and value.

The strip under the briefs shows how many memories were selected, for example “12 high-relevance memories selected from 52 recalled.” **How the agent used memory** is the step trace. **Read the selected memories** lists each one with its source deal.

## Setup

Python 3.11 or newer.

```bash
pip install -r requirements.txt
copy .env.example .env
```

Fill in `.env`:

`.env` is gitignored. Do not commit it.

- `GROQ_API_KEY` from [Groq](https://groq.com/). The model in `.env.example` is `openai/gpt-oss-120b`.
- `HINDSIGHT_API_KEY` from [Hindsight Cloud](https://ui.hindsight.vectorize.io). After you register, promo code `MEMHACK99` adds $50 in credits under billing.

```bash
python app.py
```

The first launch retains the sample pipeline (13 interactions and 4 playbook lessons). That call can take a few minutes. Later launches reuse the same document ids, so they update memory instead of duplicating it.

## 60-second demo

1. Open the app on **Northwind Logistics**. Leave the question about the 30 September call with Anil Deshpande.
2. Click **Brief from Memory**, then **Compare with no memory**. The left brief should name Priya Shah, Raj Malhotra, the overdue security brief, and CargoFlow. The right brief only knows the company record.
3. Read the selection strip, then open **How the agent used memory** and **Read the selected memories**.
4. Open **Memory** and recall the deal beside the playbook.
5. Open **Timeline** and show the two overdue promises.
6. To show it learning: open **Log a call**, note that the two-page security brief was sent to Raj, mark that promise kept, then generate the briefing again. The overdue item should be gone and the new fact should be in the brief.

## Layout

- `app.py` — Streamlit UI
- `dealrecall/memory.py` — Hindsight retain, recall, reflect
- `dealrecall/agent.py` — recall, select the short memory list, then ask Groq for the brief
- `dealrecall/store.py` — local timeline and promises (SQLite in `data/`)
- `dealrecall/seed.py` — the sample pipeline
- `tests/test_core.py` — deal matching, tool errors, section parsing

```bash
python -m unittest tests.test_core
```

The local database is only the timeline the rep looks at. If a save cannot reach Hindsight, the screen says so. It does not pretend the note was remembered.
