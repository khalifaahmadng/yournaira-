# YourNaira — Your Money, Your Voice

N-ATLAS innovation challenge prototype. Local typed expense/income tracking and budgeting work after dependency installation. Speech requires authorized NCAIR ASR model access and optional local model packages. WhatsApp requires Twilio credentials. Neither integration is verified.

## Ubuntu setup
```bash
sudo apt update && sudo apt install -y python3-venv ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
set -a; source .env; set +a
uvicorn app.main:app --reload --port 8000
```
Open http://localhost:8000 or http://localhost:8000/docs.

**Security:** only fictional amounts and test accounts; no authentication or bank integrations. Do not use financial credentials.

See [API_SETUP.md](API_SETUP.md) for exact token and WhatsApp Sandbox configuration.
