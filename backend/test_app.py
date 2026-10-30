from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app import app, Base, db_dep, Agency, Agent, Property, cookie_settings, create_database_engine, database_url_from_env, default_app_environment, initialize_database, validate_frontend_origin

@pytest.fixture
def client():
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    TestingSession=sessionmaker(engine,expire_on_commit=False)
    Base.metadata.create_all(engine)
    with TestingSession() as db:
        agency=Agency(name="Test Realty");db.add(agency);db.flush()
        agent=Agent(agency_id=agency.id,name="Test Agent");db.add(agent);db.flush()
        db.add(Property(title="Test home",locality="HSR Layout",price=40000,beds=2,description="Test listing",assigned_agent_id=agent.id,amenities=["Lift"]))
        db.commit()
    def override_db():
        with TestingSession() as db: yield db
    app.dependency_overrides[db_dep]=override_db
    with TestClient(app) as test_client: yield test_client
    app.dependency_overrides.clear();Base.metadata.drop_all(engine);engine.dispose()

def register(client,email="customer@example.com"):
    return client.post("/api/auth/register",json={"email":email,"password":"safePassword123"})

def test_registration_hashes_password_and_sets_customer_role(client):
    response=register(client)
    assert response.status_code==200
    assert response.json()["role"]=="customer"
    assert "password" not in response.json() and "password_hash" not in response.json()
    set_cookie=response.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie

def test_login_error_and_logout_invalidate_session(client):
    register(client)
    bad=client.post("/api/auth/login",json={"email":"customer@example.com","password":"incorrectPass1"})
    assert bad.status_code==401 and "incorrect" in bad.json()["detail"].lower()
    assert client.get("/api/auth/me").status_code==200
    assert client.post("/api/auth/logout").status_code==200
    assert client.get("/api/auth/me").status_code==401

def test_public_search_and_protected_roles(client):
    assert client.get("/api/properties?q=HSR").json()[0]["locality"]=="HSR Layout"
    assert client.get("/api/properties?q=NoSuchBengaluruLocality").json()==[]
    assert client.get("/api/properties/1").status_code==200
    assert client.get("/api/health").json()["status"]=="ok"
    assert client.get("/api/voice/session").status_code==405
    assert client.post("/api/voice/session").status_code==401
    assert client.get("/api/private/calls").status_code==401
    register(client)
    assert client.get("/api/admin/analytics").status_code==403
    assert client.get("/api/agent/leads").status_code==403

def test_integration_status_does_not_claim_unimplemented_providers(client,monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID","configured-placeholder")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET","configured-placeholder")
    monkeypatch.setenv("EMAIL_PROVIDER_API_KEY","configured-placeholder")
    result=client.get("/api/integrations/status").json()
    assert result["google_calendar"]=={"configured":False,"mode":"not_implemented"}
    assert result["email"]=={"configured":False,"mode":"not_implemented"}
    assert "configured-placeholder" not in str(result)

def test_health_checks_database_and_untrusted_origin_is_rejected(client):
    assert client.get("/api/health").json()=={"status":"ok","database":"ok"}
    cors=client.get("/api/properties",headers={"Origin":"http://localhost:3000"})
    assert cors.headers["access-control-allow-origin"]=="http://localhost:3000"
    assert cors.headers["access-control-allow-credentials"]=="true"
    denied=client.post("/api/auth/register",headers={"Origin":"https://untrusted.example"},json={"email":"a@example.com","password":"safePassword123"})
    assert denied.status_code==403

def test_missing_production_database_uses_sqlite_fallback(monkeypatch):
    monkeypatch.delenv("DATABASE_URL",raising=False)
    assert database_url_from_env("production")=="sqlite:///./voicedesk.db"
    engine=create_database_engine(None,"production")
    try:
        assert engine.url.drivername=="sqlite"
        assert engine.dialect.create_connect_args(engine.url)[1]["check_same_thread"] is False
    finally:
        engine.dispose()
    assert database_url_from_env("development")=="sqlite:///./voicedesk.db"

