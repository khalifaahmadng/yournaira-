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
