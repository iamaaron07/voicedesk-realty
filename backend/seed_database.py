"""Load fictional Bengaluru demo listings; never use these as real inventory."""
from sqlalchemy import select
from app import SessionLocal, Property, Agent

LOCALITIES=["Indiranagar","Whitefield","Koramangala","HSR Layout","Electronic City"]
AMENITIES=[["Balcony","Lift"],["Parking","Security"],["Gym","Clubhouse"],["Garden","Power backup"],["Metro access","Water supply"]]
with SessionLocal() as db:
    agents=db.scalars(select(Agent).order_by(Agent.id)).all()
    existing=db.query(Property).count()
    for n in range(existing,30):
        locality=LOCALITIES[n%len(LOCALITIES)];beds=1+n%4;price=35000+(n*3700)%60000
        db.add(Property(title=f"Demo {beds}-bed home near {locality}",locality=locality,price=price,beds=beds,description=f"Fictional demo listing with a practical layout in {locality}.",deposit=price*3,amenities=AMENITIES[n%len(AMENITIES)],area_sqft=650+beds*280,furnishing=["furnished","semi-furnished","unfurnished"][n%3],assigned_agent_id=agents[n%len(agents)].id if agents else None,demo=True))
    db.commit()
print("Ensured 30 fictional demo properties are present.")
