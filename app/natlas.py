"""Official NCAIR ASR models. No substitute model is silently used."""
import os
import subprocess
import tempfile
import shutil
import requests
from functools import lru_cache
from pathlib import Path

OFFICIAL_ASR = {
    "en-NG": "NCAIR1/NigerianAccentedEnglish",
    "ha": "NCAIR1/Hausa-ASR",
    "yo": "NCAIR1/Yoruba-ASR",
    "ig": "NCAIR1/Igbo-ASR",
}

@lru_cache(maxsize=2)
def get_asr(language):
    from transformers import pipeline
    if language not in OFFICIAL_ASR:
        raise ValueError("Unsupported language")
    return pipeline("automatic-speech-recognition", model=OFFICIAL_ASR[language], token=os.getenv("HF_TOKEN") or None)

def transcribe(audio_bytes, suffix, language):
    if language not in OFFICIAL_ASR:
        raise ValueError("Unsupported language")
    if len(audio_bytes) > 8 * 1024 * 1024:
        raise ValueError("Audio exceeds 8 MB")
    if not audio_bytes:
        raise ValueError("The audio file is empty")
    endpoint = os.getenv("ASR_ENDPOINT_" + language.upper().replace("-", "_"))
    if endpoint:
        if not endpoint.startswith("https://"):
            raise RuntimeError("The speech endpoint must use HTTPS")
        token = os.getenv("HF_TOKEN")
        headers = {"Content-Type": "application/octet-stream"}
        if token: headers["Authorization"] = "Bearer " + token
        try:
            response = requests.post(endpoint, data=audio_bytes, headers=headers, timeout=45)
            response.raise_for_status()
            text = response.json().get("text", "").strip()
        except (requests.RequestException, ValueError, AttributeError) as error:
            raise RuntimeError("The speech service could not transcribe this recording. Check endpoint access and try again.") from error
        if not text: raise ValueError("No speech was recognized. Try a clearer recording.")
        return text
    if os.getenv("VERCEL"):
        raise RuntimeError("Audio transcription is not configured for this language. Use the microphone dictation option or type your message.")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is missing on the speech server. Install FFmpeg or configure a hosted speech endpoint.")
    with tempfile.TemporaryDirectory() as tmp:
        extension = suffix.lower() if suffix.lower() in (".ogg",".opus",".mp3",".wav",".m4a",".mp4",".webm") else ".bin"
        source = Path(tmp) / ("voice"+extension)
        dest = Path(tmp) / "voice.wav"
        source.write_bytes(audio_bytes)
        subprocess.run(["ffmpeg","-nostdin","-y","-loglevel","error","-i",str(source),"-t","45","-ac","1","-ar","16000",str(dest)], check=True, timeout=30, capture_output=True)
        text = (get_asr(language)(str(dest)).get("text") or "").strip()
        if not text: raise ValueError("No speech was recognized. Try a clearer recording.")
        return text
