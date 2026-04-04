import csv
import random
from locust import HttpUser, task, between

# 1. Load the valid user IDs into memory ONCE
# This runs before the swarm starts, keeping the attack blazing fast
with open("C:/Users/Kj/Desktop/Coding/Flash-Sale-API/users_db.csv", "r") as f:
    reader = csv.reader(f)
    # Assumes the CSV is just a list of UUIDs. 
    # If your CSV export included a "user_id" header row, change this to: [row[0] for row in reader][1:]
    VALID_USER_IDS = [row[0] for row in reader if row]

class TicketBuyer(HttpUser):
    # Set to 0 to simulate the instantaneous flash sale spike
    wait_time = between(0, 0)

    def on_start(self):
        # 2. Assign a real, database-verified user ID to this bot
        self.user_id = random.choice(VALID_USER_IDS)
        
        # Make sure this is still a valid tier_id from your database!
        self.tier_id = "e72a63e4-b8f7-45aa-9b8b-6e054981d493"

    @task
    def purchase_flow(self):
        # Step 1: Lock ticket
        lock_res = self.client.post(
            "/tickets/lock",
            json={
                "tier_id": self.tier_id,
                "user_id": self.user_id
            }
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
                "user_id": self.user_id,
                "ticket_ids": [ticket_id]
            }
        )

        if order_res.status_code != 201:
            print(f"ORDER FAILED: {order_res.status_code} - {order_res.text}")
            
            # Release lock if purchase failed
            self.client.delete(
                f"/tickets/{ticket_id}/lock",
                params={"user_id": self.user_id}
            )