def test_startup_initializes_tables_safely_and_idempotently(monkeypatch):
    test_engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    monkeypatch.setattr("app.engine",test_engine)
    try:
        initialize_database()
        first_tables=set(inspect(test_engine).get_table_names())
        initialize_database()
        assert "users" in first_tables and "properties" in first_tables
        assert set(inspect(test_engine).get_table_names())==first_tables
    finally:
        test_engine.dispose()

def test_postgres_url_normalization_and_small_pool():
    engine=create_database_engine("postgresql://unit:unit@localhost/voicedesk","production")
    try:
        assert engine.url.drivername=="postgresql+psycopg"
        assert engine.pool.size()==2 and engine.pool._max_overflow==0
        assert engine.pool._pre_ping is True
    finally:
        engine.dispose()

def test_vercel_engine_does_not_retain_connection_pool(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    engine=create_database_engine("postgresql://unit:unit@localhost/voicedesk","production")
    try:
        assert isinstance(engine.pool,NullPool)
    finally:
        engine.dispose()

def test_vercel_environment_defaults_to_production(monkeypatch):
    monkeypatch.delenv("APP_ENV",raising=False)
    monkeypatch.setenv("VERCEL_ENV","production")
    assert default_app_environment()=="production"
    monkeypatch.delenv("VERCEL_ENV")
    monkeypatch.delenv("VERCEL",raising=False)
    monkeypatch.delenv("RENDER",raising=False)
    assert default_app_environment()=="development"

def test_voice_is_disabled_by_default(client,monkeypatch):
    monkeypatch.setenv("BOLNA_API_KEY","configured-test-key")
    monkeypatch.setenv("BOLNA_AGENT_ID","configured-test-agent")
    monkeypatch.delenv("BOLNA_WEB_CALL_ENABLED",raising=False)
    assert client.get("/api/integrations/status").json()["bolna"]["configured"] is False
    register(client)
    response=client.post("/api/voice/session")
    assert response.status_code==503

def test_production_cookie_requires_secure_flag():
    assert cookie_settings("production")== (True,"none")
    assert cookie_settings("development")== (False,"lax")
    with pytest.raises(RuntimeError,match="COOKIE_SECURE"):
        cookie_settings("production","false","lax")

def test_production_frontend_origin_must_be_exact_https_origin():
    assert validate_frontend_origin("https://site.example/","production")=="https://site.example"
    with pytest.raises(RuntimeError,match="HTTPS frontend origin"):
        validate_frontend_origin("http://site.example","production")
    with pytest.raises(RuntimeError,match="HTTPS frontend origin"):
        validate_frontend_origin("https://site.example/path","production")

def test_bolna_webhook_requires_shared_secret(client,monkeypatch):
    monkeypatch.setenv("BOLNA_WEBHOOK_SECRET","test-only-secret")
    monkeypatch.setenv("BOLNA_AGENT_ID","test-agent")
    denied=client.post("/api/integrations/bolna/webhook",json={"id":"run-1","agent_id":"test-agent","status":"completed"})
    assert denied.status_code==401
    wrong_agent=client.post("/api/integrations/bolna/webhook",headers={"X-VoiceDesk-Webhook-Secret":"test-only-secret"},json={"id":"run-1","agent_id":"other-agent","status":"completed"})
    assert wrong_agent.status_code==422

def test_authenticated_bolna_session_uses_backend_key_and_persists_run(client,monkeypatch):
    import app as app_module
    monkeypatch.setenv("BOLNA_API_KEY","server-only-test-key")
    monkeypatch.setenv("BOLNA_AGENT_ID","agent-test-id")
    monkeypatch.setenv("BOLNA_WEB_CALL_ENABLED","true")
    class ProviderResponse:
        status_code=200
        def json(self): return {"run_id":"provider-run-test","agent_id":"agent-test-id","token":"ephemeral-session-token"}
    class ProviderClient:
        def __init__(self,**kwargs): assert "timeout" in kwargs
        async def __aenter__(self): return self
        async def __aexit__(self,*args): return None
        async def post(self,url,headers,json):
            assert url=="https://api.bolna.ai/web-call/freeswitch-session"
            assert headers["Authorization"]=="Bearer server-only-test-key"
            assert json=={"agent_id":"agent-test-id"}
            return ProviderResponse()
    monkeypatch.setattr(app_module.httpx,"AsyncClient",ProviderClient)
    assert client.post("/api/voice/session").status_code==401
    register(client)
    response=client.post("/api/voice/session")
    assert response.status_code==200,response.text
    assert response.json()["run_id"]=="provider-run-test"
    assert "server-only-test-key" not in response.text
    history=client.get("/api/private/calls").json()
    assert len(history)==1 and history[0]["id"]=="provider-run-test"

def test_demo_seed_refuses_production_without_explicit_confirmation(monkeypatch):
    import sys
    from seed_database import main
    monkeypatch.setenv("APP_ENV","production")
    monkeypatch.setattr(sys,"argv",["seed_database.py"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code==2

def test_demo_seed_refuses_vercel_production_without_confirmation(monkeypatch):
    import sys
    from seed_database import main
    monkeypatch.delenv("APP_ENV",raising=False)
    monkeypatch.setenv("VERCEL_ENV","production")
    monkeypatch.setattr(sys,"argv",["seed_database.py"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code==2

def test_invalid_email_and_short_password_are_rejected(client):
    assert client.post("/api/auth/register",json={"email":"not-an-email","password":"safePassword123"}).status_code==422
    assert client.post("/api/auth/register",json={"email":"valid@example.com","password":"short"}).status_code==422

def test_customer_booking_idempotency_and_conflict(client):
    register(client)
    # Pick the next weekday at 10:00 in Bengaluru, represented as UTC.
    now=datetime.now(ZoneInfo("Asia/Kolkata"));day=now.date()+timedelta(days=1)
    while day.weekday()>5: day+=timedelta(days=1)
    start=datetime(day.year,day.month,day.day,10,tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)
    payload={"property_id":1,"start_at":start.isoformat(),"idempotency_key":"customer-booking-001"}
    first=client.post("/api/bookings",json=payload);assert first.status_code==200,first.text
    assert first.json()["status"]=="requested"
    replay=client.post("/api/bookings",json=payload);assert replay.status_code==200 and replay.json()["id"]==first.json()["id"]
    client.post("/api/auth/logout")
    register(client,"second@example.com")
    conflict=client.post("/api/bookings",json={**payload,"idempotency_key":"customer-booking-002"})
    assert conflict.status_code==409

def test_booking_cancel_and_saved_properties(client):
    register(client)
    now=datetime.now(ZoneInfo("Asia/Kolkata"));day=now.date()+timedelta(days=1)
    while day.weekday()>5: day+=timedelta(days=1)
    start=datetime(day.year,day.month,day.day,12,tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)
    booking=client.post("/api/bookings",json={"property_id":1,"start_at":start.isoformat(),"idempotency_key":"cancel-booking-01"})
    assert booking.status_code==200
    assert client.post(f"/api/bookings/{booking.json()['id']}/cancel").json()["status"]=="cancelled"
    assert client.post("/api/customer/saved-properties/1").json()["saved"] is True
    assert len(client.get("/api/customer/saved-properties").json())==1

def test_booking_reschedule_updates_persisted_time(client):
    register(client)
    now=datetime.now(ZoneInfo("Asia/Kolkata"));day=now.date()+timedelta(days=1)
    while day.weekday()>5: day+=timedelta(days=1)
    first=datetime(day.year,day.month,day.day,10,tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)
    booking=client.post("/api/bookings",json={"property_id":1,"start_at":first.isoformat(),"idempotency_key":"reschedule-create-01"})
    assert booking.status_code==200
    later=first+timedelta(hours=2)
    result=client.post(f"/api/bookings/{booking.json()['id']}/reschedule",json={"property_id":1,"start_at":later.isoformat(),"idempotency_key":"reschedule-new-0001"})
    assert result.status_code==200 and result.json()["status"]=="rescheduled"
    assert datetime.fromisoformat(result.json()["start_at"])==later
