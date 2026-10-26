# API setup for YourNaira

## Official NCAIR N-ATLAS models
1. Create a Hugging Face account: https://huggingface.co/join
2. Visit https://huggingface.co/NCAIR1/Hausa-ASR or https://huggingface.co/NCAIR1/NigerianAccentedEnglish; follow the access conditions. Other models: NCAIR1/Yoruba-ASR and NCAIR1/Igbo-ASR.
3. Create a read token at https://huggingface.co/settings/tokens and permit access to the authorized repository.
4. Add `HF_TOKEN=...` to private `.env` (never commit secrets).
5. `pip install torch transformers librosa soundfile huggingface_hub`
6. `set -a; source .env; set +a` then start uvicorn. Upload a short voice file; a successful transcript is needed before claiming model integration.
7. Official published model weights may be distinct from the organizer's hosted N-ATLAS ASR service; confirm any required service endpoint with organizers.

## Twilio WhatsApp Sandbox
1. Create a Twilio account at https://console.twilio.com and open the WhatsApp Sandbox in the Messaging section.
2. Join the sandbox by sending its specific code to its assigned WhatsApp number.
3. Find Account SID and Auth Token in Twilio console; put `TWILIO_ACCOUNT_SID=...` and `TWILIO_AUTH_TOKEN=...` in `.env`.
4. Install/start ngrok (`ngrok http 8000`), put your generated HTTPS domain as `PUBLIC_BASE_URL=https://...` in `.env`, then restart uvicorn.
5. In Twilio Sandbox, set `When a message comes in` webhook to `https://YOUR-DOMAIN/twilio/whatsapp` with POST.
6. Send a text like `I spent ₦1500 on food` to test. Voice mode uses Hausa by default and still needs official ASR model access. Sandbox scaffold is not production-safe.

## Not needed yet
OpenAI, Paystack, bank account access, BVN/NIN, and trading API keys are not required for this prototype.

## Vercel deployment and complete user flow
- Text: enter an expense, income or budget → Send message → request `/api/message` → ledger → response. `summary` reads only the current browser session. Session storage resets when the browser session ends; there are no accounts yet.
- Microphone: allow microphone access → dictate → review/edit the text → Send message. Browser speech recognition is a separate service, not the official NCAIR model, and availability depends on browser/language.
- Upload: select the language → choose a recording → transcribe → review/edit transcript → Send message. Transcribing alone never saves a financial entry.
- Configure `DATABASE_URL` with a PostgreSQL connection string for persistent shared storage. Without it Vercel uses `/tmp/yournaira_demo.db`, which is disposable and not shared between instances. `DATABASE_URL` takes precedence over `DATABASE_PATH`. Existing SQLite entries are not migrated automatically.
- Configure one HTTPS dedicated Hugging Face inference endpoint per supported language: `ASR_ENDPOINT_EN_NG`, `ASR_ENDPOINT_HA`, `ASR_ENDPOINT_YO`, `ASR_ENDPOINT_IG`. Each endpoint must serve its corresponding official model listed above, accept raw audio bytes, and return `{"text":"..."}`. Set `HF_TOKEN` privately for endpoint authentication. No endpoint is provisioned by this repository.
- Hosted upload inference bypasses FFmpeg and local model downloads on Vercel. To run models on your own speech server, install system FFmpeg and `pip install -r requirements-voice.txt`; model access must already be authorized.
- Redeploy after changing environment variables. `/api/capabilities` reports configuration only; it does not prove model access. Test a known recording before claiming official integration.
- WhatsApp still requires your Twilio sandbox credentials and webhook configuration above; it cannot be verified without them.

## Verification
Run `python -m pytest -q`. The tests cover text accounting and session isolation, validation, JSON errors, and a simulated voice transcript followed by user confirmation. They do not prove live speech model access or persistent database connectivity.

## Chat interface and recorded voice
The chat UI uses `/api/message` for text, `/api/history?session=...` for the last 200 conversation turns, and `/api/voice` for transcription only. The server saves each text/reply pair atomically with its ledger action. A stable request ID makes a retry return its previous response without adding the transaction again. PostgreSQL uses a per-session transaction lock; SQLite uses an immediate transaction.

The browser preserves its random session ID in localStorage and migrates the existing sessionStorage ID on first use. This is a prototype identity, not authentication or cross-device account access. Clearing browser data loses the identifier. New conversation starts a separate ledger and chat and stops displaying the previous session; it does not delete database records. Old ledger entries have no chat messages to backfill.

The microphone now uses MediaRecorder, not browser speech recognition. Select Nigerian English or Hausa, record up to 45 seconds, stop, listen, transcribe, edit the resulting draft, then send. Audio is submitted only when Transcribe is pressed. Closing/discarding releases microphone tracks and object URLs; YourNaira does not store the recording. Hosted inference providers have their own data-handling policies. Uploads and recordings are limited to 8 MB.

On Vercel the selected language needs its matching ASR_ENDPOINT_EN_NG or ASR_ENDPOINT_HA. Unconfigured voice controls are disabled while text remains usable. Local inference defaults to CPU to support laptops whose GPUs are incompatible with their installed PyTorch build. English passes `language=en, task=transcribe`; Hausa passes `language=ha, task=transcribe`. The Hausa model still requires a real recording test before claiming successful Hausa inference. Basic Hausa financial phrases with numeric amounts are supported, e.g. `Na kashe naira 500 a abinci`, `Na samu naira 2000`, and `takaitawa`; this is a rule-based financial parser, not unrestricted Hausa conversation.

### Updating the deployed UI
Fetch and switch to the feature branch after saving any local changes, then deploy using your existing authorized Vercel CLI session. Keep DATABASE_URL set for Production. Neither speech endpoints nor secrets are provisioned by this feature.
