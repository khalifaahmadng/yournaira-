"""FastAPI demo. This is not an authenticated production finance service."""
import os,uuid,io,csv,hashlib,logging
from pathlib import Path
from urllib.parse import urlparse
import requests
from fastapi import FastAPI,UploadFile,File,Form,HTTPException,Request
from fastapi.responses import HTMLResponse,StreamingResponse,Response,JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel,Field
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from .core import safe_session,handle,record_event,connect
from .natlas import transcribe,OFFICIAL_ASR

ROOT=Path(__file__).resolve().parents[1]
app=FastAPI(title="YourNaira N-ATLAS Prototype",version="0.2.0")
templates=Jinja2Templates(directory=str(ROOT/"templates"))

@app.exception_handler(Exception)
async def server_error(request: Request, error: Exception):
    logging.getLogger("yournaira").exception("Request failed: %s", request.url.path, exc_info=error)
    return JSONResponse(status_code=500, content={"detail": "The server could not complete this request. Please try again. If it continues, check the deployment logs."})

@app.get("/api/capabilities")
def capabilities():
    hosted = [lang for lang in OFFICIAL_ASR if os.getenv("ASR_ENDPOINT_" + lang.upper().replace("-", "_"))]
    return {"hosted_voice_languages": hosted, "local_voice": not bool(os.getenv("VERCEL")),
            "storage": "persistent" if os.getenv("DATABASE_URL") else "temporary" if os.getenv("VERCEL") else "local"}


class Message(BaseModel):
    session:str=Field(default_factory=lambda:str(uuid.uuid4()))
    text:str=Field(min_length=1,max_length=600)
    consent:bool=False

@app.get("/",response_class=HTMLResponse)
def home(request:Request):
    return templates.TemplateResponse(request=request,name="index.html",context={})

@app.get("/api/health")
def health():
    return {"ok":True,"official_asr_models":OFFICIAL_ASR,"note":"Model download/inference not verified by this endpoint."}

@app.post("/api/message")
def message(data:Message):
    session=safe_session(data.session)
    action,reply=handle(session,data.text)
    record_event(session,"web-text","en-NG",action,False,data.consent)
    return {"session":session,"input":data.text,"reply":reply,"action":action,"official_asr_used":False}

@app.post("/api/voice")
async def voice(audio:UploadFile=File(...),session:str=Form(...),language:str=Form("ha"),consent:bool=Form(False)):
    if language not in OFFICIAL_ASR: raise HTTPException(400,"Unsupported language")
    data=await audio.read(8*1024*1024+1)
    if len(data)>8*1024*1024: raise HTTPException(413,"File exceeds 8MB")
    try: transcript=await run_in_threadpool(transcribe,data,Path(audio.filename or "voice.ogg").suffix,language)
    except ValueError as error: raise HTTPException(400,str(error)) from error
    except Exception as error:
        logging.getLogger("yournaira").exception("Speech recognition failed")
        raise HTTPException(503,str(error)[:240]) from error
    return {"session":safe_session(session),"transcript":transcript,"official_asr_used":True,"official_model":OFFICIAL_ASR[language],"requires_confirmation":True}

@app.post("/twilio/whatsapp")
async def whatsapp(request:Request):
    token=os.getenv("TWILIO_AUTH_TOKEN","")
    base=os.getenv("PUBLIC_BASE_URL","").rstrip("/")
    if not token or not base: raise HTTPException(503,"Twilio webhook not configured")
    form=await request.form()
    params={key:str(value) for key,value in form.items()}
    if not RequestValidator(token).validate(base+"/twilio/whatsapp",params,request.headers.get("X-Twilio-Signature","")): raise HTTPException(403,"Invalid Twilio signature")
    sender=str(form.get("From","unknown"))
    session="wa_"+hashlib.sha256(sender.encode()).hexdigest()[:24]
    transcript=str(form.get("Body","")).strip()
    if int(form.get("NumMedia","0") or 0):
        media_url=str(form.get("MediaUrl0",""))
        parsed=urlparse(media_url)
        if parsed.scheme!="https" or parsed.hostname not in ("api.twilio.com","media.twiliocdn.com"): raise HTTPException(400,"Unexpected media host")
        sid=os.getenv("TWILIO_ACCOUNT_SID","")
        if not sid: raise HTTPException(503,"Twilio SID missing")
        try:
            media=requests.get(media_url,auth=(sid,token),timeout=20,allow_redirects=False)
            media.raise_for_status()
            transcript=transcribe(media.content,".ogg","ha")
        except Exception: transcript=""
    _,reply=handle(session,transcript) if transcript else ("unknown","Sorry, voice could not be processed. Try text.")
    response=MessagingResponse()
    response.message(reply)
    return Response(content=str(response),media_type="application/xml")

@app.get("/api/validation-template")
def validation_template():
    output=io.StringIO()
    csv.writer(output).writerow(["participant_code","date_utc","consent_confirmed","language","channel","scenario","asr_model","actual_transcript","task_success","notes"])
    return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=validation_template.csv"})
