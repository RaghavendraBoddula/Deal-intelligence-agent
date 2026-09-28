"""Sample pipeline. Same records feed the local CRM and the Hindsight bank."""

from __future__ import annotations

DEALS = [
    {
        "slug": "northwind-logistics",
        "name": "Northwind Logistics",
        "stage": "Commercial review",
        "value_inr": 1_800_000,
        "segment": "3PL and warehousing",
    },
    {
        "slug": "meridian-health",
        "name": "Meridian Health",
        "stage": "Closed won",
        "value_inr": 2_200_000,
        "segment": "Multi-clinic hospital group",
    },
    {
        "slug": "kaveri-retail",
        "name": "Kaveri Retail",
        "stage": "Closed lost",
        "value_inr": 1_200_000,
        "segment": "Multi-store retail",
    },
    {
        "slug": "saffron-hotels",
        "name": "Saffron Hotels",
        "stage": "Discovery",
        "value_inr": 900_000,
        "segment": "Regional hotel group",
    },
]

# result: advanced | open | won | lost
INTERACTIONS = [
    {
        "document_id": "seed-northwind-1",
        "deal_slug": "northwind-logistics",
        "happened_on": "2026-08-12",
        "contact": "Priya Shah (VP Operations)",
        "type": "Discovery call",
        "notes": (
            "Northwind runs four warehouses in Pune and Nagpur. Exception handling "
            "is a spreadsheet plus WhatsApp and takes about 11 hours a week. Priya "
            "Shah owns operations and has budget authority up to Rs 20 lakh, but the "
            "CFO signs anything annual. She is worried onboarding will take her floor "
            "leads off the dock for a month. No competitor named yet."
        ),
        "outcome": "Demo booked for 21 August with operations and IT security.",
        "tactic": "",
        "result": "advanced",
        "people": ["Priya Shah"],
    },
    {
        "document_id": "seed-northwind-2",
        "deal_slug": "northwind-logistics",
        "happened_on": "2026-08-21",
        "contact": "Priya Shah (VP Operations) and Raj Malhotra (IT Security Lead)",
        "type": "Product demo",
        "notes": (
            "Priya liked the warehouse exception workflow and asked for a customer "
            "in 3PL, not a generic retail logo. Raj Malhotra asked three things and "
            "would not move without them: SSO with Okta, SOC 2 Type II, and data "
            "residency in India. He said CargoFlow is already in a proof of concept "
            "and is about 30 percent cheaper. Priya did not defend the price on the call."
        ),
        "outcome": "Promised Priya a 3PL case study and Raj a security packet.",
        "tactic": "Showed the product workflow. Did not address price or security in the room.",
        "result": "advanced",
        "people": ["Priya Shah", "Raj Malhotra"],
    },
    {
        "document_id": "seed-northwind-3",
        "deal_slug": "northwind-logistics",
        "happened_on": "2026-09-02",
        "contact": "Priya Shah (VP Operations)",
        "type": "Follow-up email",
        "notes": (
            "Priya asked for 15 percent off if they prepay annually. She said CargoFlow "
            "has already offered that. We promised the 3PL case study to Priya and the "
            "security packet to Raj Malhotra before Friday 4 September. Neither has been sent."
        ),
        "outcome": "Waiting on us. Commercial conversation not scheduled yet.",
        "tactic": "",
        "result": "open",
        "people": ["Priya Shah", "Raj Malhotra"],
    },
    {
        "document_id": "seed-northwind-4",
        "deal_slug": "northwind-logistics",
        "happened_on": "2026-09-16",
        "contact": "Priya Shah (VP Operations)",
        "type": "Working session",
        "notes": (
            "Priya is still the champion. Raj has stopped replying because the security "
            "packet never arrived. Priya confirmed her CFO, Anil Deshpande, will join a "
            "commercial call on 30 September. She said Anil will lead with price. We still "
            "owe the case study and the security note. CargoFlow's demo is set for 25 September."
        ),
        "outcome": "Commercial call held for 30 September with Anil Deshpande.",
        "tactic": "",
        "result": "open",
        "people": ["Priya Shah", "Raj Malhotra", "Anil Deshpande"],
    },
    {
        "document_id": "seed-northwind-5",
        "deal_slug": "northwind-logistics",
        "happened_on": "2026-09-25",
        "contact": "Priya Shah (VP Operations)",
        "type": "Follow-up email",
        "notes": (
            "Priya wrote after the CargoFlow demo. She said their price is lower but the "
            "warehouse workflow felt generic and would not fit the Nagpur dock. She needs "
            "the 3PL case study before the Wednesday 30 September call or she cannot hold "
            "Anil. Raj is still silent. The security packet due 4 September is now three "
            "weeks late."
        ),
        "outcome": "Champion is intact. Two promises are overdue going into the CFO call.",
        "tactic": "",
        "result": "open",
        "people": ["Priya Shah", "Raj Malhotra", "Anil Deshpande"],
    },
    {
        "document_id": "seed-meridian-1",
        "deal_slug": "meridian-health",
        "happened_on": "2026-06-18",
        "contact": "Dr. Ananya Rao (COO)",
        "type": "Discovery call",
        "notes": (
            "Meridian Health runs nine clinics in Bengaluru. Nurses spend about six hours "
            "a week on referral paperwork. Dr. Ananya Rao is the COO and the champion. "
            "She warned that nothing moves without Meera Iyer, the CISO, and Vikram Shah, "
            "the CFO. Budget discussed around Rs 22 lakh."
        ),
        "outcome": "Security review scheduled with Meera Iyer.",
        "tactic": "",
        "result": "advanced",
        "people": ["Ananya Rao", "Meera Iyer", "Vikram Shah"],
    },
    {
        "document_id": "seed-meridian-2",
        "deal_slug": "meridian-health",
        "happened_on": "2026-07-02",
        "contact": "Meera Iyer (CISO)",
        "type": "Working session",
        "notes": (
            "We sent Meera a 40-page security PDF the morning of the review. She had not "
            "opened it. She asked for SSO, SOC 2 Type II, and whether patient data stays "
            "in India. The meeting ended with no approval."
        ),
        "outcome": "No decision. She asked for a shorter note before a second review.",
        "tactic": "Long security PDF delivered during the meeting. It failed.",
        "result": "open",
        "people": ["Meera Iyer"],
    },
    {
        "document_id": "seed-meridian-3",
        "deal_slug": "meridian-health",
        "happened_on": "2026-07-09",
        "contact": "Meera Iyer (CISO)",
        "type": "Follow-up email",
        "notes": (
            "Forty-eight hours before the second review we sent a two-page note only: "
            "SOC 2 Type II status, Okta SSO, and Mumbai region residency. Meera approved "
            "on the call and told Ananya she was unblocked."
        ),
        "outcome": "Security approval. Pricing moved to the CFO.",
        "tactic": "Two-page security brief sent 48 hours before the review.",
        "result": "advanced",
        "people": ["Meera Iyer", "Ananya Rao"],
    },
    {
        "document_id": "seed-meridian-4",
        "deal_slug": "meridian-health",
        "happened_on": "2026-08-04",
        "contact": "Vikram Shah (CFO) and Dr. Ananya Rao (COO)",
        "type": "Commercial call",
        "notes": (
            "Vikram asked for 20 percent off because CareStack was cheaper. We did not "
            "discount. We offered a 45-day paid pilot on two clinics and a named story "
            "about nurse admin hours, not a feature grid. He signed the Rs 22 lakh order "
            "form the same week."
        ),
        "outcome": "Closed won at list price.",
        "tactic": "Refused the discount. Offered a 45-day paid pilot and a workflow story.",
        "result": "won",
        "people": ["Vikram Shah", "Ananya Rao"],
    },
    {
        "document_id": "seed-kaveri-1",
        "deal_slug": "kaveri-retail",
        "happened_on": "2026-07-08",
        "contact": "Neha Kapoor (Head of Store Ops)",
        "type": "Discovery call",
        "notes": (
            "Kaveri Retail has 40 stores around Pune. Neha Kapoor likes the idea of "
            "cutting stock-count overtime. She is not the buyer. She said procurement "
            "and her director would decide. We never got that meeting."
        ),
        "outcome": "Second call booked with Neha only.",
        "tactic": "",
        "result": "advanced",
        "people": ["Neha Kapoor"],
    },
    {
        "document_id": "seed-kaveri-2",
        "deal_slug": "kaveri-retail",
        "happened_on": "2026-07-16",
        "contact": "Neha Kapoor (Head of Store Ops)",
        "type": "Product demo",
        "notes": (
            "Neha said CargoFlow had quoted 18 percent below us. On the call we matched "
            "it and offered 18 percent off for an annual prepay. We did not show a retail "
            "customer or ask to meet procurement. She said she would take the discount upstairs."
        ),
        "outcome": "Discount offered. No economic buyer in the room.",
        "tactic": "Opened with an 18 percent discount as soon as CargoFlow was named.",
        "result": "open",
        "people": ["Neha Kapoor"],
    },
    {
        "document_id": "seed-kaveri-3",
        "deal_slug": "kaveri-retail",
        "happened_on": "2026-07-28",
        "contact": "Neha Kapoor (Head of Store Ops)",
        "type": "Follow-up email",
        "notes": (
            "Neha wrote that procurement chose CargoFlow. The comparison they used was "
            "price only. She said she had liked our workflow but had nothing on paper to "
            "defend it, and her director never took a call."
        ),
        "outcome": "Closed lost to CargoFlow on price.",
        "tactic": "Discount-first. No customer story. Economic buyer never met.",
        "result": "lost",
        "people": ["Neha Kapoor"],
    },
    {
        "document_id": "seed-saffron-1",
        "deal_slug": "saffron-hotels",
        "happened_on": "2026-09-18",
        "contact": "Arjun Mehta (Director of Operations)",
        "type": "Discovery call",
        "notes": (
            "Saffron Hotels has six properties in Jaipur and Udaipur. Arjun Mehta said "
            "night audit takes two people until about 2am. He has not named a budget, a "
            "competitor, or a security stakeholder. He said he would introduce his general "
            "manager and has not done it."
        ),
        "outcome": "No next meeting on the calendar.",
        "tactic": "",
        "result": "open",
        "people": ["Arjun Mehta"],
    },
]

