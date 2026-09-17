import csv
import os
import random
import uuid
from pathlib import Path
from dotenv import load_dotenv
from jose import jwt
from locust import HttpUser, task, between

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "flash-sale-secret-key-change-in-production")
ALGORITHM = "HS256"

# Load valid user IDs from CSV if available, or fallback to empty list
CSV_PATH = Path(__file__).resolve().parent.parent.parent / "users_db.csv"
if not CSV_PATH.exists():
    CSV_PATH = Path("users_db.csv")

VALID_USER_IDS: list[str] = []
if CSV_PATH.exists():
    try:
        with open(CSV_PATH, "r") as f:
            reader = csv.reader(f)
            VALID_USER_IDS = [row[0] for row in reader if row]
    except Exception:
        VALID_USER_IDS = []


def create_access_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id}, SECRET_KEY, algorithm=ALGORITHM)


class TicketBuyer(HttpUser):
    # Set to 0 to simulate the instantaneous flash sale spike
    wait_time = between(0, 0)

    def on_start(self):
        # Use user from CSV if available, otherwise generate a unique UUID
        if VALID_USER_IDS:
            self.user_id = random.choice(VALID_USER_IDS)
        else:
            self.user_id = str(uuid.uuid4())

        self.token = create_access_token(self.user_id)
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Make sure this is a valid tier_id from your database
        self.tier_id = "c77dc8f1-12e8-4bc0-b009-03471f8ad447"

    @task
    def purchase_flow(self):
        # Step 1: Lock ticket
        lock_res = self.client.post(
            "/tickets/lock",
            json={
                "tier_id": self.tier_id,
            },
            headers=self.headers,
        )

        if lock_res.status_code == 422:
            print(f"PYDANTIC ERROR: {lock_res.text}")
            return

        if lock_res.status_code != 200:
            return  # No ticket available or lock conflict

        ticket = lock_res.json()
        ticket_id = ticket.get("ticket_id")
        if not ticket_id:
            return

        # Step 2: Create order
        order_res = self.client.post(
            "/orders",
            json={
                "ticket_ids": [ticket_id],
            },
            headers=self.headers,
        )

        if order_res.status_code != 201:
            print(f"ORDER FAILED: {order_res.status_code} - {order_res.text}")

            # Release lock if purchase failed
            self.client.delete(
                f"/tickets/{ticket_id}/lock",
                headers=self.headers,
            )