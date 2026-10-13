"""Official NCAIR ASR models. No substitute model is silently used."""
import os
import subprocess
import tempfile
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
    with tempfile.TemporaryDirectory() as tmp:
        extension = suffix.lower() if suffix.lower() in (".ogg",".opus",".mp3",".wav",".m4a",".mp4",".webm") else ".bin"
        source = Path(tmp) / ("voice"+extension)
        dest = Path(tmp) / "voice.wav"
        source.write_bytes(audio_bytes)
        subprocess.run(["ffmpeg","-nostdin","-y","-loglevel","error","-i",str(source),"-t","45","-ac","1","-ar","16000",str(dest)], check=True, timeout=30, capture_output=True)
        return (get_asr(language)(str(dest)).get("text") or "").strip()