COMMITMENTS = [
    {
        "deal_slug": "northwind-logistics",
        "what": "Send Raj Malhotra a two-page security brief: Okta SSO, SOC 2 Type II, India residency",
        "who": "Raj Malhotra",
        "due_on": "2026-09-04",
        "status": "open",
    },
    {
        "deal_slug": "northwind-logistics",
        "what": "Send Priya Shah a 3PL case study before the 30 September commercial call",
        "who": "Priya Shah",
        "due_on": "2026-09-04",
        "status": "open",
    },
    {
        "deal_slug": "saffron-hotels",
        "what": "Ask Arjun Mehta for an introduction to the general manager",
        "who": "Arjun Mehta",
        "due_on": "2026-09-25",
        "status": "open",
    },
]

# Curated lessons. Tagged playbook so a new deal can recall what already won or lost.
PLAYBOOK = [
    {
        "document_id": "seed-playbook-discount",
        "happened_on": "2026-08-04",
        "content": (
            "Playbook, pricing. Do not open with a discount. On Kaveri Retail, lost "
            "28 July 2026, the rep offered 18 percent off on the second call as soon as "
            "Neha Kapoor named CargoFlow. Procurement compared price only and chose "
            "CargoFlow. On Meridian Health, won 4 August 2026, the team refused a 20 "
            "percent discount asked by CFO Vikram Shah and offered a 45-day paid pilot "
            "on two clinics instead. Meridian signed at the Rs 22 lakh list price."
        ),
    },
    {
        "document_id": "seed-playbook-security",
        "happened_on": "2026-07-09",
        "content": (
            "Playbook, security reviews. A long PDF delivered in the meeting does not "
            "get read. Meera Iyer, CISO at Meridian Health, ignored a 40-page security "
            "PDF on 2 July 2026. She approved after a two-page note, sent 48 hours before "
            "the next review, covering only SOC 2 Type II, SSO, and India data residency."
        ),
    },
    {
        "document_id": "seed-playbook-buyer",
        "happened_on": "2026-07-28",
        "content": (
            "Playbook, stakeholders. Deals stall when only the champion is in the room. "
            "Kaveri Retail was lost with Neha Kapoor as the only contact. Her director "
            "never took a call, and procurement picked CargoFlow. Meridian Health closed "
            "after the COO, the CISO, and the CFO were all in the commercial conversation."
        ),
    },
    {
        "document_id": "seed-playbook-competitor",
        "happened_on": "2026-08-04",
        "content": (
            "Playbook, competitors. When a cheaper competitor is in the deal, answer with "
            "hours saved in their actual workflow and a named customer in their industry. "
            "A feature comparison did not give Neha Kapoor anything she could defend at "
            "Kaveri Retail. Meridian Health moved when the story was nurse admin hours at "
            "clinics like theirs, not a module checklist."
        ),
    },
]


