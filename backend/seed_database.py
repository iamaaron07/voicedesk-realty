"""Explicitly seed fictional Bengaluru demo listings after running Alembic."""
import argparse
import os

from sqlalchemy import select, func

from app import SessionLocal, Agency, Agent, Property

LOCALITIES = ["Indiranagar", "Whitefield", "Koramangala", "HSR Layout", "Electronic City"]
AMENITIES = [["Balcony", "Lift"], ["Parking", "Security"], ["Gym", "Clubhouse"], ["Garden", "Power backup"], ["Metro access", "Water supply"]]
FEATURED = [
    ("Sunlit residence in Indiranagar", "Indiranagar", 68000, 2, "A thoughtfully planned demo home close to cafés and metro links.", 204000, ["Lift", "Balcony"]),
    ("Garden-facing home in Whitefield", "Whitefield", 52000, 3, "Bright, spacious demo living with landscaped community spaces.", 156000, ["Garden", "Parking"]),
    ("Calm Koramangala apartment", "Koramangala", 74000, 2, "Modern demo interiors in a well-connected central neighborhood.", 222000, ["Gym", "Security"]),
    ("HSR family home", "HSR Layout", 46000, 3, "Generous demo rooms and everyday conveniences nearby.", 138000, ["Balcony", "Parking"]),
]

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-production-demo-seed", action="store_true", help="Required before writing fictional listings in production")
    args = parser.parse_args()
    runtime_env = os.getenv("APP_ENV", "production" if os.getenv("RENDER") else "development").lower()
    if runtime_env == "production" and not args.confirm_production_demo_seed:
        parser.error("Refusing to seed demo data in production without --confirm-production-demo-seed.")

    with SessionLocal.begin() as db:
        agency = db.scalar(select(Agency).order_by(Agency.id).limit(1))
        if agency is None:
            agency = Agency(name="VoiceDesk Demo Realty")
            db.add(agency)
            db.flush()
        agents = db.scalars(select(Agent).where(Agent.agency_id == agency.id).order_by(Agent.id)).all()
        if not agents:
            agents = [Agent(agency_id=agency.id, name=name) for name in ["Asha Rao", "Kiran Mehta", "Neha Iyer", "Rohan Shah", "Maya Nair"]]
            db.add_all(agents)
            db.flush()
        existing = int(db.scalar(select(func.count()).select_from(Property)) or 0)
        for n in range(existing, 30):
            if n < len(FEATURED):
                title, locality, price, beds, description, deposit, amenities = FEATURED[n]
                db.add(Property(title=title, locality=locality, price=price, beds=beds, description=description, deposit=deposit, amenities=amenities, area_sqft=650 + beds * 280, furnishing="semi-furnished", assigned_agent_id=agents[n % len(agents)].id, demo=True))
                continue
            locality = LOCALITIES[n % len(LOCALITIES)]
            beds = 1 + n % 4
            price = 35000 + (n * 3700) % 60000
            db.add(Property(
                title=f"Demo {beds}-bed home near {locality}",
                locality=locality,
                price=price,
                beds=beds,
                description=f"Fictional demo listing with a practical layout in {locality}.",
                deposit=price * 3,
                amenities=AMENITIES[n % len(AMENITIES)],
                area_sqft=650 + beds * 280,
                furnishing=["furnished", "semi-furnished", "unfurnished"][n % 3],
                assigned_agent_id=agents[n % len(agents)].id,
                demo=True,
            ))
    print("Ensured 30 fictional demo properties are present.")

if __name__ == "__main__":
    main()
