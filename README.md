<div align="center">
  <h1>Chaufferone</h1>
  <p><strong>The Obligation Engine</strong></p>
  <p>Turn chaotic SMS alerts, emails, and chats into one intelligent, sequenced plan.</p>
</div>

## 🚨 The Problem

While isolated reminders exist, managing overlapping obligations collectively creates severe cognitive fatigue. This leads to missed deadlines, financial penalties, and lost savings. Existing solutions fail because they treat tasks as independent, isolated alerts rather than an **interconnected ecosystem**.

There is no unified, proactive personal intelligence system capable of automatically aggregating, contextualizing, and sequencing obligations extracted across disparate communication channels into an intelligent timeline.

**Until now.**

## 💡 The Solution

**Every message becomes an obligation. Every obligation knows what it depends on and what it costs. You get one sequenced plan instead of thirty alerts. Your voice approves the plan; your UPI PIN approves every payment.**

Chaufferone (The Obligation Engine) reads your incoming channels (SMS, Gmail, WhatsApp), extracts the critical information, and calculates a sound daily plan.

### Core Features

- 📥 **Zero-Typing Ingestion:** Android SMS (live, including RBI-mandated pre-debit notices), SMS backup import, Gmail, `.eml` files, and WhatsApp chat exports.
- 🧠 **Smart Extraction:** Bank SMS are parsed by deterministic regex templates on your machine (HDFC, SBI, ICICI, Axis, Kotak formats). Emails and chats go through an LLM into a strict schema: due date, lead time, cost, penalty, dependencies.
- 🕸️ **Obligation Graph:** Knows that renewing your scooter insurance *requires* a valid PUC certificate (SC order, Aug 2017; IRDAI circulars 2018/2020), and which payments *share money* from the same allowance.
- 📅 **Backward-Scheduling Sequencer:** Works back from each deadline through its prerequisites to a planned date, and snaps "needs a free afternoon" tasks (PUC test) to a weekend.
- 💰 **Clash-Free Money Engine:** A 45-day daily forecast with a hard emergency floor. If anything would push you below it, you hear about it weeks early, with fixes that are each re-simulated before they're offered.
- 🎙️ **Voice Consent:** The engine speaks the trade-off; you answer ("first one, but do the PUC on Sunday"). Every change is validated against deadlines, prerequisite order, and the floor, and logged.
- ✅ **Verification Loop:** A payment is only "done" when the bank's own debit SMS matches it.

## 🏗️ Architecture

- **Backend:** Python 3.12–3.14, FastAPI, SQLAlchemy 2 + Alembic, SQLite
- **Graph & Engine:** NetworkX (dependency DAG), dateparser, rapidfuzz
- **Frontend:** Next.js (React) in `web/`
- **AI Stack:**
  - *Bank SMS:* regex templates, no LLM
  - *Email/WhatsApp extraction:* Anthropic Claude (hosted, labelled)
  - *Voice:* browser Web Speech API for speech-to-text and text-to-speech; replies parsed by rules first, hosted LLM only as a fallback (`VOICE_LLM_ENABLED`)
