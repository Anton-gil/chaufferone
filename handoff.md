# Handoff: The Obligation Engine

**Hackathon track:** Fragmented Life Administration & Obligation Fatigue
**Working name:** TBD (this doc calls it "the Engine")
**Status:** Idea locked, nothing built yet
**Read time:** ~25 minutes. Sections 1–4 are mandatory for everyone. Sections 5 onwards are per-role.

---

## 0. The one-paragraph version

People don't miss deadlines because they lack reminders. They miss them because their obligations are tangled together and nobody untangles them. Rent competes with insurance for the same money. Insurance can't be renewed without a pollution certificate. An assignment deadline lands in the same week as a friend's birthday contribution. Every app today sends a separate alert for each of these, as if they had nothing to do with each other. We're building one engine that reads your email, SMS and WhatsApp, turns every message into an **obligation**, works out how the obligations affect each other, and hands you one sequenced plan. When money has to move, it asks you out loud first.

---

## 1. The exact problem we are solving

### 1.1 The problem statement (verbatim, this is our contract)

> "While isolated reminders exist, managing these overlapping obligations collectively creates severe cognitive fatigue, leading to missed deadlines, financial penalties, and lost savings. Existing solutions fail because they treat tasks as independent, isolated alerts rather than an interconnected ecosystem. There is no unified, proactive personal intelligence system capable of automatically aggregating, contextualizing, and sequencing obligations extracted across disparate communication channels into an intelligent timeline."

### 1.2 What that actually means, in plain words

Break the quote into its promises. Every feature we build has to trace back to one of these. If it doesn't, it gets cut.

| Phrase in the problem statement | What it means in real life | Which part of our system handles it |
|---|---|---|
| "overlapping obligations" | Things that collide: two bills in the same week, an exam and a vehicle service on the same day | The Sequencer |
| "missed deadlines" | You knew about it, you just started too late | Start-by dates (Section 3.4) |
| "financial penalties" | Late fees, lapsed insurance, fines for an expired PUC | Penalty-aware ordering + cash buffer (Section 3.5) |
| "lost savings" | Auto-renewing at a worse price, paying for a subscription you forgot | Cost reducers (Plugin P4) |
| "isolated alerts" | 30 separate pings from 12 apps | One timeline, one daily plan (Section 3.6) |
| "interconnected ecosystem" | Obligations depend on each other and share your money and time | The Obligation Graph (Section 3.3) |
| "automatically aggregating" | You shouldn't type anything in | Ingest (Section 3.1) |
| "contextualizing" | Knowing that *this* SMS is about *that* insurance policy | Extract + link (Section 3.2) |
| "sequencing" | Deciding what to do first, and when to start | The Sequencer (Section 3.4) |
| "disparate communication channels" | Gmail, SMS, WhatsApp, PDFs | Ingest (Section 3.1) |
| "proactive" | It comes to you before it's too late, not when you open the app | Event triggers + voice (Section 3.7) |
| "intelligent timeline" | One screen showing what to start today and why | Timeline (Section 3.6) |

### 1.3 Who it's for

**Primary persona: the student juggling everything for the first time.**
Example: Arun, 20, third-year engineering student in Chennai. He gets a monthly allowance plus some freelance income. His life includes:

- Assignments and exams (college LMS emails, WhatsApp class groups)
- Phone recharge, OTT subscriptions, hostel or PG rent
- A scooter: PUC certificate, insurance, service
- Documents: college ID, bus pass, passport application
- Social obligations: birthday contributions, trip splits, event RSVPs, all on WhatsApp

Arun doesn't miss things because he's lazy. He misses them because they're spread across five apps and he has to hold the connections in his head. That mental juggling *is* the "cognitive fatigue" in the problem statement.

**Secondary persona: any working adult.** The engine is the same. Only the plugins change (salary instead of allowance, EMIs instead of assignments). We pitch students because the problem is sharpest there and judges relate to it. We don't *limit* the product to students.

### 1.4 What already exists, and why it doesn't solve this

Details are in the research report. The short version:

