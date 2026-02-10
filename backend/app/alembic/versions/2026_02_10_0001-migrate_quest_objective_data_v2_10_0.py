"""migrate_quest_objective_data_v2_10_0

Revision ID: 3c8d45e9f1a2
Revises: 2675b30246ad
Create Date: 2026-02-10 00:00:00.000000

"""

import json
import re
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import bindparam, text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c8d45e9f1a2"
down_revision: str | None = "2675b30246ad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Migrate existing quest and objective data to structured format."""
    conn = op.get_bind()

    # ========== QUEST DATA MIGRATION ==========

    # Get all quests
    quests_result = conn.execute(
        text("""
        SELECT id, title, short_description, long_description, requirements, rewards
        FROM quest
    """)
    )
    quests = quests_result.fetchall()

    for quest in quests:
        quest_id = quest[0]
        title = quest[1] or ""
        short_desc = quest[2] or ""
        long_desc = quest[3] or ""
        requirements_str = quest[4] or ""
        rewards_str = quest[5] or ""

        # Determine quest type based on keywords
        full_text = (title + " " + short_desc + " " + long_desc).lower()
        if "daily" in full_text:
            quest_type = "DAILY"
        elif "event" in full_text:
            quest_type = "EVENT"
        elif any(word in full_text for word in ["tutorial", "training", "getting started", "main"]):
            quest_type = "MAIN"
        else:
            quest_type = "SIDE"

        # Determine quest category based on keywords
        if any(word in full_text for word in ["combat", "kill", "defeat", "enemy", "fight"]):
            quest_category = "combat"
        elif any(word in full_text for word in ["explore", "wasteland", "scout", "discover"]):
            quest_category = "exploration"
        elif any(word in full_text for word in ["collect", "gather", "find", "acquire"]):
            quest_category = "collection"
        elif any(word in full_text for word in ["build", "construct", "room", "expand"]):
            quest_category = "building"
        elif any(word in full_text for word in ["train", "level up", "upgrade", "improve"]):
            quest_category = "training"
        else:
            quest_category = "general"

        # Update quest with type and category
        conn.execute(
            text("""
                UPDATE quest
                SET quest_type = :quest_type, quest_category = :quest_category
                WHERE id = :quest_id
            """),
            {"quest_type": quest_type, "quest_category": quest_category, "quest_id": quest_id},
        )

        # Parse and create requirements
        if requirements_str and requirements_str.strip() and requirements_str.lower() not in ["none", "n/a", ""]:
            # Split by comma or 'and'
            parts = re.split(r",|\band\b", requirements_str, flags=re.IGNORECASE)

            for raw_part in parts:
                part = raw_part.strip()
                if not part:
                    continue

                req_type = None
                req_data = {}

                # Pattern: "Level X dwellers/rooms/etc"
                level_match = re.match(r"level\s+(\d+)\s+(\w+)", part, re.IGNORECASE)
                if level_match:
                    req_type = "LEVEL"
                    req_data = {"level": int(level_match.group(1)), "target": level_match.group(2).lower()}

                # Pattern: "X caps"
                caps_match = re.match(r"(\d+)\s+caps", part, re.IGNORECASE)
                if caps_match and req_type is None:
                    req_type = "ITEM"
                    req_data = {"item_type": "caps", "amount": int(caps_match.group(1))}

                # Pattern: "X rooms"
                rooms_match = re.match(r"(\d+)\s+rooms?", part, re.IGNORECASE)
                if rooms_match and req_type is None:
                    req_type = "ROOM"
                    req_data = {"amount": int(rooms_match.group(1))}

                # Pattern: "X dwellers"
                dwellers_match = re.match(r"(\d+)\s+dwellers?", part, re.IGNORECASE)
                if dwellers_match and req_type is None:
                    req_type = "DWELLER_COUNT"
                    req_data = {"amount": int(dwellers_match.group(1))}

                # Default: generic requirement
                if req_type is None:
                    req_type = "QUEST_COMPLETED"
                    req_data = {"description": part}

                # Insert requirement
                conn.execute(
                    text("""
                        INSERT INTO questrequirement (id, quest_id, requirement_type, requirement_data, is_mandatory)
                        VALUES (gen_random_uuid(), :quest_id, :req_type, :req_data, true)
                    """),
                    {
                        "quest_id": quest_id,
                        "req_type": req_type,
                        "req_data": json.dumps(req_data) if req_data else "{}",
                    },
                )

        # Parse and create rewards
        if rewards_str and rewards_str.strip() and rewards_str.lower() not in ["none", "n/a", ""]:
            # Split by comma or 'and' (same as requirements)
            parts = re.split(r",|\band\b", rewards_str, flags=re.IGNORECASE)

            for part in parts:
                if not part:
                    continue

                reward_type = None
                reward_data = {}
                reward_chance = 1.0

                # Pattern: "X caps"
                caps_match = re.match(r"(\d+)\s+caps", part, re.IGNORECASE)
                if caps_match:
                    reward_type = "CAPS"
                    reward_data = {"amount": int(caps_match.group(1))}

                # Pattern: "X XP/experience"
                xp_match = re.match(r"(\d+)\s+(?:xp|experience)", part, re.IGNORECASE)
                if xp_match and reward_type is None:
                    reward_type = "EXPERIENCE"
                    reward_data = {"amount": int(xp_match.group(1))}

                # Pattern: "Item Name xN" or "N x Item Name"
                if reward_type is None:
                    quantity_match = re.match(r"(.*?)(?:\s*x\s*(\d+))?$", part, re.IGNORECASE)
                    if quantity_match:
                        item_name = quantity_match.group(1).strip()
                        quantity = int(quantity_match.group(2)) if quantity_match.group(2) else 1
                        if item_name and item_name.lower() not in ["caps", "xp", "experience"]:
                            reward_type = "ITEM"
                            reward_data = {"item_name": item_name, "quantity": quantity}

                # Default: item
                if reward_type is None:
                    reward_type = "ITEM"
                    reward_data = {"item_name": part, "quantity": 1}

                # Insert reward
                conn.execute(
                    text("""
                        INSERT INTO questreward (id, quest_id, reward_type, reward_data, reward_chance)
                        VALUES (gen_random_uuid(), :quest_id, :reward_type, :reward_data, :reward_chance)
                    """),
                    {
                        "quest_id": quest_id,
                        "reward_type": reward_type,
                        "reward_data": json.dumps(reward_data) if reward_data else "{}",
                        "reward_chance": reward_chance,
                    },
                )

    # ========== OBJECTIVE DATA MIGRATION ==========

    # Get all objectives
    objectives_result = conn.execute(
        text("""
        SELECT id, challenge, reward FROM objective
    """)
    )
    objectives = objectives_result.fetchall()

    for obj in objectives:
        obj_id = obj[0]
        challenge_str = obj[1] or ""

        objective_type = None
        target_entity = {}
        target_amount = 1

        challenge_lower = challenge_str.lower()

        # Pattern: "Collect X [Resource]"
        collect_match = re.match(r"collect\s+(\d+)\s+(\w+)", challenge_lower)
        if collect_match:
            objective_type = "collect"
            target_amount = int(collect_match.group(1))
            resource = collect_match.group(2)
            if resource in ["caps", "food", "water", "power"]:
                target_entity = {"resource_type": resource}
            else:
                target_entity = {"item_type": resource}

        # Pattern: "Build X Rooms"
        build_match = re.match(r"build\s+(\d+)\s+rooms?", challenge_lower)
        if build_match and objective_type is None:
            objective_type = "build"
            target_amount = int(build_match.group(1))
            target_entity = {"room_type": "any"}

        # Pattern: "Train X Dwellers"
        train_match = re.match(r"train\s+(\d+)\s+dwellers?", challenge_lower)
        if train_match and objective_type is None:
            objective_type = "train"
            target_amount = int(train_match.group(1))
            target_entity = {"target": "dwellers"}

        # Pattern: "Reach X Population"
        reach_match = re.match(r"reach\s+(\d+)\s+population", challenge_lower)
        if reach_match and objective_type is None:
            objective_type = "reach"
            target_amount = int(reach_match.group(1))
            target_entity = {"target": "population"}

        # Pattern: "Assign X Dwellers"
        assign_match = re.match(r"assign\s+(\d+)\s+dwellers?", challenge_lower)
        if assign_match and objective_type is None:
            objective_type = "assign"
            target_amount = int(assign_match.group(1))
            target_entity = {"target": "dwellers"}

        # Pattern: "Kill X Enemies"
        kill_match = re.match(r"(?:kill|defeat)\s+(\d+)\s+(?:enemies?|creatures?)", challenge_lower)
        if kill_match and objective_type is None:
            objective_type = "kill"
            target_amount = int(kill_match.group(1))
            target_entity = {"target": "enemies"}

        # Generic patterns
        if objective_type is None:
            # Try generic number extraction
            number_match = re.search(r"(\d+)", challenge_str)
            if number_match:
                target_amount = int(number_match.group(1))

            if "collect" in challenge_lower or "gather" in challenge_lower:
                objective_type = "collect"
                target_entity = {"resource_type": "any"}
            elif "build" in challenge_lower or "construct" in challenge_lower:
                objective_type = "build"
                target_entity = {"room_type": "any"}
            elif "train" in challenge_lower:
                objective_type = "train"
                target_entity = {"target": "dwellers"}
            elif "reach" in challenge_lower:
                objective_type = "reach"
                target_entity = {"target": "population"}
            elif "assign" in challenge_lower:
                objective_type = "assign"
                target_entity = {"target": "dwellers"}
            elif "kill" in challenge_lower or "defeat" in challenge_lower:
                objective_type = "kill"
                target_entity = {"target": "enemies"}
            else:
                objective_type = "collect"
                target_entity = {"resource_type": "any"}

        # Update objective with parsed data
        if objective_type:
            conn.execute(
                text("""
                    UPDATE objective
                    SET objective_type = :obj_type, target_entity = :target_entity, target_amount = :target_amount
                    WHERE id = :obj_id
                """),
                {
                    "obj_type": objective_type,
                    "target_entity": json.dumps(target_entity) if target_entity else "{}",
                    "target_amount": target_amount,
                    "obj_id": obj_id,
                },
            )


