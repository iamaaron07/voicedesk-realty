import os, secrets, re, logging, time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from fastapi import FastAPI, Depends, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, JSON, select, func, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from sqlalchemy.pool import NullPool
import bcrypt
import httpx
from collections import defaultdict, deque
from threading import Lock

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:
    pass

def default_app_environment() -> str:
    # Hosted platforms must not inherit local-development SQLite defaults just
    # because APP_ENV was accidentally omitted from their project settings.
    return "production" if os.getenv("RENDER") or os.getenv("VERCEL") or os.getenv("VERCEL_ENV") else "development"

APP_ENV = os.getenv("APP_ENV", default_app_environment()).strip().lower()
PRODUCTION = APP_ENV == "production"

def database_url_from_env(app_env: str | None = None) -> str:
    configured = os.getenv("DATABASE_URL", "").strip()
    if not configured:
        if (app_env if app_env is not None else APP_ENV).lower() == "production":
            raise RuntimeError("DATABASE_URL must be configured in production.")
        return "sqlite:///./voicedesk.db"
    return normalize_database_url(configured)

def normalize_database_url(configured: str) -> str:
    if configured.startswith("postgres://"):
        return "postgresql+psycopg://" + configured[len("postgres://"):]
    if configured.startswith("postgresql://"):
        return "postgresql+psycopg://" + configured[len("postgresql://"):]
    return configured

def create_database_engine(database_url: str | None = None, app_env: str | None = None):
    env = (app_env if app_env is not None else APP_ENV).lower()
    url = normalize_database_url(database_url) if database_url else database_url_from_env()
    if env == "production" and url.startswith("sqlite"):
        raise RuntimeError("SQLite is not supported for production DATABASE_URL.")
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False}, pool_pre_ping=True)
    # Vercel Functions may create many short-lived execution environments. Use
    # the Neon pooled URL and release each connection after the request instead
    # of retaining a per-process pool that multiplies across function instances.
    if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
        return create_engine(url, poolclass=NullPool, pool_pre_ping=True)
    return create_engine(url, pool_size=2, max_overflow=0, pool_timeout=15, pool_recycle=300, pool_pre_ping=True)

DB_URL = database_url_from_env()
engine = create_database_engine(DB_URL)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
log = logging.getLogger("voicedesk")
_voice_hits=defaultdict(deque);_voice_lock=Lock()
_request_hits=defaultdict(deque);_request_lock=Lock()
SESSION_DAYS = 7
COOKIE = "voicedesk_session"
def cookie_settings(app_env: str, secure_value: str | None = None, samesite_value: str | None = None):
    secure = (secure_value if secure_value is not None else os.getenv("COOKIE_SECURE", "true" if app_env == "production" else "false")).lower() == "true"
    same_site = (samesite_value if samesite_value is not None else os.getenv("COOKIE_SAMESITE", "none" if app_env == "production" else "lax")).lower()
    if same_site not in {"lax", "strict", "none"}:
        raise RuntimeError("COOKIE_SAMESITE must be lax, strict, or none.")
    if app_env == "production" and not secure:
        raise RuntimeError("COOKIE_SECURE must be true in production.")
    if same_site == "none" and not secure:
        raise RuntimeError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true.")
    return secure, same_site

COOKIE_SECURE, COOKIE_SAMESITE = cookie_settings(APP_ENV)

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="customer")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
class SessionRow(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
class Property(Base):
    __tablename__ = "properties"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    locality: Mapped[str] = mapped_column(String(80))
    price: Mapped[int] = mapped_column(Integer)
    beds: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(500))
    demo: Mapped[bool] = mapped_column(Boolean, default=True)
    property_type: Mapped[str] = mapped_column(String(40), default="apartment")
    furnishing: Mapped[str] = mapped_column(String(40), default="semi-furnished")
    deposit: Mapped[int] = mapped_column(Integer, default=0)
    amenities: Mapped[list] = mapped_column(JSON, default=list)
    images: Mapped[list] = mapped_column(JSON, default=list)
    city: Mapped[str] = mapped_column(String(80), default="Bengaluru")
    area_sqft: Mapped[int] = mapped_column(Integer, default=1000)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    transaction_type: Mapped[str] = mapped_column(String(20), default="rent")
    assigned_agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), nullable=True)

class Agency(Base):
    __tablename__ = "agencies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[int] = mapped_column(primary_key=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agencies.id"))
    name: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    weekdays: Mapped[list] = mapped_column(JSON, default=lambda:[0,1,2,3,4,5])
    start_hour: Mapped[int] = mapped_column(Integer, default=9)
    end_hour: Mapped[int] = mapped_column(Integer, default=18)
