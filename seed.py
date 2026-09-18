"""Fills the database with demo data, so you can try the API and test tenant isolation.

It creates 2 companies (Acme Ltd and Globex Corp). Each company gets:
  1 admin, 1 manager, 2 sales agents, 25 leads (3 converted to customers),
  8 customers in total, 8 contacts, 10 deals, 20 activities and some notes.

Every user's password is:  Password123!
Logins:  admin@acme.example, manager@acme.example, agent1@acme.example, agent2@acme.example
         admin@globex.example, manager@globex.example, ...

Usage:  python seed.py   (run python migrate.py first)
It does nothing if the demo data already exists.
"""
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.database import get_engine
from app.security import hash_password

DEMO_PASSWORD = "Password123!"

COMPANIES = [
    {"name": "Acme Ltd", "domain": "acme.example"},
    {"name": "Globex Corp", "domain": "globex.example"},
]

FIRST_NAMES = ["John", "Mary", "Ahmed", "Priya", "Liam", "Olivia", "Noah", "Emma", "Raj", "Sofia",
               "Lucas", "Mia", "Omar", "Chloe", "Ethan", "Grace", "Arjun", "Hannah", "Leo", "Zara"]
LAST_NAMES = ["Smith", "Jones", "Khan", "Patel", "Brown", "Taylor", "Wilson", "Singh", "Evans", "Clark"]
COMPANY_NAMES = ["Blue Ocean Ltd", "Green Leaf plc", "Red Rock Co", "Swift Logistics", "Nova Tech",
                 "Bright Foods", "Peak Fitness", "Urban Homes"]
JOB_TITLES = ["CEO", "CTO", "Head of Sales", "Office Manager", "Marketing Lead", "Buyer"]
LEAD_STATUSES = ["NEW", "CONTACTED", "QUALIFIED", "PROPOSAL", "NEGOTIATION", "WON", "LOST"]
LEAD_SOURCES = ["WEBSITE", "REFERRAL", "LINKEDIN", "EMAIL", "PHONE", "ADVERTISEMENT", "OTHER"]
DEAL_STAGES = ["NEW", "QUALIFIED", "PROPOSAL", "NEGOTIATION", "WON", "LOST"]
ACTIVITY_TYPES = ["CALL", "EMAIL", "MEETING", "TASK", "NOTE"]

# A fixed seed means the "random" data is the same every time.
rng = random.Random(42)


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def insert(db, sql, params):
    """Run an INSERT and return the new row's id."""
    return db.execute(text(sql), params).lastrowid


def random_person():
    first_name = rng.choice(FIRST_NAMES)
    last_name = rng.choice(LAST_NAMES)
    email = f"{first_name}.{last_name}{rng.randint(1, 999)}@example.com".lower()
    return first_name, last_name, email


def create_users(db, company_id, domain, password_hash):
    users = {}
    for key, name, role in [
        ("admin", "Admin User", "ADMIN"),
        ("manager", "Manager User", "MANAGER"),
        ("agent1", "Sales Agent One", "SALES_AGENT"),
        ("agent2", "Sales Agent Two", "SALES_AGENT"),
    ]:
        users[key] = insert(db, """
            INSERT INTO users (company_id, name, email, password_hash, role)
            VALUES (:company_id, :name, :email, :password_hash, :role)
        """, {"company_id": company_id, "name": name, "email": f"{key}@{domain}",
              "password_hash": password_hash, "role": role})
    return users


def create_leads(db, company_id, agent_ids):
    lead_ids = []
    for _ in range(25):
        first_name, last_name, email = random_person()
        lead_ids.append(insert(db, """
            INSERT INTO leads (company_id, assigned_to, first_name, last_name, email, phone,
                               company_name, job_title, source, status, estimated_value)
            VALUES (:company_id, :assigned_to, :first_name, :last_name, :email, :phone,
                    :company_name, :job_title, :source, :status, :estimated_value)
        """, {
            "company_id": company_id,
            "assigned_to": rng.choice(agent_ids),
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": f"07700 9{rng.randint(10000, 99999)}",
            "company_name": rng.choice(COMPANY_NAMES),
            "job_title": rng.choice(JOB_TITLES),
            "source": rng.choice(LEAD_SOURCES),
            "status": rng.choice(LEAD_STATUSES[:5]),
            "estimated_value": rng.randint(5, 200) * 100,
        }))
    return lead_ids


def convert_leads(db, company_id, lead_ids, admin_id):
    """Turn the first 3 leads into customers, the same way the API does."""
    customer_ids = []
    for lead_id in lead_ids[:3]:
        lead = db.execute(text("SELECT * FROM leads WHERE id = :id"), {"id": lead_id}).mappings().one()
        customer_id = insert(db, """
            INSERT INTO customers (company_id, lead_id, assigned_to, first_name, last_name,
                                   email, phone, company_name)
            VALUES (:company_id, :lead_id, :assigned_to, :first_name, :last_name,
                    :email, :phone, :company_name)
        """, {"company_id": company_id, "lead_id": lead_id, "assigned_to": lead["assigned_to"],
              "first_name": lead["first_name"], "last_name": lead["last_name"], "email": lead["email"],
              "phone": lead["phone"], "company_name": lead["company_name"]})
        db.execute(text("UPDATE leads SET status = 'WON', converted_at = UTC_TIMESTAMP() WHERE id = :id"),
                   {"id": lead_id})
        insert(db, """
            INSERT INTO activities (company_id, user_id, lead_id, customer_id, type, title, completed_at)
            VALUES (:company_id, :user_id, :lead_id, :customer_id, 'NOTE', 'Lead converted to customer',
                    UTC_TIMESTAMP())
        """, {"company_id": company_id, "user_id": admin_id, "lead_id": lead_id, "customer_id": customer_id})
        customer_ids.append(customer_id)
    return customer_ids


