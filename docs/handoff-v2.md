# Refined Plan: Obligation Engine, 8-hour build (v2 of handoff.md)

## Context

**Status:** Supersedes the build scope of `handoff.md` for the hackathon. Sections 1–4 of `handoff.md` (the problem, the persona, the Obligation concept) still hold. Where the two documents disagree, **this one wins**.

`handoff.md` describes a multi-week, 4-role product: a Kotlin companion app, Gmail OAuth, local STT/TTS, WASM plugins, licensing, encryption and more. The real constraints:

- **8 hours** of build time. Code freeze at **12 AM**. **Live demo later** (next morning).
- **1 backend developer.** The UI is handled separately by the team.
- **Hardware:** a GPU laptop, plus an Android phone that receives real bank SMS.
- **Stack:** Python + React (+ a little Kotlin).
- **LLM:** local for extraction; hosted only for the live voice step, behind a labelled switch.

This plan cuts the handoff down to one hero chain that a single person can build in 8 hours, corrects the legal and platform assumptions against current (Sep 2026) rules, and hardens the demo so nothing depends on luck.

Method: a product-lens diagnostic plus a grill-style interview (every decision below was forced to an answer). The legal facts were checked against sources on 29 Sep 2026, and they're listed at the end.

---

## 1. Grilling log (decisions resolved)

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | Can one person build the whole of Section 3 in 8 hours? | No. Build **one chain**: PUC → insurance, money clash, voice consent, verified payment. Everything else goes to the roadmap. | The handoff itself says to protect demo steps 2–4. |
| 2 | Should we write a Kotlin SMS app? | **No custom Kotlin.** Use the open-source **"SMS to URL Forwarder"** APK (F-Droid/GitHub, installed via `adb`) for live SMS. Use **"SMS Backup & Restore"** (Play Store) XML export for the 60-day backfill. | Zero Android code. The forwarder allows cleartext HTTP, has a JSON template and retries. |
| 3 | How does the phone reach the laptop? | **`adb reverse tcp:8000 tcp:8000` over USB.** The phone posts to `http://127.0.0.1:8000`. | Venue Wi-Fi often isolates clients from each other. `localhost` also counts as a browser secure context, so the mic works. |
| 4 | WhatsApp? | **Chat export `.txt` only**, from a staged group of consenting teammates. | There's no personal WhatsApp API, and notification-listener work doesn't fit in 8 hours. |
| 5 | Gmail? | **`.eml` upload** (Gmail → ⋮ → Download message) as the primary path. Gmail API in testing mode is a **stretch goal**. | OAuth setup plus the restricted-scope warning screen costs about an hour. `.eml` is still real mail through the same extractor. |
| 6 | Where do LLMs run? | **Extraction:** local Ollama on the GPU laptop, **precomputed and cached** before the demo. **Voice intent:** hosted, through an OpenAI-compatible client, where `LLM_BASE_URL` is the labelled switch (it can point back at Ollama `/v1`). **Rules first, LLM second** for both. | The live demo path becomes deterministic: regex for SMS, a rule parser for the scripted reply. The LLM only covers off-script input. |
| 7 | STT/TTS? | Browser **Web Speech API** for STT and **speechSynthesis** for TTS (Windows ships local en-IN voices). The UI team owns both. The backend is text in, text out. **A typed-reply box is mandatory.** | faster-whisper with CUDA on Windows is a rabbit hole for a solo developer. Typing is the offline fallback. |
| 8 | How do we show a payment? | A **UPI P2P QR code** (`upi://pay?pa=…&am=…&tn=…` rendered as a QR) for a **teammate's VPA**. It's scanned by the demo phone and paid with its PIN. **No intent links.** | Unsigned intents to personal VPAs are often declined by GPay/PhonePe, and merchant intents need `mc`/`tr` from a registered merchant. Scanning a P2P QR always works. |
| 9 | What counts as proof of payment? | The **real bank debit SMS** from that payment. Pay **≥ ₹100**, because some banks (e.g. HDFC since 2024) send no SMS for small UPI debits. **Test this in hour 1.** | Real proof instead of a mocked one. |
| 10 | How does the live pre-debit SMS arrive? | A teammate sends the **real template text** of a pre-debit SMS from their phone. Their number goes in `DEMO_SENDERS`. We say this on stage. | No one can make a bank send one on cue. |
| 11 | Voice-call and WhatsApp escalation? | **Cut.** The in-app prompt is pushed over SSE. | Outbound calls/SMS to users need TRAI DLT registration and 160-series numbers. WhatsApp outbound needs the Business Platform plus templates. |
| 12 | Encryption, plugin sandbox, licence, network-log screen, Alembic, Calendar, P2/P4/P6? | **Cut from the build** and shown **on a roadmap slide only**. | Don't claim anything that isn't built (see §9). |