class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    budget_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    locality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="new")
    score: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_booking_idempotency"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="requested")
    calendar_event_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default="completed")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
class SavedProperty(Base):
    __tablename__ = "saved_properties"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
class CallRecord(Base):
    __tablename__ = "call_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    execution_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    agent_id: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(40), default="session_issued")
    summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

app = FastAPI(title="VoiceDesk Realty API", version="1.0")
def validate_frontend_origin(origin: str, app_env: str) -> str:
    origin = origin.strip().rstrip("/")
    if app_env == "production":
        parsed_frontend = urlparse(origin)
        if parsed_frontend.scheme != "https" or not parsed_frontend.netloc or parsed_frontend.path not in ("", "/") or parsed_frontend.query or parsed_frontend.fragment:
            raise RuntimeError("FRONTEND_URL must be the exact HTTPS frontend origin in production.")
    return origin

frontend_origin = validate_frontend_origin(os.getenv("FRONTEND_URL", "http://localhost:3000"), APP_ENV)
allowed_origins = {frontend_origin}
app.add_middleware(CORSMiddleware, allow_origins=sorted(allowed_origins), allow_credentials=True, allow_methods=["GET","POST","DELETE","OPTIONS"], allow_headers=["Content-Type"])
@app.middleware("http")
async def auth_rate_limit(request:Request,call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path != "/api/integrations/bolna/webhook":
        origin=request.headers.get("origin")
        if origin and origin.rstrip("/") not in allowed_origins:
            return JSONResponse(status_code=403,content={"detail":"Request origin is not allowed."})
        if PRODUCTION and not origin:
            return JSONResponse(status_code=403,content={"detail":"A valid request origin is required."})
    if request.method=="POST" and request.url.path in ("/api/auth/login","/api/auth/register","/api/auth/password-reset"):
        ip=request.client.host if request.client else "unknown";now=time.monotonic()
        with _request_lock:
            hits=_request_hits[ip]
            while hits and now-hits[0]>60: hits.popleft()
            if len(hits)>=20: return JSONResponse(status_code=429,content={"detail":"Too many requests. Please wait and try again."})
            hits.append(now)
    return await call_next(request)
def db_dep():
    with SessionLocal() as db: yield db
def digest(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()
def current_user(request: Request, db: Session=Depends(db_dep)):
    token=request.cookies.get(COOKIE)
    if not token: raise HTTPException(401, "Please log in to continue.")
    row=db.get(SessionRow,digest(token))
    if not row or row.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        raise HTTPException(401, "Your session has expired. Please log in again.")
    user=db.get(User,row.user_id)
    if not user or not user.active: raise HTTPException(401,"Account unavailable.")
    return user
class Credentials(BaseModel):
    email: str = Field(min_length=3,max_length=320)
    password: str = Field(min_length=10,max_length=72)
class ResetRequest(BaseModel):
    email: str = Field(min_length=3,max_length=320)
class BookingRequest(BaseModel):
    property_id: int
    start_at: datetime
    idempotency_key: str = Field(min_length=8,max_length=120)
class LeadRequest(BaseModel):
    budget_max: int | None = Field(default=None,ge=0)
    locality: str | None = Field(default=None,max_length=100)
    bedrooms: int | None = Field(default=None,ge=0,le=20)
def valid_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value))
def hash_password(value: str) -> str:
    return bcrypt.hashpw(value.encode(), bcrypt.gensalt(rounds=12)).decode()
def verify_password(value: str, hashed: str) -> bool:
    try: return bcrypt.checkpw(value.encode(), hashed.encode())
    except ValueError: return False
def issue_session(response: Response, db: Session, user: User):
    token=secrets.token_urlsafe(32)
    db.add(SessionRow(token_hash=digest(token),user_id=user.id,expires_at=datetime.now(timezone.utc)+timedelta(days=SESSION_DAYS)))
    db.commit()
    response.set_cookie(COOKIE,token,httponly=True,secure=COOKIE_SECURE,samesite=COOKIE_SAMESITE,max_age=SESSION_DAYS*86400,path="/")
