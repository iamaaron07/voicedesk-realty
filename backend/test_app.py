from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import app, Base, db_dep, Agency, Agent, Property

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
