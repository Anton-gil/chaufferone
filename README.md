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

**Every message becomes an obligation. Every obligation knows what it depends on and what it costs. You get one sequenced plan instead of thirty alerts, and nothing moves your money without your voice saying yes.**

Chaufferone (The Obligation Engine) reads your incoming channels (SMS, Gmail, WhatsApp), extracts the critical information using a local LLM, and calculates a mathematically sound daily plan. 

### Core Features

- 📥 **Zero-Typing Ingestion:** Reads obligations from Gmail, Android SMS (including RBI-mandated pre-debit notices), WhatsApp, and PDFs.
- 🧠 **Smart Extraction:** Turns unstructured messages into a strict schema: Due Date, Lead Time, Costs, Penalty, and Dependencies using local LLMs (Ollama) and Regex.
- 🕸️ **Obligation Graph:** Knows that renewing your scooter insurance *requires* a PUC certificate, and both *share money* from your monthly allowance.
- 📅 **Backward-Scheduling Sequencer:** Calculates the exact *latest safe start date* for every task to avoid clashes, using manufacturing scheduling algorithms.
- 💰 **Clash-Free Money Engine:** Runs a 45-day daily forecast. If a bill drops you below your hard emergency floor, it tells you weeks in advance and proposes a fix.
- 🎙️ **Voice Consent:** Never moves your money without speaking to you. You hear the trade-offs and confirm with your voice.
- ✅ **Verification Loop:** Follows up on planned payments by matching real debit SMS alerts to close the loop.

## 🏗️ Architecture

- **Backend:** Python, FastAPI, SQLModel, SQLite
- **Graph & Engine:** NetworkX (Dependency tracking), Dateparser
- **Frontend:** Next.js (React), TailwindCSS
- **AI Stack:** 
  - *Extraction:* Local Ollama (7-8B Instruct model)
  - *Voice Control:* Hosted LLM for intent routing + STT (faster-whisper) + TTS (Piper/Kokoro)
- **Mobile Bridge:** Kotlin Android companion app (SMS to URL forwarder via `adb reverse tcp:8000`)

## 🚀 How it Works (The Demo Flow)

1. **Ingest:** An SMS or email hits the server.
2. **Contextualize:** The system identifies a deadline, penalty, and cost.
3. **Sequence:** The item is scheduled based on dependencies.
4. **Forecast:** The Money Engine detects an upcoming shortfall (cash clash).
5. **Consent:** The Voice assistant alerts you and proposes deferring a non-critical subscription. You reply via mic.
6. **Verify:** The payment is made via a generated UPI QR code (scanned manually), and the engine verifies the transaction via a matched debit SMS.

## 🔒 Privacy & Security

Your life administration belongs to you.
- **Local-First Processing:** Core extraction and sequencing run entirely on your own laptop/device.
- **No Money Touching:** We don't hold credentials. Payments happen in your own UPI app.
- **Checkable Privacy:** Nothing is hidden or obfuscated. Personal data doesn't leave your machine.

## 🛠️ Quick Start

**1. Clone the repository**
```bash
git clone https://github.com/Anton-gil/chaufferone.git
cd chaufferone
```

**2. Start the Backend**
```bash
# We use uv for fast Python dependency management
uv run uvicorn app.main:app --reload
```
*Note: Alembic migrations will create the `chaufferone.db` SQLite database on first run.*

**3. Start the Frontend**
```bash
cd web
npm install
npm run dev
```

Visit `http://localhost:3000` to access the timeline.
