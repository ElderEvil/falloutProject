"""Game loop and game control tasks for load testing."""

from utils import pick_random

from locust import TaskSet, task


class GameTaskSet(TaskSet):
    """Task set for game loop operations."""

    @task(5)
    def get_game_state(self):
        """Get game state for a vault."""
        vault_id = pick_random(self.user.vault_ids)
        if not vault_id:
            return

        self.user.authenticated_get(
            f"/api/v1/game/vaults/{vault_id}/game-state",
            name="GET /game/vaults/{id}/game-state",
        )

    @task(2)
    def manual_tick(self):
        """Trigger a manual game tick."""
        vault_id = pick_random(self.user.vault_ids)
        if not vault_id:
            return

        self.user.authenticated_post(
            f"/api/v1/game/vaults/{vault_id}/tick",
            name="POST /game/vaults/{id}/tick",
        )

    @task(1)
    def pause_vault(self):
        """Pause a vault's game loop."""
        vault_id = pick_random(self.user.vault_ids)
        if not vault_id:
            return

        self.user.authenticated_post(
            f"/api/v1/game/vaults/{vault_id}/pause",
            name="POST /game/vaults/{id}/pause",
        )

    @task(1)
    def resume_vault(self):
        """Resume a paused vault's game loop."""
        vault_id = pick_random(self.user.vault_ids)
        if not vault_id:
            return

        self.user.authenticated_post(
            f"/api/v1/game/vaults/{vault_id}/resume",
            name="POST /game/vaults/{id}/resume",
        )

    @task(3)
    def get_incidents(self):
        """Get list of incidents for a vault."""
        vault_id = pick_random(self.user.vault_ids)
        if not vault_id:
            return

        self.user.authenticated_get(
            f"/api/v1/game/vaults/{vault_id}/incidents",
            name="GET /game/vaults/{id}/incidents",
        )

    @task(2)
    def get_quests(self):
        """Get quests for a vault."""
        vault_id = pick_random(self.user.vault_ids)
        if not vault_id:
            return

        self.user.authenticated_get(
            f"/api/v1/quests/{vault_id}/",
            name="GET /quests/{vault_id}/",
        )

    @task(2)
    def get_objectives(self):
        """Get objectives for a vault."""
        vault_id = pick_random(self.user.vault_ids)
        if not vault_id:
            return

        self.user.authenticated_get(
            f"/api/v1/objectives/{vault_id}/",
            name="GET /objectives/{vault_id}/",
        )
