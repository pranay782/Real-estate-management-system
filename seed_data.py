"""
seed_data.py
Optional: populates the database with a handful of sample properties,
agents, clients, and a couple of inquiries (one closed) so the dashboard
charts and the "Matching Properties" / close-deal flow have something to
demo immediately instead of an empty app.

Run once:
    python seed_data.py

Safe to re-run - it checks counts first and skips if data already exists.
"""

from datetime import datetime, timedelta
import random

from db import get_db, ensure_indexes
from auth import ensure_default_admin

SAMPLE_PROPERTIES = [
    {"title": "Sunrise Heights 3BHK", "type": "Apartment", "price": 8500000, "location": "Andheri West",
     "bedrooms": 3, "bathrooms": 2, "area_sqft": 1250, "status": "available"},
    {"title": "Green Meadows Villa", "type": "Villa", "price": 22000000, "location": "Lonavala",
     "bedrooms": 5, "bathrooms": 4, "area_sqft": 3800, "status": "available"},
    {"title": "Central Plaza Office", "type": "Commercial", "price": 15000000, "location": "Bandra Kurla Complex",
     "bedrooms": 0, "bathrooms": 2, "area_sqft": 2000, "status": "available"},
    {"title": "Riverside Plot", "type": "Plot", "price": 4500000, "location": "Panvel",
     "bedrooms": 0, "bathrooms": 0, "area_sqft": 5000, "status": "available"},
    {"title": "Palm Residency 2BHK", "type": "Apartment", "price": 6200000, "location": "Thane West",
     "bedrooms": 2, "bathrooms": 2, "area_sqft": 950, "status": "sold"},
    {"title": "Skyline Towers 4BHK", "type": "Apartment", "price": 12500000, "location": "Powai",
     "bedrooms": 4, "bathrooms": 3, "area_sqft": 1900, "status": "rented"},
]

SAMPLE_AGENTS = [
    {"name": "Priya Sharma", "contact": "priya.sharma@example.com", "region": "Western Suburbs", "experience_years": 6},
    {"name": "Rahul Verma", "contact": "rahul.verma@example.com", "region": "South Mumbai", "experience_years": 3},
    {"name": "Ayesha Khan", "contact": "ayesha.khan@example.com", "region": "Navi Mumbai", "experience_years": 8},
]

SAMPLE_CLIENTS = [
    {"name": "Karan Mehta", "contact": "karan.mehta@example.com", "budget": 9000000,
     "preferred_location": "Andheri", "requirement_type": "buy"},
    {"name": "Sneha Patil", "contact": "sneha.patil@example.com", "budget": 7000000,
     "preferred_location": "Thane", "requirement_type": "rent"},
    {"name": "Vikram Desai", "contact": "vikram.desai@example.com", "budget": 25000000,
     "preferred_location": "Lonavala", "requirement_type": "buy"},
]


def run():
    ensure_indexes()
    ensure_default_admin()
    db = get_db()

    if db.properties.count_documents({}) == 0:
        for p in SAMPLE_PROPERTIES:
            p["image_ids"] = []
            p["date_listed"] = datetime.utcnow() - timedelta(days=random.randint(1, 120))
        db.properties.insert_many(SAMPLE_PROPERTIES)
        print(f"Inserted {len(SAMPLE_PROPERTIES)} sample properties.")
    else:
        print("Properties already exist - skipping.")

    if db.agents.count_documents({}) == 0:
        db.agents.insert_many(SAMPLE_AGENTS)
        print(f"Inserted {len(SAMPLE_AGENTS)} sample agents.")
    else:
        print("Agents already exist - skipping.")

    if db.clients.count_documents({}) == 0:
        agents = list(db.agents.find())
        for c in SAMPLE_CLIENTS:
            c["assigned_agent_id"] = random.choice(agents)["_id"] if agents else None
        db.clients.insert_many(SAMPLE_CLIENTS)
        print(f"Inserted {len(SAMPLE_CLIENTS)} sample clients.")
    else:
        print("Clients already exist - skipping.")

    if db.inquiries.count_documents({}) == 0:
        client = db.clients.find_one({})
        prop = db.properties.find_one({"status": "available"})
        agent = db.agents.find_one({})
        if client and prop and agent:
            db.inquiries.insert_one({
                "client_id": client["_id"],
                "property_id": prop["_id"],
                "agent_id": agent["_id"],
                "status": "Site Visit",
                "date_created": datetime.utcnow() - timedelta(days=5),
                "closing_price": None,
            })
            print("Inserted 1 sample inquiry (status: Site Visit).")
    else:
        print("Inquiries already exist - skipping.")

    print("\nSeed complete. Default login: admin / admin123")


if __name__ == "__main__":
    run()
