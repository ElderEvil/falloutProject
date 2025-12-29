"""Vault-related tasks for load testing."""

from utils import generate_vault_number, pick_random

from locust import TaskSet, task


class VaultTaskSet(TaskSet):
    """Task set for vault operations."""

    @task(10)
    def list_vaults(self):
        """List all user's vaults."""
        response = self.user.authenticated_get(
            "/api/v1/vaults/",
            name="GET /vaults/",
        )

        # Store vault IDs for later use
        if response.status_code == 200:
            vaults = response.json()
            if vaults:
                self.user.vault_ids = [v["id"] for v in vaults]

    @task(5)
    def get_vault_details(self):
        """Get details of a specific vault."""
        vault_id = pick_random(self.user.vault_ids)
        if not vault_id:
            return

        self.user.authenticated_get(
            f"/api/v1/vaults/{vault_id}",
            name="GET /vaults/{id}",
        )

    @task(2)
    def create_vault(self):
        """Create a new vault."""
        vault_number = generate_vault_number()

        response = self.user.authenticated_post(
            "/api/v1/vaults/initiate",
            json={"number": vault_number},
            name="POST /vaults/initiate",
        )

        # Store the new vault ID
        if response.status_code == 201:
            vault = response.json()
            if vault and "id" in vault:
                self.user.vault_ids.append(vault["id"])

    @task(3)
    def get_vault_rooms(self):
        """Get rooms for a vault."""
        vault_id = pick_random(self.user.vault_ids)
        if not vault_id:
            return

        self.user.authenticated_get(
            f"/api/v1/rooms/vault/{vault_id}/",
            name="GET /rooms/vault/{id}/",
        )

    @task(3)
    def get_vault_dwellers(self):
        """Get dwellers for a vault."""
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