def downgrade() -> None:
    """Remove migrated data (scoped to rows modified by this migration)."""
    conn = op.get_bind()

    # Find quest IDs that were modified by this migration (have quest_type set)
    result = conn.execute(text("SELECT id FROM quest WHERE quest_type IS NOT NULL"))
    modified_quest_ids = [row[0] for row in result.fetchall()]

    if modified_quest_ids:
        # Delete quest rewards and requirements only for modified quests
        conn.execute(
            text("DELETE FROM questreward WHERE quest_id IN :quest_ids").bindparams(
                bindparam("quest_ids", expanding=True)
            ),
            {"quest_ids": modified_quest_ids},
        )
        conn.execute(
            text("DELETE FROM questrequirement WHERE quest_id IN :quest_ids").bindparams(
                bindparam("quest_ids", expanding=True)
            ),
            {"quest_ids": modified_quest_ids},
        )

        # Reset quest columns only for modified quests
        conn.execute(
            text(
                """
            UPDATE quest
            SET quest_type = NULL, quest_category = NULL, previous_quest_id = NULL, next_quest_id = NULL
            WHERE id IN :quest_ids
            """
            ).bindparams(bindparam("quest_ids", expanding=True)),
            {"quest_ids": modified_quest_ids},
        )

    # Reset objective columns only for rows that were modified (have objective_type set)
    conn.execute(
        text("""
        UPDATE objective
        SET objective_type = NULL, target_entity = NULL, target_amount = 1
        WHERE objective_type IS NOT NULL
    """)
    )
