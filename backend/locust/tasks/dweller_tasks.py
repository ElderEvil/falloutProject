"""Dweller-related tasks for load testing."""

from utils import generate_dweller_name, pick_random

from locust import TaskSet, task


class DwellerTaskSet(TaskSet):
    """Task set for dweller operations."""

    @task(8)
    def list_dwellers(self):
        """List dwellers for a vault."""
        vault_id = pick_random(self.user.vault_ids)
        if not vault_id:
            return

        response = self.user.authenticated_get(
            f"/api/v1/dwellers/vault/{vault_id}/",
            name="GET /dwellers/vault/{id}/",
        )

        # Store dweller IDs
        if response.status_code == 200:
            dwellers = response.json()
            if dwellers:
                self.user.dweller_ids = [d["id"] for d in dwellers]

    @task(5)
    def get_dweller_details(self):
        """Get details of a specific dweller."""
        dweller_id = pick_random(self.user.dweller_ids)
        if not dweller_id:
            return

        self.user.authenticated_get(
            f"/api/v1/dwellers/{dweller_id}",
            name="GET /dwellers/{id}",
        )

    @task(2)
    def create_dweller(self):
        """Create a new dweller."""
        vault_id = pick_random(self.user.vault_ids)
        if not vault_id:
            return

        dweller_name = generate_dweller_name()
        first_name, last_name = dweller_name.split(" ", 1)

        response = self.user.authenticated_post(
            "/api/v1/dwellers/",
            json={
                "first_name": first_name,
                "last_name": last_name,
                "vault_id": vault_id,
            },
            name="POST /dwellers/",
        )

        # Store the new dweller ID
        if response.status_code == 201:
            dweller = response.json()
            if dweller and "id" in dweller:
                self.user.dweller_ids.append(dweller["id"])

    @task(1)
    def update_dweller(self):
        """Update a dweller's information."""
        dweller_id = pick_random(self.user.dweller_ids)
        if not dweller_id:
            return

        # Simple update - toggle happiness
        self.user.authenticated_put(
            f"/api/v1/dwellers/{dweller_id}",
            json={"happiness": 75},
            name="PUT /dwellers/{id}",
        )
