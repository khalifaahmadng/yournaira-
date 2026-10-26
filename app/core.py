"""Simple deterministic financial tracker: no bank or investment APIs."""
import os, re, sqlite3, uuid, hashlib
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

class PostgresConnection:
    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row
        self.connection = psycopg.connect(url, row_factory=dict_row, connect_timeout=10)
    def execute(self, sql, params=()):
        return self.connection.execute(sql.replace("?", "%s"), params)
    def executescript(self, sql):
        for statement in sql.split(";"):
            if statement.strip(): self.execute(statement)
    def __enter__(self): return self
    def __exit__(self, kind, value, traceback):
        try:
            if kind: self.connection.rollback()
            else: self.connection.commit()
        finally: self.connection.close()

def connect():
    url = os.getenv("DATABASE_URL")
    if url:
        connection = PostgresConnection(url)
    else:
        default = "/tmp/yournaira_demo.db" if os.getenv("VERCEL") else "yournaira_demo.db"
        connection = sqlite3.connect(os.getenv("DATABASE_PATH") or default, timeout=10)
    if not url: connection.row_factory=sqlite3.Row
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY,session TEXT,kind TEXT,amount_kobo BIGINT,category TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS budgets(session TEXT PRIMARY KEY,amount_kobo BIGINT);
    CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,session_hash TEXT,channel TEXT,language TEXT,action TEXT,used_official_asr INTEGER,consent INTEGER,at TEXT);
    """)
    return connection

def safe_session(value):
    value=(value or "").strip()
    return value[:96] if re.fullmatch(r"[a-zA-Z0-9_-]{3,96}",value) else str(uuid.uuid4())

def spoken_amount(text):
    units = dict(zip("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(), range(20)))
    units.update(dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20,100,10))))
    scales = {"hundred":100,"thousand":1000,"million":1000000}
    words = re.findall(r"[a-z]+", text.lower())
    total = current = 0
    found = False
    for word in words:
        if word in units:
            current += units[word]; found = True
        elif word in scales:
            if word == "hundred": current = max(current,1)*100
            else: total += max(current,1)*scales[word]; current = 0
            found = True
        elif word == "and" and found: continue
        elif found: break
    return (total+current)*100 if found else None

def detect(text):
    normalized=" ".join(text.lower().strip().split())
    match=re.search(r"(?:₦|ngn\s*|n\s*)([\d,]+(?:\.\d{1,2})?)",normalized) or re.search(r"\b([\d,]+(?:\.\d{1,2})?)\s*(?:naira|ngn)\b",normalized)
    if not match: match=re.search(r"\b([\d,]+(?:\.\d{1,2})?)\b",normalized)
    try: amount=int(Decimal(match.group(1).replace(",",""))*100) if match else None
    except (InvalidOperation,ValueError): amount=None
    if amount is None: amount = spoken_amount(normalized)
    if re.search(r"-\s*(?:₦|ngn|n)?\s*\d", normalized): amount=None
    if amount is not None and not (1<=amount<=100000000000): amount=None
    if re.search(r"\b(summary|balance|report|how much|total|spent so far)\b",normalized): return "summary",None,None
    if re.search(r"\b(help|commands|start)\b",normalized): return "help",None,None
    if re.search(r"\b(budget|limit|cap)\b",normalized): return "budget",amount,"monthly"
    if re.search(r"\b(income|earned|received|salary|paid me)\b",normalized): return "income",amount,"income"
    if re.search(r"\b(spent|spend|bought|paid for|expense|na kashe)\b",normalized):
        category="transport" if re.search(r"\b(transport|fuel|bus|taxi)\b",normalized) else "food" if re.search(r"\b(food|lunch|rice|breakfast|dinner)\b",normalized) else "other"
        return "expense",amount,category
    return "unknown",None,None

def handle(session,text):
    action,amount,category=detect(text)
    with connect() as db:
        if action in ("expense","income"):
            if amount is None: return action,"Please include an amount, e.g. I spent ₦1,500 on food."
            db.execute("INSERT INTO entries VALUES (?,?,?,?,?,?)",(str(uuid.uuid4()),session,action,amount,category,datetime.now(timezone.utc).isoformat()))
            return action,f"Recorded ₦{amount/100:,.2f} as {action} ({category}). Say summary to view totals."
        if action=="budget":
            if amount is None: return action,"Please include an amount, e.g. Set budget ₦30,000."
            db.execute("INSERT INTO budgets VALUES (?,?) ON CONFLICT(session) DO UPDATE SET amount_kobo=excluded.amount_kobo",(session,amount))
            return action,f"Monthly budget recorded: ₦{amount/100:,.2f}."
        if action=="summary":
            totals={row["kind"]:row["total"] for row in db.execute("SELECT kind, COALESCE(SUM(amount_kobo),0) total FROM entries WHERE session=? GROUP BY kind",(session,)).fetchall()}
            earned,spent=totals.get("income",0),totals.get("expense",0)
            budget=db.execute("SELECT amount_kobo FROM budgets WHERE session=?",(session,)).fetchone()
            suffix=f" | Budget remaining: ₦{(budget["amount_kobo"]-spent)/100:,.2f}" if budget else ""
            return action,f"Logged income: ₦{earned/100:,.2f} | Expenses: ₦{spent/100:,.2f} | Net: ₦{(earned-spent)/100:,.2f}{suffix}. Only logged entries are counted."
        if action=="help": return action,"Try: I spent ₦1,500 on food; I received ₦25,000 salary; Set budget ₦30,000; summary."
        return "unknown","Could not identify the transaction safely. Nothing was saved."

def record_event(session,channel,language,action,official,consent):
    if not consent: return
    with connect() as db:
        db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),hashlib.sha256(session.encode()).hexdigest()[:16],channel,language,action,int(official),1,datetime.now(timezone.utc).isoformat()))