def public_user(user): return {"id":user.id,"email":user.email,"role":user.role}
@app.get("/api/health")
def health(db: Session=Depends(db_dep)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(503,"Database unavailable.")
    return {"status":"ok","database":"ok"}
@app.get("/api/integrations/status")
def integrations_status():
    bolna_ready=bool(os.getenv("BOLNA_API_KEY") and os.getenv("BOLNA_AGENT_ID") and os.getenv("BOLNA_WEB_CALL_ENABLED","false").lower() in ("1","true","yes"))
    return {"bolna":{"configured":bolna_ready,"mode":"credentials_present" if bolna_ready else "not_configured"},"google_calendar":{"configured":False,"mode":"not_implemented"},"email":{"configured":False,"mode":"not_implemented"}}
@app.get("/api/properties")
def properties(q: str="", min_price:int|None=None,max_price:int|None=None,beds:int|None=None,furnishing:str|None=None,property_type:str|None=None,transaction_type:str|None=None,sort:str="price_asc",offset:int=0,limit:int=20,db: Session=Depends(db_dep)):
    stmt=select(Property).where(Property.available.is_(True))
    if q: stmt=stmt.where(Property.locality.ilike(f"%{q}%"))
    if min_price is not None: stmt=stmt.where(Property.price>=min_price)
    if max_price is not None: stmt=stmt.where(Property.price<=max_price)
    if beds is not None: stmt=stmt.where(Property.beds>=beds)
    if furnishing: stmt=stmt.where(Property.furnishing==furnishing)
    if property_type: stmt=stmt.where(Property.property_type==property_type)
    if transaction_type: stmt=stmt.where(Property.transaction_type==transaction_type)
    if sort=="price_desc": stmt=stmt.order_by(Property.price.desc())
    else: stmt=stmt.order_by(Property.price.asc())
    rows=db.scalars(stmt.offset(max(offset,0)).limit(min(max(limit,1),100))).all()
    return [property_json(p) for p in rows]
def property_json(p):
    return {"id":p.id,"title":p.title,"locality":p.locality,"city":p.city,"price":p.price,"deposit":p.deposit,"beds":p.beds,"area_sqft":p.area_sqft,"description":p.description,"demo":p.demo,"property_type":p.property_type,"furnishing":p.furnishing,"amenities":p.amenities or [],"images":p.images or [],"available":p.available,"transaction_type":p.transaction_type}
@app.get("/api/properties/{property_id}")
def property_detail(property_id:int,db:Session=Depends(db_dep)):
    p=db.get(Property,property_id)
    if not p or not p.available: raise HTTPException(404,"Property not found.")
    return property_json(p)
@app.post("/api/auth/register")
def register(data: Credentials, response: Response, db: Session=Depends(db_dep)):
    email=data.email.lower()
    if not valid_email(email): raise HTTPException(422,"Enter a valid email address.")
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,"An account with this email already exists.")
    if not any(c.isalpha() for c in data.password) or not any(c.isdigit() for c in data.password): raise HTTPException(422,"Use at least 10 characters, including a letter and a number.")
    user=User(email=email,password_hash=hash_password(data.password),role="customer")
    db.add(user); db.commit(); db.refresh(user); issue_session(response,db,user)
    return public_user(user)
@app.post("/api/auth/login")
def login(data: Credentials,response: Response,db: Session=Depends(db_dep)):
    if not valid_email(data.email): raise HTTPException(422,"Enter a valid email address.")
    user=db.scalar(select(User).where(User.email==data.email.lower()))
    if not user or not verify_password(data.password,user.password_hash): raise HTTPException(401,"Email or password is incorrect.")
    issue_session(response,db,user); return public_user(user)
@app.get("/api/auth/me")
def me(user: User=Depends(current_user)): return public_user(user)
@app.post("/api/auth/logout")
def logout(request: Request,response: Response,db: Session=Depends(db_dep)):
    token=request.cookies.get(COOKIE)
    if token:
        row=db.get(SessionRow,digest(token))
        if row: db.delete(row); db.commit()
    response.delete_cookie(COOKIE,path="/",httponly=True,secure=COOKIE_SECURE,samesite=COOKIE_SAMESITE); return {"ok":True}
@app.post("/api/auth/password-reset")
def password_reset(data: ResetRequest):
    if not valid_email(data.email): raise HTTPException(422,"Enter a valid email address.")
    if not os.getenv("EMAIL_PROVIDER_API_KEY"): raise HTTPException(503,"Password reset email is not configured. Contact the site administrator.")
    raise HTTPException(501,"Password reset delivery is configured but reset workflow is not yet enabled.")