- **Big-tech "proactive assistants"** (ChatGPT Pulse, Google's daily brief features) give you a morning summary. They don't model dependencies or money, and Pulse was shut down within a year. A summary isn't a plan.
- **Indian payment apps** (CRED, PhonePe, GPay) remind you about bills and do autopay. Each bill is handled on its own. None of them knows that paying rent today means insurance can't go through on Friday.
- **Subscription trackers** (Wallos, Rocket Money-style apps) track subscriptions only. That's one channel and one obligation type.
- **Calendars and to-do apps** only know what you typed in. They don't read your SMS, and they have no idea what anything costs.
- **Dead products are a warning:** Prism (bill pay) died with broken biller connections that caused late fees. Mint died when it turned into an ad business. Microsoft SMS Organizer, which parsed Indian bill SMS, is being shut down. That leaves a real gap in India.

**The honest baseline:** reminders plus autopay already solve about 70% of simple, fixed, recurring bills. We don't compete there. We win on the 30% that is **tangled**: things with prerequisites, things competing for the same money, and one-off obligations buried in messages.

---

## 2. The solution in one sentence

> **Every message becomes an obligation. Every obligation knows what it depends on and what it costs. You get one sequenced plan instead of thirty alerts, and nothing moves your money without your voice saying yes.**

### 2.1 Main solution vs. add-ons (the scoping rule)

- **CORE:** the engine that turns messages into obligations, connects them, and sequences them. If the core is missing, the product doesn't exist.
- **PLUGINS:** everything that *feeds* the engine new obligations, or *acts* on its plan. Plugins are optional, swappable and demo-able one at a time.
- **CUT:** anything that doesn't touch an obligation. (Example: general shopping deals. See Section 6.)

A simple test for the team. Before building a feature, ask: *"Does this create, connect, sequence or complete an obligation?"* If the answer is no, don't build it.

---

## 3. CORE: how the engine works

Seven parts in the order data flows through them. Each has a plain-English explanation first, then a "For builders" note.

```
 Gmail    SMS + pre-debit    WhatsApp + PDFs
    \           |                 /
     ----> 3.1 INGEST <----------
                |
           3.2 EXTRACT      (message -> obligation)
                |
           3.3 GRAPH        (obligations + how they connect)
                |
           3.4 SEQUENCER    (start-by dates, priorities)
           3.5 MONEY ENGINE (cash forecast + buffer)
                |
           3.6 TIMELINE     (one daily plan)
           3.7 VOICE CONSENT(talks before money moves)
                |
           3.8 VERIFY       (did it actually happen?)
```

### The one concept everyone must understand: the Obligation

An **obligation** is anything you owe the world by a certain time. It doesn't have to be money. Every obligation, whatever it is, gets the same fields:

| Field | Plain meaning | Example (scooter insurance) |
|---|---|---|
| What | What needs doing | Renew two-wheeler insurance |
| Due | The hard deadline | 18 Oct |
| Lead time | How long it takes to actually do | 1 day (online) |
| Needs first | Other obligations that must be done before this one | Valid PUC certificate |
| Costs | Money, time or effort it uses up | ₹1,850, 20 minutes |
| Penalty if missed | What happens if you blow it | Riding uninsured is illegal and risks a fine; lapsed policies lose the no-claim bonus |
| Source | Where we learned about it | Insurer email, 21 Sep |
| Confidence | How sure we are that we read it correctly | 0.92 |
| Status | Where it is in its life | Detected → Planned → Approved → Paid → Confirmed |

**Why this matters:** once a bill, an assignment, a PUC test and a birthday contribution all have the *same shape*, the engine can compare them and connect them. Existing apps can't do that, because each one stores its own kind of thing differently.

> **For builders:** One `Obligation` table in SQLite. `type` is an enum (`payment`, `document`, `task`, `event`, `renewal`). `depends_on` is a list of obligation IDs. `resources` is a JSON field like `{"inr": 1850, "minutes": 20}`. Keep the schema boring and versioned from day one (Alembic migrations) because plugins and updates depend on it.

---

### 3.1 INGEST: reading your channels

**Plain version:** The engine quietly reads the places where obligations arrive, so you never have to type them in.

| Channel | What it catches | How we get it |
|---|---|---|
| Gmail | Bills, renewal notices, college emails, bookings, invoices | Gmail API with read-only access, filtered to likely senders and keywords |
| SMS (Android) | Bank debits, UPI AutoPay **pre-debit notices**, bill alerts, OTP-free transaction messages | Android companion app reads SMS on the phone |
| WhatsApp | Class group deadlines, party plans, "send ₹500 for the gift", trip splits | Android notification reading, or a manual "Export chat" import (no official API exists for personal chats) |
| PDFs and images | Insurance policies, fee receipts, RC, PUC certificate | Upload or email attachment, read with OCR |

**The India-specific goldmine:** RBI rules require your bank to send a **pre-debit notice at least 24 hours before every auto-debit** (UPI AutoPay / e-mandate). That SMS is a structured, legally required warning that money is about to leave. Nobody else builds around it. We treat it as a first-class signal.

> **For builders:**
> - Gmail: OAuth with `gmail.readonly`, pull only messages matching sender/keyword filters so we don't process the whole inbox. Note: Google treats Gmail read scopes as restricted. For the hackathon, run it as a test app with your own accounts.
> - SMS: Kotlin companion app with a `READ_SMS` / `RECEIVE_SMS` broadcast receiver, pushing to the local engine over the LAN. **Sideloaded APKs that request SMS access are auto-blocked by Play Protect in India** when installed from a browser, chat app or file manager. For the demo, install via `adb` or Android Studio. For real users it has to go through the Play Store (see Section 7).
> - WhatsApp: a `NotificationListenerService` catches incoming message previews. The fallback is parsing `.txt` chat exports. Don't touch unofficial WhatsApp Web automation libraries, because they risk account bans.
> - PDFs: doctr or paperless-gpt style OCR, then pass the text to Extract.

---

### 3.2 EXTRACT: turning a message into an obligation

**Plain version:** A message like *"Your policy 2231xx expires on 18/10/2026. Renew now to keep your NCB"* becomes a clean obligation card: *Renew scooter insurance, due 18 Oct, ~₹1,850, penalty: lose no-claim bonus.* The engine also recognises when two messages are about the same thing (the insurer's email and their SMS reminder) and merges them into one card instead of two alerts.

This is the "contextualizing" part of the problem statement. Three jobs:

1. **Pull out the facts:** what, when, how much, who.
2. **Merge duplicates:** five reminders about one bill = one obligation, with five sources attached.
3. **Link to what we already know:** this SMS about ₹1,850 matches that insurance obligation; this debit SMS means that bill is now paid.

**When it's unsure,** it doesn't guess silently. The card shows up as "needs a quick check", and you confirm with one tap or one word.

> **For builders:**
> - Two-stage extraction. First, fast rules (regex templates for common Indian bank and biller SMS formats, `dateparser` for dates). Then an LLM for everything the rules miss, prompted to return strict JSON matching the Obligation schema.
> - Dedup key: `(counterparty, amount ±5%, due ±3 days)`, plus an LLM tie-breaker for fuzzy matches.
> - Store `confidence`. Anything below about 0.75 goes to a review queue instead of the plan.
> - No maintained open-source Indian bank-SMS parser exists. **We are building one.** That is itself a contribution worth mentioning in the pitch.

---

### 3.3 GRAPH: how obligations connect

**Plain version:** This is our core idea. Obligations are not a list. They form a web. The engine knows four kinds of connections:

| Connection | Plain meaning | Example |
|---|---|---|
| **Needs first** | B can't happen until A is done | PUC certificate → insurance renewal (required by Supreme Court / IRDAI rules) |
| **Shares money** | A and B draw from the same pocket | Rent and insurance both come from the allowance that lands on the 1st |
| **Shares time** | A and B compete for the same hours or day | Assignment submission vs. vehicle service appointment |
| **Same trip** | A and B can be done together to save effort | PUC test and scooter service at the same garage |

**Why judges should care:** no reminder app has "needs first" or "shares money" connections. Those two edges are the whole difference between an *isolated alert* and an *interconnected ecosystem*, which is the exact failure the problem statement names.

Where connections come from:
- **Built-in knowledge packs:** e.g. "insurance renewal for a vehicle needs a valid PUC" ships with the app.
- **Automatically:** anything paid with money is linked to the income it will come from.
- **From the user:** "don't book anything on exam days" becomes a time rule.

> **For builders:** Adjacency list in SQLite (`edges` table: `from_id`, `to_id`, `kind`). Load it into `networkx` in memory for planning. The graph for one person is tiny (hundreds of nodes), so don't over-engineer it. Knowledge packs are versioned JSON rule files, and they're also what paid updates deliver (Section 7.6).

---

### 3.4 SEQUENCER: what to start, and when

**Plain version:** Normal apps remind you on the due date. By then it's too late if something else has to happen first. We borrow a trick from **factory planning** (called *backward scheduling*): start from the deadline and walk backwards through every prerequisite to find the **latest safe start date**.

**Worked example:**
- Insurance due 18 Oct. Renewal takes 1 day.
- It needs a valid PUC. Your PUC expired. Getting one takes 1 day (you need a free afternoon to ride to a test centre).
- Add 2 days of safety margin.
- **Start-by date = 14 Oct.** That's when you get told, not 17 Oct.

Then it decides **priority** when several things are due around the same time. Plain rule:

> **Priority = how likely you are to miss it × how much it hurts to miss it ÷ how much effort it takes**

A ₹50 late fee on an easy bill ranks below a lapsed insurance policy, even if the bill is due sooner.

It also does **bundling**, borrowed from pharmacies. Pharmacies line up all your medicine refills on the same day, and that measurably helps people stay on track. We do the same: small admin tasks get grouped into one "admin slot" (for example, the day your allowance lands) instead of 30 pings across the month.

> **For builders:**
> - `start_by = due - lead_time - sum(lead_time of unfinished prerequisites along the longest chain) - margin`. That's a longest-path calculation over the DAG. Detect cycles and reject them.
> - `priority = p_miss * penalty_inr / effort_minutes`. `p_miss` starts as a heuristic (days of slack, past behaviour) and can later be learned.
> - Bundling: group obligations whose windows overlap and whose `location` or `channel` match, then snap the group to the nearest "admin slot" (allowance day, or a weekend slot the user picks).

---

### 3.5 MONEY ENGINE: the hero of the demo

**Plain version:** This is the part that makes the whole ecosystem feel connected. It answers: *"If I pay this today, what happens to everything else I owe this month?"*

**How it works, step by step:**

1. **Money comes in.** The engine knows when your allowance, salary or stipend usually lands (it learns this from bank SMS).
2. **Buffer comes off the top first.** Your emergency buffer is set aside *before* anything else is planned. It's not whatever's left over. It's protected from the start.
3. **Forecast.** It plays your month forward day by day: money in, every planned payment out, what your balance will be each day.
4. **Detect clashes early.** If the forecast shows your balance dipping into the buffer on some future day, you're told *now*, weeks ahead, while you still have options.
5. **Propose, don't dictate.** It offers concrete fixes, ranked by what they cost you:
   - Move a payment a few days (if the due date allows)
   - Pause a subscription you haven't used
   - Split a payment
   - Pay the bigger-penalty item first and defer the smaller one
6. **You choose (by voice).** Then it re-plans everything instantly.

**The buffer has two layers:**

| Layer | What it is | What happens when it's touched |
|---|---|---|
| **Hard floor** | Untouchable emergency money. User sets it (e.g. ₹3,000). | The engine will never plan anything that dips into it. Ever. |
| **Soft cushion** | A layer above the floor that absorbs small surprises. | If the forecast eats into it, that's the early warning. You're told weeks ahead, not on the day. |

**Why this solves the "people abandon the system" problem:** The worst moment for any finance app is when it says "insufficient funds" and you're stuck. Our engine is designed so you **never arrive at that moment**. It sees the squeeze coming weeks earlier and hands you options while you still have them. It only commits money it can already see is covered.

**Rules about moving money automatically:**
- **Standing rules run silently.** Once you've approved "same payee, same amount, every month" (e.g. Netflix ₹199), it doesn't ask again. You're told in the daily summary.
- **Everything else asks you by voice first.** New payee, changed amount, anything the engine is *rescheduling*.
- **If you don't answer, it never guesses.** It re-asks later. Close to the deadline, it escalates (voice call, then a WhatsApp message). It never pays or skips on its own.
- **It asks before the bank's 24-hour pre-debit window closes.** Otherwise the conversation is pointless, because the money is already committed.

> **Legal facts the team must know (verify before pitching):**
> - UPI AutoPay / e-mandate: banks must send a pre-debit notice ≥24h before each debit. Recurring debits up to ₹15,000 don't need your PIN each time. RBI raised this to ₹1 lakh for **insurance premiums, mutual funds and credit card bills** (Dec 2023).
> - **We cannot reschedule a biller's autopay ourselves.** Mandates live with the biller and your UPI app. What we *can* do is: (a) pay manually on a better date via a UPI payment link, which you confirm with your PIN, or (b) tell you to pause or modify the mandate in your UPI app. Be honest about this in the pitch. It's a strength ("we never touch your bank credentials"), not a weakness.

> **For builders:**
> - Cash forecast = a daily simulation for the next 45 days. `balance[d+1] = balance[d] + income[d] - planned_debits[d]`. The constraint is `balance[d] >= hard_floor` for all d.
> - Clash resolution: greedy search over candidate moves (defer by k days within the due window, pause, split), scored by `added_penalty + user_disruption`. Return the top 3 as options. No fancy solver needed at this scale. OR-Tools CP-SAT is a stretch goal.
> - Soft cushion size = something like the 80th percentile of unplanned spending over the last 60 days. For v1, a flat user-chosen number is fine.

---

### 3.6 TIMELINE: one screen, one plan

**Plain version:** The only screen you really need. Not a list of 30 alerts, but:

- **Today:** what to *start* today (not what's due today), in priority order, with one line on *why* ("Start PUC today, because insurance depends on it")
- **This week:** what's coming, grouped into bundles
- **Money strip:** a simple line showing your projected balance across the month, with the buffer drawn as a floor line
- **Needs a check:** anything the engine wasn't sure it read correctly
- **Done and verified:** things that are actually confirmed paid or submitted

Every card has a **"why"** line and a **"where from"** link (the original email or SMS). That's what makes people trust it: you can always see its reasoning.

Everything is also pushed into Google Calendar as events at the **start-by date**, so it shows up where people already look.

> **For builders:** React (or plain HTML + HTMX) served by the local FastAPI backend. Calendar export via the Google Calendar API or a subscribable `.ics` feed. The money strip is a single line chart with the buffer as a horizontal band.

---

### 3.7 VOICE CONSENT: it talks before money moves

**Plain version:** A notification saying "Pay ₹1,850?" gets tapped half-asleep without thinking. A short voice conversation forces you to actually hear the trade-off. So whenever the engine wants to move money (outside standing rules) or reschedule something, it **talks to you**.

**Example conversation (demo script):**

> **Engine:** "Hey Arun. Your allowance lands tomorrow, but rent and your scooter insurance both want it this week. If I pay both, you'd dip ₹900 into your emergency buffer on the 6th. Insurance isn't due till the 18th, and you need a PUC first anyway. I'd pay rent now, get the PUC done Saturday, and pay insurance on the 14th. That costs you nothing. Okay?"
> **Arun:** "Yeah, but do the PUC Sunday, I've got a lab Saturday."
> **Engine:** "Done. PUC Sunday, insurance on the 14th. Nothing touches your buffer."

**When it speaks vs. stays quiet:**

| Situation | What it does |
|---|---|
| Standing rule, nothing changed | Silent, appears in the daily summary |
| New payee / amount changed / rescheduling | Voice conversation |
| A clash that touches the soft cushion | Voice conversation with options |
| Low-confidence extraction | Silent card in "Needs a check" |
| You don't respond | Re-ask later. Escalate close to the deadline. Never act alone. |

You can also **start** the conversation yourself: "What do I owe this week?", "Can I afford the Goa trip?", "Move my phone bill to after the 5th."

> **For builders:**
> - Speech-to-text: `faster-whisper` (local). Text-to-speech: Piper or Kokoro (local, fast). The "brain" is an LLM with tool calls into the engine: `get_plan()`, `simulate(move)`, `approve(id)`, `defer(id, days)`.
> - **The LLM never computes money itself.** It only calls the engine's functions and reads back their results. This prevents hallucinated numbers.
> - Log every consent with a timestamp and the exact wording spoken. That's our audit trail.

---

### 3.8 VERIFY: closing the loop

**Plain version:** Reminding someone isn't the same as it getting done. Prism (the dead bill-pay app) showed "paid" while payments were actually failing, and users got hit with late fees. Our engine only marks something done when it sees **proof**.

Every money obligation moves through these stages, borrowed from how company accounts departments check invoices (matching the bill, the order and the payment):

```
Detected → Planned → Approved → Pre-debit notice seen → Debit SMS seen → Receipt / confirmation email seen = VERIFIED
```

If a stage doesn't happen on time (e.g. the pre-debit notice arrived but no debit followed), the engine flags it: *"Your insurance payment didn't go through. Retry?"*

Non-money obligations work the same way: an assignment becomes "verified" when the LMS confirmation email arrives, and a PUC becomes verified when you upload or photograph the certificate.

> **For builders:** A state machine on `Obligation.status`, with a timeout per stage. The matching logic is similar to Actual Budget's schedule-to-transaction matching (worth reading their code).

---

## 4. The hero demo (what judges will see)

**One chain, end to end, done properly.** Don't try to show every feature shallowly.

1. **Setup (30s):** Arun's phone and Gmail are connected. The timeline shows 14 obligations pulled automatically from email, SMS and WhatsApp. Nothing was typed in.
2. **The web (30s):** Click the insurance card. It shows "needs first: PUC (expired)" and "shares money with: rent, birthday contribution". Point out that no other app knows this.
3. **The clash (45s):** A pre-debit SMS arrives live (we trigger it) for an OTT renewal. The forecast line dips toward the buffer on the 6th.
4. **The call (60s):** The engine speaks, explains the clash, proposes a fix. Arun changes the PUC day by voice. The timeline re-plans live.
5. **The proof (30s):** A debit SMS plus a receipt email arrive. The card moves to "Verified".
6. **The close (15s):** "Thirty alerts became one plan. Nothing moved without his voice. Nothing left his phone."

**Build priority:** if time runs short, protect steps 2–4. That's the problem statement on screen.

---

## 5. PLUGINS: the add-ons

Plugins either **feed the engine** new obligations or **act on its plan**. They never run their own separate logic outside the engine. That's what keeps the architecture clean and stops it from feeling like "too much is going on".

**Plugin contract (what every plugin is allowed to do):**
- Read the obligations it has permission for
- Create new obligations or connections
- Propose actions (which still go through voice consent if money moves)
- Nothing else. No direct internet access unless declared and approved (see Section 7).

### P1. Payments (acts on the plan)
**Plain:** When you approve a payment, this plugin opens your own UPI app with everything pre-filled (payee, amount, note). You confirm with your PIN. We never hold your bank details.
**Why it's a plugin, not core:** the engine is valuable even if you pay manually. Payment is just one way to act on the plan.
> **Builders:** `upi://pay?pa=...&am=...&tn=...` intent links. BBPS biller deep-links where available. No payment aggregator, no merchant account, no money ever passes through us.

### P2. Student pack (feeds obligations)
**Plain:** Pulls assignments, exam dates and fee deadlines from college emails, Google Classroom and WhatsApp class groups. Adds time connections, e.g. "don't schedule a vehicle service in exam week".
> **Builders:** Google Classroom API for coursework. Email templates for common LMS notifications. WhatsApp group parsing for "submit by…" messages.

### P3. Social and events (feeds obligations)
**Plain:** Reads WhatsApp for parties, trips and gatherings, and turns them into obligations with **both** a time part and a money part: RSVP by Thursday, ₹500 gift contribution by Friday, trip split ₹2,400 due after the trip. These compete with everything else for the same money, which is exactly the "interconnected" part.
> **Builders:** LLM extraction over group messages with patterns like "send", "contribute", "₹", "who's coming", "split". Low confidence by default, so they go to "Needs a check".

### P4. Cost reducers / "lost savings" (acts on existing obligations)
**Plain:** When an obligation that costs money is coming up, this plugin looks for a cheaper way to meet *that specific obligation*:
- Insurance renewing in 20 days → compare renewal quotes
- Phone plan renewing → flag a cheaper plan with the same data
- Subscription you haven't used in 60 days → suggest pausing before the next charge
- Bills that offer a card or wallet cashback → mention it on the payment card

**The rule:** it **only** searches for offers tied to an obligation that already exists in the graph. It doesn't go looking for random deals. That's what keeps it inside the problem statement ("lost savings") instead of turning into a deals app.
> **Builders:** Per-category scrapers or APIs, triggered only by an existing obligation's `start_by` date. Cache results. Show them as a side note on the obligation card, never as a separate feed.

### P5. Vehicle and documents pack (feeds obligations + connections)
**Plain:** Tracks RC, PUC, insurance, licence and service intervals. Ships the "needs first" chains (PUC → insurance). Reads certificate photos to set the expiry dates automatically.
> **Builders:** OCR on uploaded certificates. Optional sync with LubeLogger (open source, has an MCP server) for service history. Knowledge pack = versioned JSON rules.

### P6. Spending insights (reads the plan)
**Plain:** Simple, honest views: where money went this month, which subscriptions are dead weight, how close you came to your buffer. It's advice, not automation.
> **Builders:** Aggregations over verified debits. No ML needed for v1.

### Build order for plugins
P1 (payments) and P5 (vehicle chain) are needed for the hero demo. P2 and P3 make the student story land. P4 and P6 come after the core is solid.

---

## 6. What we are NOT building (and why)

| Cut | Why |
|---|---|
| General shopping deals / sale finder ("find cheap headphones") | Doesn't touch an obligation. Judges will read it as scope creep. P4 covers the in-scope version. |
| A chatbot you ask random questions | Voice exists only to discuss the plan and consent to it. It's not a general assistant. |
| Holding or moving money ourselves | Needs licences we don't have, destroys the privacy story, and repeats Prism's failure. |
| Account Aggregator integration (for now) | Requires a regulated partner (FIU). Great later, not needed to prove the idea. |
| A "Jarvis" persona / branding | Judges have seen it many times. Pitch the engine, not the personality. |
| Unofficial WhatsApp automation | Risks bans on users' accounts. We only use notification reading and chat exports. |

---

## 7. SECURITY (secondary, but planned)

Security is not the headline. Privacy is a supporting reason to trust the engine. The approach is **"can't see it"**, not "promise not to look".

### 7.1 The principle: your data stays on your device

**Plain:** Everything (reading messages, understanding them, planning, voice) runs on the user's own laptop or phone, or on a server *they* own. Our company never receives their messages or financial data. That's not a policy promise. There's simply no server of ours for the data to go to.

What leaves the device, and why:

| Leaves the device | Why | Contains personal data? |
|---|---|---|
| License check (once, at activation) | Prove you've paid | No, just a license ID |
| Update downloads | New knowledge packs, bank SMS formats, bug fixes | No, it's a download, not an upload |
| Encrypted sync (optional, paid) | Keep phone and laptop in sync | Only scrambled data we can't read |
| Cost-reducer lookups (P4) | Check a price | Only the item category, never your identity |
| Gmail / Calendar API | Reading and writing *your own* Google account | Goes between you and Google directly, never through us |

### 7.2 Make privacy checkable, not just claimed

**Plain:** Hiding our code would make it *impossible* for anyone to check our privacy claim, and it would make our app look like malware to antivirus software. So we do the opposite:
- **Inspectable client:** the core engine is open for inspection (open-core model).
- **Network log screen:** an in-app page listing every single outbound connection the app has made, when, and why. Users can see for themselves that nothing leaves.
- **No obfuscation, no anti-VM tricks.** These were in the original plan and are dropped. They break self-hosting on a VPS (a VPS *is* a virtual machine), break WSL and some Windows 11 laptops, and they're the exact traits antivirus tools use to flag banking trojans.

### 7.3 Plugins can't leak data

**Plain:** The real risk isn't someone reverse-engineering our app. It's a plugin quietly sending data somewhere. So plugins run in a locked box: no internet by default, and they only see the obligation types they asked for. Like Android app permissions, the user approves each plugin's access.
> **Builders:** Plugins run as WASM modules (e.g. via Extism/wasmtime) or in separate processes with no network. They talk to the core only through a small API. Each plugin has a manifest declaring its permissions: `reads: [payment]`, `network: [policybazaar.com]`.

### 7.4 Data at rest

- The local database is encrypted with a key held in the OS keychain.
- Raw messages are processed and then kept only as long as needed (default 90 days). The obligation cards are kept.
- One-tap "export everything" (plain JSON) and "delete everything".

### 7.5 Licensing without a kill switch

**Plain:** Life-admin apps die a lot (Prism, Mint, SMS Organizer). If our company disappears, users' installed copies must **keep working**.
- On payment, the user receives a **signed license file**. The app checks it **offline** using a public key, with no phone-home needed.
- It's tied to the user, not to hardware fingerprints, so a new laptop or a migrated VPS doesn't mean a support ticket.
- User data lives in an open, versioned format, **separate from the license**. An expired license stops updates, never access to your own data.
> **Builders:** Ed25519-signed JSON license (`user_id`, `plan`, `updates_until`). The public key is embedded in the app.

### 7.6 How we make money without DRM

**Plain:** You can't stop determined people from copying software that runs on their own machine, so we don't try. We charge for things that can't be copied:
- **Update stream (main revenue):** bank SMS formats, biller lists, RBI rules and knowledge packs keep changing, so an unpaid copy slowly gets worse at reading your messages. Same model as antivirus software selling virus definitions.
- **Encrypted multi-device sync:** our server only ever holds scrambled data.
- **Premium plugin packs and priority support.**

### 7.7 Distribution reality check

- **Desktop / VPS:** normal installer or Docker image. No anti-VM checks, so self-hosting just works.
- **Android companion (SMS / notifications):** has to go through the **Play Store**. Play Protect in India auto-blocks sideloaded apps from browsers, chat apps and file managers when they ask for SMS or notification access. The Play Store also has strict rules on SMS permission, so we need to qualify under a permitted use case. **Check this before building the Android side for real users.** For the hackathon, install via `adb`.
- **Law:** because personal data never reaches our servers, our obligations under India's DPDP Act are much lighter than a cloud app's. Check with someone qualified before claiming this in writing.

---

## 8. Architecture summary (for builders)

| Layer | Tech | Runs where |
|---|---|---|
| Ingest | Gmail API, Kotlin Android companion (SMS + notification listener), PDF upload | Phone + local engine |
| Extract | Regex templates + `dateparser` + local LLM (Ollama / llama.cpp), strict JSON output | Local engine |
| Store | SQLite (encrypted), Alembic migrations | Local engine |
| Graph + Sequencer + Money engine | Python, `networkx`, plain simulation (OR-Tools optional) | Local engine |
| API | FastAPI | Local engine |
| Timeline UI | React or HTMX | Browser on laptop / phone |
| Voice | `faster-whisper` + LLM tool-calling + Piper/Kokoro | Local engine |
| Calendar | Google Calendar API / `.ics` feed | Local engine → user's Google |
| Payments | UPI intent links | User's UPI app |
| Plugins | WASM or sandboxed processes, permission manifests | Local engine |
| Licence | Ed25519 signed file, offline check | Local engine |

Local-first note for the demo: if laptops can't run a local LLM fast enough, use a hosted LLM **only for the demo** behind a clearly labelled switch, and say so honestly. The architecture doesn't change.

---

## 9. Team split (by role)

| Role | Owns | Hero-demo deliverable |
|---|---|---|
| Ingest & Extract | Gmail pull, Android SMS/notification bridge, SMS templates, LLM extraction, dedup | 14 real obligations appear with zero typing |
| Engine | Obligation schema, graph, sequencer, money forecast, clash options, verify state machine | The clash is detected and 3 options are generated |
| Voice & UI | Timeline, money strip, voice loop, consent log | The live call re-plans the timeline |
| Plugins & Pitch | P1 payments, P5 vehicle chain, demo data, deck, script | The PUC→insurance chain and the 3-minute story |

---

## 10. Phases (no ceiling, just order)

1. **Hackathon build:** Core 3.1–3.8 + P1 + P5, the hero demo working on real data from the team's own accounts.
2. **Right after:** P2, P3, the plugin sandbox, the network log screen, signed licenses.
3. **Product:** Play Store Android app, P4 cost reducers, encrypted sync, on-device learning of `p_miss` and lead times, Account Aggregator via a licensed partner.

---

## 11. Glossary (plain English)

- **Obligation:** anything you owe by a certain time: money, a document, a task, an RSVP.
- **Start-by date:** the latest day you can begin and still make the deadline, counting everything that has to happen first.
- **Backward scheduling:** planning from the deadline backwards, as factories do.
- **Buffer (hard floor / soft cushion):** emergency money the engine never plans to touch / the warning layer above it.
- **Pre-debit notice:** the SMS your bank must send at least 24 hours before an auto-debit.
- **UPI AutoPay / e-mandate:** permission you give a biller to debit you on a schedule.
- **Standing rule:** a payment you've approved once to repeat without asking (same payee, same amount).
- **Verify / closing the loop:** marking something done only when there's proof it happened.
- **Plugin:** an add-on that feeds or acts on the engine, in a locked box.
- **Local-first:** the software runs on your device, and your data stays there.
- **Knowledge pack:** a downloadable rules file (e.g. "PUC is needed before insurance", Indian bank SMS formats).
- **DAG / graph:** the web of obligations and how they connect.
- **PUC:** Pollution Under Control certificate for vehicles.
- **BBPS:** Bharat Bill Payment System, the national bill-payment network.
- **Account Aggregator (AA):** RBI's consent-based financial data-sharing system. It needs a licensed partner, so it's a later phase.
- **DPDP Act:** India's Digital Personal Data Protection law.