---

## 2. Legal and platform facts (verified Sep 2026), and what each one changes

| Rule (source) | Consequence |
|---|---|
| **Play Protect "enhanced fraud protection" (India, since Oct 2024)** auto-blocks internet-sideloaded apps that request `RECEIVE_SMS`, `READ_SMS`, notification-listener or accessibility permissions. | Install via **`adb` only** (exempt). Play Protect may still flag the forwarder, because an SMS-to-URL app looks like an SMS stealer. Choose "Install anyway". On the **demo phone only**, pause "Scan apps with Play Protect" until the event is over. |
| **Android 15+ restricted settings** apply to sideloaded apps (SMS runtime permission, notification listener). | If the SMS toggle is greyed out: App info → ⋮ → **Allow restricted settings**, then grant it. |
| **Android developer verification**: enforced from **30 Sep 2026 in BR/ID/SG/TH only**, globally in 2027. **ADB installs are exempt.** | No impact on India tomorrow. For production, publish a verified Play app. |
| **Play SMS policy**: non-default-handler apps can use `READ_SMS`/`RECEIVE_SMS` under the **"SMS-based money management"** exception, subject to review. | This is the real production path for Android. It goes on the roadmap slide instead of "we'll figure it out". |
| **Gmail `gmail.readonly` is a restricted scope.** Testing mode allows ≤100 test users and **refresh tokens expire after 7 days**. A CASA assessment is needed only if data can reach a **server**. | For the hackathon: `.eml` upload, or testing-mode OAuth with the team as test users. For production: local-first processing may avoid CASA (confirm with Google), but restricted-scope verification is still needed. |
| **RBI Digital Payments – E-mandate Framework, 2026 (21 Apr 2026)** consolidates the old circulars: a pre-debit notice **≥24 h** before each debit, with opt-out; AFA-free up to **₹15,000**, up to **₹1 lakh** for insurance, mutual funds and credit cards; **only the customer can modify or withdraw a mandate, with AFA**. | Cite the 2026 framework, not the 2019/2023 circulars. The engine **advises** pausing a mandate in the user's UPI app. It never touches mandates itself. |
| **RBI authentication directions:** from **1 Apr 2026**, digital payments need 2 factors, one of them dynamic. | **Voice approves the plan. The UPI PIN approves the payment.** Voice is never payment authorisation. |
| **NPCI:** P2P **collect requests banned since 1 Oct 2025**. Mobile numbers are **masked** in UPI apps from 4 Sep 2026. | The future P3 trip-split plugin can't "request money". It has to share a QR instead. Don't key payees on phone numbers; use the VPA or name. |
| **TRAI header suffixes (since 6 May 2025):** `-T`, `-S`, `-G`, `-P`. | Sender filter: accept `-T`/`-S`/`-G` headers plus `DEMO_SENDERS`, drop `-P`. This removes promos and most spoofed SMS. |
| **PUC → insurance:** SC order (*M.C. Mehta*, Aug 2017); IRDAI circulars of 6 Jul 2018 and 20 Aug 2020. IRDAI (26 Aug 2020) says a **claim** can't be rejected solely for a missing PUC. The rule applies at **renewal**. | The "needs first" edge is legally grounded. The penalty text says: no PUC, up to ₹10,000 (MV Act). Riding uninsured, ₹2,000 and NCB loss after a 90-day lapse. *Double-check the uninsured-fine figure before saying it on stage.* |
| **DPDP Rules notified 13 Nov 2025.** The substantive duties start **14 May 2027**. Purely personal or domestic processing by an individual is outside the Act. | Pitch "designed so personal data never reaches our servers", **not** "DPDP-compliant". Demo only the team's own data and a staged group of consenting teammates. |
| **Meta WhatsApp Business Platform:** general-purpose AI chatbots banned since **15 Jan 2026**. Task-specific bots are allowed. | Future WhatsApp nudges are allowed (a task bot), but they're out of scope today. |
| **Insurance quote comparison** is an IRDAI-regulated intermediary activity (web aggregators/brokers). *Verify.* | P4 must **link out** to the insurer or a licensed aggregator. It must not compare quotes in-app. |