def deal_by_slug(slug: str) -> dict:
    for deal in DEALS:
        if deal["slug"] == slug:
            return deal
    raise KeyError(slug)


def interaction_content(item: dict) -> str:
    deal = deal_by_slug(item["deal_slug"])
    tactic = item["tactic"] or "None recorded."
    return (
        f"Deal: {deal['name']} ({deal['segment']}). "
        f"Stage context: {deal['stage']}. Value discussed: Rs {deal['value_inr'] // 100000} lakh.\n"
        f"Date: {item['happened_on']}. Type: {item['type']}.\n"
        f"Contacts: {item['contact']}.\n"
        f"Notes: {item['notes']}\n"
        f"Outcome: {item['outcome']}\n"
        f"Tactic tried: {tactic}\n"
        f"Result: {item['result']}."
    )


def memory_items() -> list[dict]:
    """Retain payloads. document_id makes a re-seed an upsert, not a duplicate."""
    items: list[dict] = []
    for item in INTERACTIONS:
        deal = deal_by_slug(item["deal_slug"])
        entities = [{"text": deal["name"], "type": "ORG"}]
        entities += [{"text": person, "type": "PERSON"} for person in item["people"]]
        items.append(
            {
                "content": interaction_content(item),
                "context": f"sales interaction on {deal['name']}",
                "timestamp": f"{item['happened_on']}T10:30:00Z",
                "document_id": item["document_id"],
                "tags": [f"deal:{item['deal_slug']}"],
                "metadata": {
                    "deal": deal["name"],
                    "deal_slug": item["deal_slug"],
                    "type": item["type"],
                    "result": item["result"],
                },
                "entities": entities,
                "resolve_entities": False,
            }
        )
    for lesson in PLAYBOOK:
        items.append(
            {
                "content": lesson["content"],
                "context": "sales playbook lesson learned from closed deals",
                "timestamp": f"{lesson['happened_on']}T18:00:00Z",
                "document_id": lesson["document_id"],
                "tags": ["playbook"],
                "metadata": {"kind": "playbook"},
                "resolve_entities": False,
            }
        )
    return items