@app.post("/api/voice/session")
async def voice_session(user: User=Depends(current_user),db:Session=Depends(db_dep)):
    now=datetime.now(timezone.utc).timestamp()
    with _voice_lock:
        hits=_voice_hits[user.id]
        while hits and now-hits[0]>60: hits.popleft()
        if len(hits)>=3: raise HTTPException(429,"Too many call attempts. Please wait a minute and retry.")
        hits.append(now)
    api_key=os.getenv("BOLNA_API_KEY","").strip(); agent_id=os.getenv("BOLNA_AGENT_ID","").strip()
    if os.getenv("BOLNA_WEB_CALL_ENABLED","false").lower() not in ("1","true","yes") or not api_key or not agent_id:
        raise HTTPException(503,"Voice calling is not configured yet. Please try again later.")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            response=await client.post("https://api.bolna.ai/web-call/freeswitch-session",headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},json={"agent_id":agent_id})
        if response.status_code == 429: raise HTTPException(429,"Voice service is at capacity. Please try again shortly.")
        if response.status_code in (401,403):
            log.error("Bolna rejected server credentials (HTTP %s)",response.status_code)
            raise HTTPException(502,"Voice service authentication failed. Please contact support.")
        if response.status_code >= 400:
            log.warning("Bolna session request failed (HTTP %s)",response.status_code)
            raise HTTPException(502,"The voice service could not start a session. Please try again.")
        payload=response.json()
        run_id=payload.get("run_id") if isinstance(payload,dict) else None
        if not run_id or str(payload.get("agent_id", agent_id)) != agent_id:
            log.error("Bolna returned an invalid web-call session payload")
            raise HTTPException(502,"The voice service returned an invalid session.")
        db.add(CallRecord(user_id=user.id,execution_id=str(run_id),agent_id=agent_id,status="session_issued"));db.commit()
        return payload
    except httpx.TimeoutException:
        raise HTTPException(504,"The voice service took too long to respond. Please retry.")
    except httpx.RequestError:
        log.warning("Bolna session request could not reach provider")
        raise HTTPException(502,"The voice service is temporarily unreachable.")
@app.get("/api/bookings")
def my_bookings(user:User=Depends(current_user),db:Session=Depends(db_dep)):
    return [booking_json(b,db) for b in db.scalars(select(Booking).where(Booking.user_id==user.id).order_by(Booking.start_at.desc())).all()]
def booking_json(b:Booking,db:Session):
    p=db.get(Property,b.property_id);a=db.get(Agent,b.agent_id)
    start=b.start_at.replace(tzinfo=timezone.utc) if b.start_at.tzinfo is None else b.start_at
    end=b.end_at.replace(tzinfo=timezone.utc) if b.end_at.tzinfo is None else b.end_at
    return {"id":b.id,"property_id":b.property_id,"property_title":p.title if p else "","agent":a.name if a else "","start_at":start.isoformat(),"end_at":end.isoformat(),"status":b.status,"calendar_mode":"demo (no Google Calendar event created)" if not b.calendar_event_id else "connected"}
def lock_booking_slots(db:Session):
    # Serialize overlap checks on PostgreSQL so concurrent API workers cannot
    # both accept the same agent/time window. SQLite serializes writers itself.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(731942018)"))
@app.post("/api/bookings")
def create_booking(data:BookingRequest,user:User=Depends(current_user),db:Session=Depends(db_dep)):
    start=data.start_at
    if start.tzinfo is None: raise HTTPException(422,"Appointment time must include its timezone.")
    start=start.astimezone(timezone.utc);end=start+timedelta(hours=1)
    if start <= datetime.now(timezone.utc): raise HTTPException(422,"Choose a future appointment time.")
    existing=db.scalar(select(Booking).where(Booking.user_id==user.id,Booking.idempotency_key==data.idempotency_key))
    if existing: return booking_json(existing,db)
    prop=db.get(Property,data.property_id)
    if not prop or not prop.available: raise HTTPException(404,"This property is no longer available.")
    lock_booking_slots(db)
    agents=db.scalars(select(Agent).where(Agent.active.is_(True),Agent.id==prop.assigned_agent_id) if prop.assigned_agent_id else select(Agent).where(Agent.active.is_(True))).all()
    local=start.astimezone(ZoneInfo("Asia/Kolkata")); agent=next((a for a in agents if local.weekday() in a.weekdays and local.hour>=a.start_hour and (local+timedelta(hours=1)).hour<=a.end_hour and not db.scalar(select(Booking.id).where(Booking.agent_id==a.id,Booking.status.in_(["requested","confirmed","rescheduled"]),Booking.start_at<end,Booking.end_at>start))),None)
    if not agent: raise HTTPException(409,"No agent is available for this appointment time. Choose another slot.")
    booking=Booking(user_id=user.id,property_id=prop.id,agent_id=agent.id,start_at=start,end_at=end,status="requested",idempotency_key=data.idempotency_key)
    db.add(booking);db.add(WorkflowEvent(user_id=user.id,event_type="booking.created",metadata_json={"property_id":prop.id,"agent_id":agent.id,"calendar":"unconfigured_demo"}));db.commit();db.refresh(booking)
    return booking_json(booking,db)