---

## 3. Scope for the 8 hours

**BUILD (the solo backend):**
- **Ingest:** `POST /api/ingest/sms` (forwarder and demo injection share this code path); SMS Backup XML import; WhatsApp `.txt` import; `.eml` upload.
- **Extract:** regex templates for the demo phone's bank (pre-debit/mandate, debit, credit), with `dateparser` in DMY order, then a local LLM fallback (Ollama with a `format` JSON schema); dedup key `(counterparty, amount ±5%, due ±3d)`; confidence below 0.75 goes to Needs-check.
- **Graph:** a knowledge pack JSON with the one rule `puc_before_motor_insurance`; automatic "shares money" edges; `networkx` for cycle checks.
- **Sequencer:** `start_by = due − lead − margin(2d)`, recursing through prerequisites; payments are planned just-in-time on their `start_by`; PUC snaps to the nearest weekend slot on or before its `start_by`; `priority = p_miss × penalty ÷ effort`.
- **Money engine:** a 45-day daily simulation, a hard floor plus a soft cushion, clash detection, and a greedy search for up to 3 options (defer within the due window after the next income / pause a mandate before its 24 h window closes / reorder by penalty). **Never plan below the floor.**
- **Consent:** an SSE `consent_needed` event carries a proposal whose speech is templated from engine numbers; `POST /api/voice/turn` runs the rule parser first and the LLM second, then simulates, validates, applies and **logs consent** (timestamp, spoken proposal, exact utterance).
- **Verify:** `detected → planned → approved → paid (debit SMS matched on amount + payee within 3 days) → verified`.
- **Pay:** `GET /api/pay/{id}` returns a UPI URI plus a QR PNG (`segno`).

**FAKE, AND SAY SO:** the persona "Arun"; a seeded vehicle profile (PUC expiry); a seeded opening balance and allowance; staged insurer and freelance emails and the WhatsApp group, all with **fictional brand names** (e.g. "SafeRide Insurance", "StreamMax").

**CUT:** see decision 12, Gmail API (stretch only), OCR, Calendar, bundling beyond the PUC weekend snap, and learned `p_miss`.

---

## 4. Architecture (one process)

```
Phone (USB) ──adb reverse──► FastAPI :8000 (laptop) ◄── UI (team's React, same laptop / projector)
 SMS Forwarder → /api/ingest/sms      │  SQLite (SQLModel, create_all; snapshot file for reset)
 SMS Backup XML / WA .txt / .eml ───► │  extract (regex → Ollama JSON) · graph (networkx) · sequencer
                                      │  money sim · consent · verify · SSE /api/events
 Hosted LLM (voice intent only) ◄─────┘  via LLM_BASE_URL switch (can point to Ollama /v1)
```

Libraries: `fastapi uvicorn sqlmodel networkx dateparser httpx openai sse-starlette python-multipart segno beautifulsoup4 pytest`.