def create_customers(db, company_id, agent_ids, how_many):
    customer_ids = []
    for _ in range(how_many):
        first_name, last_name, email = random_person()
        customer_ids.append(insert(db, """
            INSERT INTO customers (company_id, assigned_to, first_name, last_name, email, company_name, status)
            VALUES (:company_id, :assigned_to, :first_name, :last_name, :email, :company_name, :status)
        """, {"company_id": company_id, "assigned_to": rng.choice(agent_ids), "first_name": first_name,
              "last_name": last_name, "email": email, "company_name": rng.choice(COMPANY_NAMES),
              "status": rng.choice(["ACTIVE", "ACTIVE", "INACTIVE"])}))
    return customer_ids


def create_contacts(db, company_id, owner_ids):
    for _ in range(8):
        first_name, last_name, email = random_person()
        insert(db, """
            INSERT INTO contacts (company_id, owner_id, first_name, last_name, email, job_title, company_name)
            VALUES (:company_id, :owner_id, :first_name, :last_name, :email, :job_title, :company_name)
        """, {"company_id": company_id, "owner_id": rng.choice(owner_ids), "first_name": first_name,
              "last_name": last_name, "email": email, "job_title": rng.choice(JOB_TITLES),
              "company_name": rng.choice(COMPANY_NAMES)})


def create_deals(db, company_id, agent_ids, customer_ids):
    deal_ids = []
    for number in range(10):
        deal_ids.append(insert(db, """
            INSERT INTO deals (company_id, customer_id, assigned_to, title, description, value,
                               stage, expected_close_date)
            VALUES (:company_id, :customer_id, :assigned_to, :title, :description, :value,
                    :stage, :expected_close_date)
        """, {"company_id": company_id, "customer_id": rng.choice(customer_ids),
              "assigned_to": rng.choice(agent_ids), "title": f"Deal #{number + 1} - {rng.choice(COMPANY_NAMES)}",
              "description": "Demo deal created by seed.py", "value": rng.randint(10, 500) * 100,
              "stage": rng.choice(DEAL_STAGES),
              "expected_close_date": (utc_now() + timedelta(days=rng.randint(5, 90))).date()}))
    return deal_ids


def create_activities_and_notes(db, company_id, user_ids, lead_ids, deal_ids):
    for number in range(20):
        due_at = utc_now() + timedelta(hours=rng.randint(-48, 96))
        # Make the first activity due in 30 minutes, so the reminder worker has something to do.
        if number == 0:
            due_at = utc_now() + timedelta(minutes=30)
        insert(db, """
            INSERT INTO activities (company_id, user_id, lead_id, deal_id, type, title, description, due_at)
            VALUES (:company_id, :user_id, :lead_id, :deal_id, :type, :title, :description, :due_at)
        """, {"company_id": company_id, "user_id": rng.choice(user_ids), "lead_id": rng.choice(lead_ids),
              "deal_id": rng.choice(deal_ids), "type": rng.choice(ACTIVITY_TYPES),
              "title": f"Follow-up #{number + 1}", "description": "Demo activity", "due_at": due_at})

    for lead_id in lead_ids[:10]:
        insert(db, """
            INSERT INTO notes (company_id, lead_id, user_id, content)
            VALUES (:company_id, :lead_id, :user_id, :content)
        """, {"company_id": company_id, "lead_id": lead_id, "user_id": rng.choice(user_ids),
              "content": "Spoke on the phone. Interested, wants a quote next week."})


def seed(engine):
    password_hash = hash_password(DEMO_PASSWORD)

    with engine.begin() as db:
        already_seeded = db.execute(text("SELECT id FROM users WHERE email = 'admin@acme.example'")).first()
        if already_seeded:
            print("Demo data already exists. Nothing to do.")
            return

        starter_plan_id = db.execute(text("SELECT id FROM plans WHERE name = 'STARTER'")).scalar_one()

        for company in COMPANIES:
            company_id = insert(db, "INSERT INTO companies (name, email) VALUES (:name, :email)",
                                {"name": company["name"], "email": f"hello@{company['domain']}"})
            # STARTER, because the FREE plan only allows 3 users and we create 4.
            insert(db, "INSERT INTO subscriptions (company_id, plan_id) VALUES (:company_id, :plan_id)",
                   {"company_id": company_id, "plan_id": starter_plan_id})

            users = create_users(db, company_id, company["domain"], password_hash)
            agent_ids = [users["agent1"], users["agent2"]]
            all_user_ids = list(users.values())

            lead_ids = create_leads(db, company_id, agent_ids)
            customer_ids = convert_leads(db, company_id, lead_ids, users["admin"])
            customer_ids += create_customers(db, company_id, agent_ids, how_many=5)
            create_contacts(db, company_id, all_user_ids)
            deal_ids = create_deals(db, company_id, agent_ids, customer_ids)
            create_activities_and_notes(db, company_id, all_user_ids, lead_ids, deal_ids)

            print(f"Created {company['name']} (id {company_id}) with users, leads, customers, deals and activities.")

    print(f"Done. Log in with e.g. admin@acme.example / {DEMO_PASSWORD}")


if __name__ == "__main__":
    seed(get_engine())