- **Mobile Bridge:** the open-source [SMS to URL Forwarder](https://github.com/bogkonstantin/android_income_sms_gateway_webhook) Android app, installed via `adb`, posting to the laptop over USB (`adb reverse tcp:8000 tcp:8000`)

## 🚀 How it Works (The Demo Flow)

1. **Ingest:** An SMS or email hits the server.
2. **Contextualize:** The system identifies a deadline, penalty, and cost.
3. **Sequence:** The item is scheduled based on dependencies.
4. **Forecast:** The Money Engine detects an upcoming shortfall (cash clash).
5. **Consent:** The voice assistant explains the clash and proposes fixes (e.g. pay insurance after your freelance money lands, or pause a subscription in your UPI app). You reply via mic.
6. **Verify:** The payment is made by scanning a generated UPI QR code in your own UPI app, and the engine verifies it with the matched bank debit SMS.

## 🔒 Privacy & Security

Your life administration belongs to you.
- **Local-First Engine:** The database, planning, money forecast, and bank-SMS parsing run on your own laptop. There is no Chaufferone server.
- **Labelled hosted AI:** Email and WhatsApp text is sent to a hosted LLM for extraction. For voice, only your spoken reply and obligation titles/dates are sent, and only when the rules can't understand you. Set `VOICE_LLM_ENABLED=false` to turn that off.
- **No Money Touching:** We never hold bank credentials or money. Payments happen in your own UPI app with your PIN. Auto-debit mandates can only be paused by you, in your UPI app; we only remind you in time.
- **Checkable:** Nothing is obfuscated; every voice decision is in the consent log (`GET /api/consent-log`).

## 🛠️ Quick Start

**1. Clone the repository**
```bash
git clone https://github.com/Anton-gil/chaufferone.git
cd chaufferone
cp .env.example .env   # then fill in the values
```

**2. Start the Backend**
```bash
# uv (recommended)
uv run uvicorn app.main:app --reload --port 8000

# or plain pip
python -m venv .venv && .venv/Scripts/activate   # Windows (source .venv/bin/activate elsewhere)
pip install -e . && uvicorn app.main:app --reload --port 8000
```
*Alembic migrations run automatically on startup and create `data/chaufferone.db`.*

**3. Start the Frontend**
```bash
cd web
npm install
npm run dev
```

Visit `http://localhost:3000` to access the timeline. API docs: `http://localhost:8000/docs`.

**4. Tests**
```bash
uv run pytest -q
```

## 🎬 Demo Runbook

See [`docs/handoff-v2.md`](docs/handoff-v2.md) for the full plan, the legal notes, and the pitch rules.

**Load the story:** `POST /api/demo/scenario` loads persona Arun's tight month (fictional companies: SafeRide Insurance, StreamMax, Kavi Studio). Import any real data you want on screen, then `POST /api/demo/snapshot`. `POST /api/demo/reset` returns to that point in about a second.

**Phone (Android, USB debugging on):**
```bash
adb install sms-to-url-forwarder.apk     # from F-Droid/GitHub; choose "Install anyway" if Play Protect warns
adb reverse tcp:8000 tcp:8000            # re-run whenever the cable is replugged
```
In the forwarder app, set the URL to `http://127.0.0.1:8000/api/ingest/sms` and keep the default JSON template. On Android 15+, if the SMS permission is greyed out: App info → ⋮ → *Allow restricted settings*.

**Live beats:**
1. A teammate sends the pre-debit text from `GET /api/demo/sample-sms` → `pre_debit` to the demo phone. Their number must be in `DEMO_SENDERS`. The UI gets a `consent_needed` event with the spoken proposal.
2. Reply by voice (typed fallback works the same): *"Go with the first one, but do the PUC on Sunday, I've got a lab on Saturday."*
3. Open `GET /api/pay/{gift_id}` and scan the QR to pay the teammate. The bank's real debit SMS marks it **Verified**. Use at least ₹100: some banks don't SMS small UPI debits.

If an SMS is late, `POST /api/demo/inject/sms` replays the same text through the same code path.

### API (for the UI)

| Method & path | What it does |
|---|---|
| `GET /api/plan` | Cards grouped `today / week / later / needs_check / verified`, plus money summary and the open proposal |
| `GET /api/money/forecast` | 45-day balances, floor/cushion, clashes |
| `GET /api/events` | SSE: `obligation_created`, `plan_changed`, `consent_needed`, `pay_requested`, `verified` (polling fallback: `/api/events/recent?since=<id>`) |
| `GET /api/proposal/current` | The open consent proposal: `speech`, `options[A,B]`, `clash` |
| `POST /api/voice/turn` | `{"text": "...", "proposal_id": "..."}` → `{speech, intent, applied_moves, plan_changed}` |
| `GET /api/consent-log` | Audit trail of every voice decision |
| `GET /api/pay/{id}` | `{upi_uri, qr_png_b64, payee_masked}` |
| `POST /api/ingest/sms` · `/sms-backup` · `/whatsapp` · `/eml` | Ingest (forwarder JSON / XML upload / chat export / .eml files) |
| `GET /api/graph` · `/api/graph/cascade/{id}` · `/api/graph/risk/{id}` | The obligation graph and "what breaks if I miss this" |
| `POST /api/demo/scenario` · `/snapshot` · `/reset` · `/inject/sms`, `GET /api/demo/sample-sms` | Demo controls |