Suggested layout: `engine/{models,ingest,extract,graph,sequencer,money,consent,verify,api,demo}.py`, `knowledge/pack.json`, `seed/scenario.json`, `data/` (gitignored), `tests/test_scenario.py`.

---

## 5. API contract for the UI team (send by T+0:30; the UI can mock it straight away)

- `GET /api/timeline` → `{today[], week[], needs_check[], verified[]}` of **cards**
- **Card:** `{id,title,type,due,start_by,planned_on,amount_inr,status,priority,why,needs_first[],shares_money_with[],penalty,sources[{channel,label,ref}],confidence}`
- `GET /api/obligations/{id}` → card plus the raw source text
- `GET /api/forecast` → `{floor,cushion_top,days[{date,balance,events[]}],clash:{date,shortfall,options[{id,summary,cost_inr,moves[]}]}|null}`
- `GET /api/events` (SSE): `obligation_created`, `plan_changed`, `consent_needed{proposal_id,speech,options}`, `paid`, `verified`
- `POST /api/voice/turn {proposal_id,text}` → `{speech,intent,applied_moves[],plan_changed}`
- `POST /api/obligations/{id}/confirm` (Needs-check), `GET /api/pay/{id}` → `{upi_uri,qr_png_b64}`
- `POST /api/demo/reset`, `POST /api/demo/inject/sms {from,text}`, `GET /api/consent-log`

UI must-dos: a typed-reply fallback next to the mic; **one click on the page before the demo** (Chrome needs a user gesture before speechSynthesis will speak); display VPAs masked.

---

## 6. Demo scenario (numbers checked; pinned by `tests/test_scenario.py`)