@app.post("/api/bookings/{booking_id}/cancel")
def cancel_booking(booking_id:int,user:User=Depends(current_user),db:Session=Depends(db_dep)):
    booking=db.get(Booking,booking_id)
    if not booking or booking.user_id!=user.id: raise HTTPException(404,"Booking not found.")
    if booking.status in ("cancelled","completed"): raise HTTPException(409,"This booking can no longer be cancelled.")
    booking.status="cancelled";db.add(WorkflowEvent(user_id=user.id,event_type="booking.cancelled",metadata_json={"booking_id":booking.id}));db.commit();return booking_json(booking,db)
@app.post("/api/bookings/{booking_id}/reschedule")
def reschedule_booking(booking_id:int,data:BookingRequest,user:User=Depends(current_user),db:Session=Depends(db_dep)):
    booking=db.get(Booking,booking_id)
    if not booking or booking.user_id!=user.id: raise HTTPException(404,"Booking not found.")
    if booking.status not in ("requested","confirmed","rescheduled"): raise HTTPException(409,"This booking can no longer be rescheduled.")
    start=data.start_at
    if start.tzinfo is None: raise HTTPException(422,"Appointment time must include its timezone.")
    start=start.astimezone(timezone.utc);end=start+timedelta(hours=1)
    if start<=datetime.now(timezone.utc): raise HTTPException(422,"Choose a future appointment time.")
    if db.scalar(select(Booking.id).where(Booking.user_id==user.id,Booking.idempotency_key==data.idempotency_key,Booking.id!=booking.id)): raise HTTPException(409,"This request key has already been used.")
    prop=db.get(Property,booking.property_id)
    lock_booking_slots(db)
    agents=db.scalars(select(Agent).where(Agent.active.is_(True),Agent.id==prop.assigned_agent_id) if prop and prop.assigned_agent_id else select(Agent).where(Agent.active.is_(True))).all()
    local=start.astimezone(ZoneInfo("Asia/Kolkata"));agent=next((a for a in agents if local.weekday() in a.weekdays and local.hour>=a.start_hour and (local+timedelta(hours=1)).hour<=a.end_hour and not db.scalar(select(Booking.id).where(Booking.agent_id==a.id,Booking.id!=booking.id,Booking.status.in_(["requested","confirmed","rescheduled"]),Booking.start_at<end,Booking.end_at>start))),None)
    if not agent: raise HTTPException(409,"No agent is available for this appointment time. Choose another slot.")
    booking.agent_id=agent.id;booking.start_at=start;booking.end_at=end;booking.status="rescheduled";booking.idempotency_key=data.idempotency_key
    db.add(WorkflowEvent(user_id=user.id,event_type="booking.rescheduled",metadata_json={"booking_id":booking.id,"agent_id":agent.id}));db.commit();db.refresh(booking)
    return booking_json(booking,db)
@app.post("/api/leads")
def upsert_lead(data:LeadRequest,user:User=Depends(current_user),db:Session=Depends(db_dep)):
    lead=db.scalar(select(Lead).where(Lead.user_id==user.id))
    if not lead: lead=Lead(user_id=user.id);db.add(lead)
    lead.budget_max=data.budget_max;lead.locality=data.locality;lead.bedrooms=data.bedrooms
    lead.score=sum([20 if data.budget_max else 0,20 if data.locality else 0,20 if data.bedrooms else 0]);lead.status="qualified" if lead.score>=40 else "new"
    db.add(WorkflowEvent(user_id=user.id,event_type="lead.updated",metadata_json={"lead_score":lead.score,"score_factors":[name for name,value in [("budget",data.budget_max),("locality",data.locality),("bedrooms",data.bedrooms)] if value]}));db.commit();db.refresh(lead)
    return {"id":lead.id,"budget_max":lead.budget_max,"locality":lead.locality,"bedrooms":lead.bedrooms,"score":lead.score,"status":lead.status}
