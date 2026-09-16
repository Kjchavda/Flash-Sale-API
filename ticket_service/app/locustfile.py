import csv
import os
import random
from pathlib import Path
from dotenv import load_dotenv
from jose import jwt
from locust import HttpUser, task, between

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "flash-sale-secret-key-change-in-production")
ALGORITHM = "HS256"

# 1. Load the valid user IDs into memory ONCE
# This runs before the swarm starts, keeping the attack blazing fast
with open("C:/Users/Kj/Desktop/Coding/Flash-Sale-API/users_db.csv", "r") as f:
    reader = csv.reader(f)
    VALID_USER_IDS = [row[0] for row in reader if row]

def create_access_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id}, SECRET_KEY, algorithm=ALGORITHM)


class TicketBuyer(HttpUser):
    # Set to 0 to simulate the instantaneous flash sale spike
    wait_time = between(0, 0)

    def on_start(self):
        # 2. Assign a real, database-verified user ID to this bot
        self.user_id = random.choice(VALID_USER_IDS)
        self.token = create_access_token(self.user_id)
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Make sure this is still a valid tier_id from your database!
        self.tier_id = "e72a63e4-b8f7-45aa-9b8b-6e054981d493"

    @task
    def purchase_flow(self):
        # Step 1: Lock ticket
        lock_res = self.client.post(
            "/tickets/lock",
            json={
                "tier_id": self.tier_id
            },
            headers=self.headers,
        )

        if lock_res.status_code == 422:
            print(f"PYDANTIC ERROR: {lock_res.text}")
            return
            
        if lock_res.status_code != 200:
            return  # no ticket available / conflict

        ticket = lock_res.json()
        ticket_id = ticket["ticket_id"]

        # Step 2: Create order
        order_res = self.client.post(
            "/orders",
            json={
                "ticket_ids": [ticket_id]
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