Persona Arun. Today is **Wed 30 Sep 2026** (`DEMO_TODAY` can override). Floor **₹1,000**, cushion top **₹2,000**. Opening balance **₹2,500** (seeded; in demo mode, real SMS balances are ignored, which keeps the teammate's balance private).

| Date | Item | Δ | Balance before SMS | After OTT pre-debit | After consent (option A + PUC Sunday) |
|---|---|---|---|---|---|
| Thu 1 Oct | Allowance | +10,000 | 12,500 | 12,500 | 12,500 |
| Sat 3 Oct | Rent (due Mon 5) | −7,800 | 4,700 | 4,700 | 4,700 |
| Tue 6 Oct | **StreamMax annual (new pre-debit SMS)** | −1,499 | – | 3,201 | 3,201 |
| Wed 7 Oct | Birthday gift (WhatsApp, due Thu 8) | −500 | 4,200 | 2,701 | 2,701 |
| Sat 10 → **Sun 11** | PUC (needs a free afternoon) | −100 | 4,100 | 2,601 | 2,601 |
| Thu 15 → **Sat 17** | Insurance (due Sun 18, needs PUC) | −1,850 | **2,250 ✓** | **751 ✗ (₹249 below floor)** | 3,751 (on the 17th) |
| Fri 16 Oct | Freelance (invoice email, expected) | +3,000 | 5,250 | 3,751 | 5,601 |

- **Option A** (top, costs ₹0): pay insurance on Sat 17, after the freelance money lands, still a day before the deadline. The minimum balance becomes ₹2,601. The engine says it will re-check on Friday night if the freelance money hasn't arrived.
- **Option B:** pause StreamMax in the UPI app **before Mon 5 Oct** (the 24 h window). Saves ₹1,499.
- **Step 5** pays the birthday gift of ₹500 today to the teammate's VPA. The balance drops to exactly ₹2,000, which is at the cushion top and doesn't trigger a warning. The later numbers are unchanged.
- **Tests assert properties, not rupees:** no warning before injection; a floor clash after injection; option A ranked first and clearing the clash; "PUC Sunday" accepted because it's still before insurance; "insurance on the 19th" rejected because it's past the due date. The spoken script is generated from engine output, so the numbers can't drift.
- The rule parser's aliases for STT mishearings: `puc | p u c | p.u.c | pc | pollution (check|certificate)`, plus weekday names and ordinals, plus `yes|okay|go ahead|first one|option a|b`.

**Stage flow (3.5 min):** (1) the timeline, built from backfill, WhatsApp and `.eml` imports (nothing typed); (2) the insurance card with *needs first: PUC (expired)* and *shares money with: rent, gift*; (3) a teammate sends the pre-debit SMS, the forecast line dips below the floor, and `consent_needed` fires; (4) the voice exchange ("Go with the first one, but do the PUC on Sunday, I've got a lab Saturday"), then a live re-plan and the consent-log entry; (5) scan the QR and pay ₹500, the real debit SMS arrives, and the card turns **Verified**; (6) the close: *"Thirty alerts became one plan. Voice approved the plan, his UPI PIN approved the payment, and nothing left his own devices except the labelled voice model."*

---

## 7. Solo schedule (T0 ≈ 16:00, freeze 23:50) and cut ladder

| Time | Work | Go/no-go at the end |
|---|---|---|
| 16:00–16:30 | **Kill the riskiest unknowns first.** Start `ollama pull` for a 7–8B instruct model (~5 GB). Enable USB debugging (Xiaomi/Redmi/POCO: also "Install via USB" and "USB debugging (Security settings)"). Install the forwarder with `adb install`; set battery to unrestricted; run `adb reverse`; point it at a stub endpoint. Export SMS Backup XML and `adb pull` it. **Make a real ₹500 UPI test payment and time the debit SMS.** Send the §5 contract to the UI team. | A live SMS hits the stub. *If not: live SMS goes through `/demo/inject` typed by a teammate; backfill stays.* |
| 16:30–18:30 | models, knowledge pack, graph, sequencer, money simulation, clash options, seed loader, **`test_scenario.py` green** | *If behind: option A only.* |
| 18:30–19:45 | SMS regex (built from the phone's real formats), XML/WhatsApp/`.eml` importers, Ollama extraction with a content-hash cache, dedup, Needs-check | *If the LLM is flaky: regex plus a hand-reviewed `seed/extracted.json`, labelled "imported".* |
| 19:45–20:15 | Break, plus **checkpoint 1**: a real SMS becomes a card through the API | |
| 20:15–21:30 | SSE, consent proposal, `/voice/turn` (rules, then LLM), consent log, verify matcher, QR endpoint | *If behind: rules-only parser, no LLM.* |
| 21:30–22:30 | Integrate with the UI; **full run #1**; fix blockers only | |
| 22:30–23:30 | `demo/reset` (copies the snapshot DB), locked snapshot, **runs #2 and #3**, **record a backup video** (OBS or the Snipping Tool screen recorder, plus the phone's screen recorder for the SMS) | |
| 23:30–23:50 | README with run steps and honesty labels; `.gitignore` covering `data/`, `.env`, exports and tokens; commit and tag | **Freeze.** |

Cut order if behind: Gmail API → LLM voice fallback → option B/C → priority formula (sort by `start_by`) → WhatsApp import (seed JSON instead).

---

## 8. Pre-flight checklist (30 min before the live demo, no code changes)

Phone charged, **"Stay awake while charging"** on, USB cable seated; `adb devices`; re-run `adb reverse tcp:8000 tcp:8000` (it resets when the cable is replugged); forwarder alive (send a test SMS); phone hotspot on for the hosted LLM and Web Speech; `ollama` running and **warmed up with one dummy call** (a cold load takes 10–20 s); engine up; **`POST /api/demo/reset`**; Chrome mic permission granted and the page clicked once; teammate with the pre-debit text ready to send; teammate payee present; backup video open in another tab; **replay buttons** (`/demo/inject`) ready if an SMS arrives late.

---

## 9. Pitch: allowed claims vs. forbidden claims

- **Say:** "We never hold your money or bank credentials." "Voice approves the plan; your UPI PIN approves the payment." "The pre-debit notice is required by RBI's 2026 E-mandate Framework." "PUC-before-renewal comes from the Supreme Court's 2017 order and IRDAI circulars." "Extraction runs on this laptop. Only your spoken reply and obligation titles go to a hosted model, behind this switch." "The staged messages use fictional companies; the SMS pipeline is real."
- **Don't say:** "RBI/NPCI approved", "DPDP-compliant", "encrypted", "works with every bank", "reschedules your autopay", "pays automatically", "nothing leaves your phone" (the SMS goes to the laptop, which is still your own device), or any competitor shutdown claim (ChatGPT Pulse, SMS Organizer) that you can't source.
- **Roadmap slide:** a Play Store app under the SMS money-management exception; a notification listener for WhatsApp and UPI app notifications; Gmail restricted-scope verification; encrypted local DB; plugin sandbox; offline-signed licence; link-out cost reducers; Account Aggregator via a licensed FIU.

---

## Verification

1. `pytest tests/test_scenario.py` is green (the §6 properties) before 18:30 and again before freeze.
2. **Checkpoint 1:** a real SMS on the phone appears as a card in `GET /api/timeline` within 5 s.
3. **Three full end-to-end rehearsals** of the §6 stage flow on the locked snapshot, each starting from `/api/demo/reset`. A rehearsal passes only if every step works without touching code.
4. The backup video is recorded and plays back before freeze.
5. `git status` shows no personal data: no `data/`, SMS XML, `.eml`, `.env` or token files.

---

## Sources (checked 29 Sep 2026)

- Play Protect enhanced fraud protection, India: https://blog.google/intl/en-in/products/launching-enhanced-fraud-protection-pilot-in-india/
- Android developer verification timeline (ADB exempt): https://www.androidauthority.com/android-sideloading-changes-timeline-3679204/
- Android 15 restricted settings: https://www.androidauthority.com/android-15-restricted-settings-sideloading-3481098/
- Play SMS/Call Log policy ("SMS-based money management" exception): https://support.google.com/googleplay/android-developer/answer/10208820?hl=en
- Gmail restricted scope verification / CASA: https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification
- OAuth testing mode, 7-day refresh tokens: https://www.unipile.com/google-oauth-refresh-token/
- RBI Digital Payments E-mandate Framework 2026: https://www.scconline.com/blog/post/2026/04/24/rbi-issues-digital-payments-e-mandate-framework-2026/
- UPI rules 2026 (2FA from 1 Apr 2026): https://www.bankbazaar.com/ifsc/upi-rules.html
- NPCI P2P collect ban (1 Oct 2025): https://www.medianama.com/2025/08/223-npci-p2p-collect-payments-oct-1-what-it-means/
- UPI mobile-number masking (Sep 2026): https://www.techpillow.co/blog/npci-upi-phone-number-masking-privacy-dpdp-2026
- TRAI SMS header suffixes: https://trai.gov.in/sites/default/files/2025-02/Regulation_12022025.pdf
- DPDP Rules 2025 (PIB): https://www.pib.gov.in/PressReleasePage.aspx?PRID=2190014&reg=3&lang=2
- DPDP enforcement dates: https://www.amsshardul.com/insight/enforcement-of-the-dpdp-act-and-notification-of-the-dpdp-rules/
- IRDAI press release, PUC at renewal: https://irdai.gov.in/document-detail?documentId=695509
- PUC mandatory for insurance renewal: https://www.autocarindia.com/car-news/puc-certificate-now-mandatory-for-insurance-renewal-418400
- WhatsApp 2026 AI chatbot policy: https://respond.io/blog/whatsapp-general-purpose-chatbots-ban
- SMS to URL Forwarder: https://github.com/bogkonstantin/android_income_sms_gateway_webhook (F-Droid: https://f-droid.org/packages/tech.bogomolov.incomingsmsgateway/)
- UPI deep-link failures with personal VPAs: https://www.technetexperts.com/fix-upi-limit-exceeded-error/