@app.get("/api/workflows/events")
def my_workflows(user:User=Depends(current_user),db:Session=Depends(db_dep)):
    return [{"id":e.id,"type":e.event_type,"status":e.status,"created_at":e.created_at.isoformat(),"metadata":e.metadata_json} for e in db.scalars(select(WorkflowEvent).where(WorkflowEvent.user_id==user.id).order_by(WorkflowEvent.created_at.desc()).limit(100)).all()]
@app.get("/api/customer/saved-properties")
def saved_properties(user:User=Depends(current_user),db:Session=Depends(db_dep)):
    return [property_json(db.get(Property,s.property_id)) for s in db.scalars(select(SavedProperty).where(SavedProperty.user_id==user.id)).all()]
@app.post("/api/customer/saved-properties/{property_id}")
def save_property(property_id:int,user:User=Depends(current_user),db:Session=Depends(db_dep)):
    if not db.get(Property,property_id): raise HTTPException(404,"Property not found.")
    row=db.get(SavedProperty,(user.id,property_id))
    if not row: db.add(SavedProperty(user_id=user.id,property_id=property_id));db.commit()
    return {"saved":True}
@app.delete("/api/customer/saved-properties/{property_id}")
def unsave_property(property_id:int,user:User=Depends(current_user),db:Session=Depends(db_dep)):
    row=db.get(SavedProperty,(user.id,property_id))
    if row: db.delete(row);db.commit()
    return {"saved":False}
@app.post("/api/voice/calls/{execution_id}/started")
def call_started(execution_id:str,user:User=Depends(current_user),db:Session=Depends(db_dep)):
    call=db.scalar(select(CallRecord).where(CallRecord.execution_id==execution_id,CallRecord.user_id==user.id))
    if not call: raise HTTPException(404,"Voice session not found.")
    if call.status=="session_issued": call.status="in-progress";db.commit()
    return {"ok":True}
@app.get("/api/private/calls")
def private_calls(user: User=Depends(current_user),db:Session=Depends(db_dep)):
    return [{"id":c.execution_id,"status":c.status,"summary":c.summary,"duration_seconds":c.duration_seconds,"started_at":c.started_at.isoformat(),"ended_at":c.ended_at.isoformat() if c.ended_at else None} for c in db.scalars(select(CallRecord).where(CallRecord.user_id==user.id).order_by(CallRecord.started_at.desc()).limit(100)).all()]
@app.post("/api/integrations/bolna/webhook")
async def bolna_webhook(request:Request,db:Session=Depends(db_dep)):
    secret=os.getenv("BOLNA_WEBHOOK_SECRET","")
    supplied=request.headers.get("x-voicedesk-webhook-secret","")
    if not secret or not secrets.compare_digest(secret,supplied): raise HTTPException(401,"Invalid webhook credentials.")
    try: payload=await request.json()
    except Exception: raise HTTPException(400,"Invalid webhook payload.")
    if not isinstance(payload,dict) or not payload.get("id") or str(payload.get("agent_id"))!=os.getenv("BOLNA_AGENT_ID","").strip(): raise HTTPException(422,"Invalid execution payload.")
    call=db.scalar(select(CallRecord).where(CallRecord.execution_id==str(payload["id"])))
    if not call: return {"ok":True,"ignored":True}
    status=str(payload.get("status", ""))[:40]
    if status in ("completed","failed","cancelled","ended"):
        call.status=status
        summary=payload.get("summary")
        call.summary=str(summary)[:2000] if summary else None
        duration=payload.get("conversation_duration")
        try: call.duration_seconds=max(0,int(float(duration))) if duration is not None else None
        except (TypeError,ValueError): call.duration_seconds=None
        call.ended_at=datetime.now(timezone.utc);db.commit()
    return {"ok":True}
@app.get("/api/agent/leads")
def agent_leads(user: User=Depends(current_user)):
    if user.role not in ("agent","admin"): raise HTTPException(403,"Agent access required.")
    return []
@app.get("/api/admin/analytics")
def admin_analytics(user: User=Depends(current_user),db:Session=Depends(db_dep)):
    if user.role != "admin": raise HTTPException(403,"Administrator access required.")
    return {"leads":db.scalar(select(func.count()).select_from(Lead)),"bookings":db.scalar(select(func.count()).select_from(Booking)),"available_properties":db.scalar(select(func.count()).select_from(Property).where(Property.available.is_(True))),"calls":None,"call_metrics_status":"No call-history records are stored yet."}
