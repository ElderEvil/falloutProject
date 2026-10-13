"""Stable objective templates and lower future payouts without clawing back rewards.

NULL reward_snapshot means not earned yet; existing earned/completed links are
backfilled before catalog updates. Empty credited_dweller_ids is correct for
legacy links: individual event identities were never stored. Existing progress
is retained; distinct counting applies to future events. Custom templates and
historical links are preserved. This catalog snapshot is immutable.
"""

import json
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "d4b9f62ce731"
down_revision = "c3a8e51bd620"
branch_labels = None
depends_on = None

_CATALOG = json.loads('''
[
{"challenge":"Collect 2000 Caps","reward":"200 caps","category":"weekly","objective_type":"collect","target_entity":{"resource_type":"caps"},"target_amount":2000,"template_key":"weekly:collect 2000 caps","legacy_challenge":"Collect 2000 Caps"},
{"challenge":"Collect 3000 Caps","reward":"300 caps","category":"weekly","objective_type":"collect","target_entity":{"resource_type":"caps"},"target_amount":3000,"template_key":"weekly:collect 3000 caps","legacy_challenge":"Collect 3000 Caps"},
{"challenge":"Collect 5000 Caps","reward":"500 caps","category":"weekly","objective_type":"collect","target_entity":{"resource_type":"caps"},"target_amount":5000,"template_key":"weekly:collect 5000 caps","legacy_challenge":"Collect 5000 Caps"},
{"challenge":"Produce 1000 Food","reward":"100 caps","category":"weekly","objective_type":"collect","target_entity":{"resource_type":"food","production_only":true},"target_amount":1000,"template_key":"weekly:collect 1000 food","legacy_challenge":"Collect 1000 Food"},
{"challenge":"Produce 2000 Food","reward":"200 caps","category":"weekly","objective_type":"collect","target_entity":{"resource_type":"food","production_only":true},"target_amount":2000,"template_key":"weekly:collect 2000 food","legacy_challenge":"Collect 2000 Food"},
{"challenge":"Produce 1000 Water","reward":"100 caps","category":"weekly","objective_type":"collect","target_entity":{"resource_type":"water","production_only":true},"target_amount":1000,"template_key":"weekly:collect 1000 water","legacy_challenge":"Collect 1000 Water"},
{"challenge":"Produce 2000 Water","reward":"200 caps","category":"weekly","objective_type":"collect","target_entity":{"resource_type":"water","production_only":true},"target_amount":2000,"template_key":"weekly:collect 2000 water","legacy_challenge":"Collect 2000 Water"},
{"challenge":"Produce 1000 Power","reward":"100 caps","category":"weekly","objective_type":"collect","target_entity":{"resource_type":"power","production_only":true},"target_amount":1000,"template_key":"weekly:collect 1000 power","legacy_challenge":"Collect 1000 Power"},
{"challenge":"Produce 2000 Power","reward":"200 caps","category":"weekly","objective_type":"collect","target_entity":{"resource_type":"power","production_only":true},"target_amount":2000,"template_key":"weekly:collect 2000 power","legacy_challenge":"Collect 2000 Power"},
{"challenge":"Build 5 Rooms","reward":"125 caps","category":"weekly","objective_type":"build","target_entity":{"room_type":"*"},"target_amount":5,"template_key":"weekly:build 5 rooms","legacy_challenge":"Build 5 Rooms"},
{"challenge":"Build 7 Rooms","reward":"175 caps","category":"weekly","objective_type":"build","target_entity":{"room_type":"*"},"target_amount":7,"template_key":"weekly:build 7 rooms","legacy_challenge":"Build 7 Rooms"},
{"challenge":"Build 10 Rooms","reward":"250 caps","category":"weekly","objective_type":"build","target_entity":{"room_type":"*"},"target_amount":10,"template_key":"weekly:build 10 rooms","legacy_challenge":"Build 10 Rooms"},
{"challenge":"Assign 5 Dwellers","reward":"100 caps","category":"weekly","objective_type":"assign","target_entity":{"distinct_dwellers":true},"target_amount":5,"template_key":"weekly:assign 5 dwellers","legacy_challenge":"Assign 5 Dwellers"},
{"challenge":"Assign 8 Dwellers","reward":"160 caps","category":"weekly","objective_type":"assign","target_entity":{"distinct_dwellers":true},"target_amount":8,"template_key":"weekly:assign 8 dwellers","legacy_challenge":"Assign 8 Dwellers"},
{"challenge":"Assign 10 Dwellers","reward":"200 caps","category":"weekly","objective_type":"assign","target_entity":{"distinct_dwellers":true},"target_amount":10,"template_key":"weekly:assign 10 dwellers","legacy_challenge":"Assign 10 Dwellers"},
{"challenge":"Correctly Assign 5 Dwellers","reward":"125 caps","category":"weekly","objective_type":"assign_correct","target_entity":{"distinct_dwellers":true},"target_amount":5,"template_key":"weekly:correctly assign 5 dwellers","legacy_challenge":"Correctly Assign 5 Dwellers"},
{"challenge":"Correctly Assign 8 Dwellers","reward":"200 caps","category":"weekly","objective_type":"assign_correct","target_entity":{"distinct_dwellers":true},"target_amount":8,"template_key":"weekly:correctly assign 8 dwellers","legacy_challenge":"Correctly Assign 8 Dwellers"},
{"challenge":"Train 3 Dwellers","reward":"150 caps","category":"weekly","objective_type":"train","target_entity":{"distinct_dwellers":true},"target_amount":3,"template_key":"weekly:train 3 dwellers","legacy_challenge":"Train 3 Dwellers"},
{"challenge":"Train 5 Dwellers","reward":"250 caps","category":"weekly","objective_type":"train","target_entity":{"distinct_dwellers":true},"target_amount":5,"template_key":"weekly:train 5 dwellers","legacy_challenge":"Train 5 Dwellers"},
{"challenge":"Level up 2 Dwellers to Lv.5","reward":"150 caps","category":"weekly","objective_type":"level_up","target_entity":{"min_level":5,"distinct_dwellers":true},"target_amount":2,"template_key":"weekly:level up 2 dwellers to lv.5","legacy_challenge":"Level up 2 Dwellers to Lv.5"},
{"challenge":"Level up 3 Dwellers to Lv.5","reward":"225 caps","category":"weekly","objective_type":"level_up","target_entity":{"min_level":5,"distinct_dwellers":true},"target_amount":3,"template_key":"weekly:level up 3 dwellers to lv.5","legacy_challenge":"Level up 3 Dwellers to Lv.5"},
{"challenge":"Level up 2 Dwellers to Lv.10","reward":"150 caps","category":"weekly","objective_type":"level_up","target_entity":{"min_level":10,"distinct_dwellers":true},"target_amount":2,"template_key":"weekly:level up 2 dwellers to lv.10","legacy_challenge":"Level up 2 Dwellers to Lv.10"},
{"challenge":"Reach 30 Dwellers","reward":"300 caps","category":"weekly","objective_type":"reach","target_entity":{"reach_type":"dweller_count"},"target_amount":30,"template_key":"weekly:reach 30 dwellers","legacy_challenge":"Reach 30 Dwellers"},
{"challenge":"Complete 2 Quests","reward":"200 caps","category":"weekly","objective_type":"expedition","target_entity":{},"target_amount":2,"template_key":"weekly:complete 2 expeditions","legacy_challenge":"Complete 2 Expeditions"},
{"challenge":"Complete 3 Quests","reward":"300 caps","category":"weekly","objective_type":"expedition","target_entity":{},"target_amount":3,"template_key":"weekly:complete 3 expeditions","legacy_challenge":"Complete 3 Expeditions"},
{"challenge":"Complete 1 Main Quest","reward":"150 caps","category":"weekly","objective_type":"expedition","target_entity":{"quest_type":"main"},"target_amount":1,"template_key":"weekly:complete 1 main quest","legacy_challenge":"Complete 1 Main Quest"},
{"challenge":"Assign dwellers to Power","reward":"25 caps","category":"starter","objective_type":"assign","target_entity":{"room_type":"power_generator"},"target_amount":3,"sequence":0,"description":"Open the Power Generator and assign dwellers.","template_key":"starter:assign dwellers to power","legacy_challenge":"Assign dwellers to Power"},
{"challenge":"Produce 150 Power","reward":"50 power","category":"starter","objective_type":"collect","target_entity":{"resource_type":"power","production_only":true},"target_amount":150,"sequence":1,"description":"Staff a Power Generator with Strength workers. Gross output counts even when storage is full.","template_key":"starter:collect 150 power","legacy_challenge":"Collect 150 Power"},
{"challenge":"Build a Living Quarters","reward":"50 caps","category":"starter","objective_type":"build","target_entity":{"room_type":"living_room"},"target_amount":1,"sequence":2,"description":"More living space lets the vault grow.","template_key":"starter:build a living quarters","legacy_challenge":"Build a Living Quarters"},
{"challenge":"Assign a dweller correctly","reward":"50 caps","category":"starter","objective_type":"assign_correct","target_entity":{},"target_amount":1,"sequence":3,"description":"Match a dweller's best SPECIAL to the room.","template_key":"starter:assign a dweller correctly","legacy_challenge":"Assign a dweller correctly"},
{"challenge":"Scavenge caps in the wasteland","reward":"100 caps","category":"starter","objective_type":"collect","target_entity":{"resource_type":"caps"},"target_amount":300,"sequence":4,"description":"Send a healthy dweller to explore \u2014 they return with caps and loot.","template_key":"starter:scavenge caps in the wasteland","legacy_challenge":"Scavenge caps in the wasteland"},
{"challenge":"Reach 10 Dwellers","reward":"100 caps","category":"starter","objective_type":"reach","target_entity":{"reach_type":"dweller_count"},"target_amount":10,"sequence":5,"description":"Grow population via the radio or breeding.","template_key":"starter:reach 10 dwellers","legacy_challenge":"Reach 10 Dwellers"},
{"challenge":"Reach 18 Dwellers","reward":"150 caps","category":"starter","objective_type":"reach","target_entity":{"reach_type":"dweller_count"},"target_amount":18,"sequence":6,"description":"The Overseer's Office needs 18 dwellers.","template_key":"starter:reach 18 dwellers","legacy_challenge":"Reach 18 Dwellers"},
{"challenge":"Build Overseer's Office","reward":"200 caps","category":"starter","objective_type":"build","target_entity":{"room_type":"overseers_office"},"target_amount":1,"sequence":7,"description":"Costs 1000 caps \u2014 keep exploring and selling loot.","template_key":"starter:build overseer's office","legacy_challenge":"Build Overseer's Office"},
{"challenge":"Reverse-engineer a schematic","reward":"300 caps","category":"starter","objective_type":"scrap","target_entity":{"item_type":"weapon","rarity":"rare"},"target_amount":1,"sequence":8,"description":"Find a rare weapon in the wasteland and scrap it to learn its schematic.","template_key":"starter:reverse-engineer a schematic","legacy_challenge":"Reverse-engineer a schematic"},
{"challenge":"Train a SPECIAL stat","reward":"200 caps","category":"starter","objective_type":"train","target_entity":{},"target_amount":1,"sequence":9,"description":"Build a training room and train one stat. Choose a stat that improves a dweller's next job or quest role.","template_key":"starter:train a special stat","legacy_challenge":"Train a SPECIAL stat"},
{"challenge":"Complete 3 quest missions","reward":"1 lunchbox","category":"starter","objective_type":"expedition","target_entity":{},"target_amount":3,"sequence":10,"description":"Use the Overseer's Office to choose missions, prepare a party and claim the rewards after each return.","template_key":"starter:complete 3 quest missions","legacy_challenge":"Complete 3 quest missions"},
{"challenge":"Develop a level 20 dweller","reward":"750 caps","category":"starter","objective_type":"reach","target_entity":{"reach_type":"level"},"target_amount":20,"sequence":11,"description":"Develop a veteran through work, quests or exploration. Review newly available missions and their equipment requirements.","template_key":"starter:develop a level 20 dweller","legacy_challenge":"Develop a level 20 dweller"},
{"challenge":"Grow a 50-dweller vault","reward":"1 lunchbox","category":"starter","objective_type":"reach","target_entity":{"reach_type":"dweller_count"},"target_amount":50,"sequence":12,"description":"Expand living space and recruit or raise dwellers. Keep production and medical capacity ahead of population growth.","template_key":"starter:grow a 50-dweller vault","legacy_challenge":"Grow a 50-dweller vault"},
{"challenge":"Collect 200 Caps","reward":"20 caps","category":"daily","objective_type":"collect","target_entity":{"resource_type":"caps"},"target_amount":200,"template_key":"daily:collect 200 caps","legacy_challenge":"Collect 200 Caps"},
{"challenge":"Collect 300 Caps","reward":"30 caps","category":"daily","objective_type":"collect","target_entity":{"resource_type":"caps"},"target_amount":300,"template_key":"daily:collect 300 caps","legacy_challenge":"Collect 300 Caps"},
{"challenge":"Collect 500 Caps","reward":"50 caps","category":"daily","objective_type":"collect","target_entity":{"resource_type":"caps"},"target_amount":500,"template_key":"daily:collect 500 caps","legacy_challenge":"Collect 500 Caps"},
{"challenge":"Produce 150 Food","reward":"15 caps","category":"daily","objective_type":"collect","target_entity":{"resource_type":"food","production_only":true},"target_amount":150,"template_key":"daily:collect 150 food","legacy_challenge":"Collect 150 Food"},
{"challenge":"Produce 250 Food","reward":"25 caps","category":"daily","objective_type":"collect","target_entity":{"resource_type":"food","production_only":true},"target_amount":250,"template_key":"daily:collect 250 food","legacy_challenge":"Collect 250 Food"},
{"challenge":"Produce 150 Water","reward":"15 caps","category":"daily","objective_type":"collect","target_entity":{"resource_type":"water","production_only":true},"target_amount":150,"template_key":"daily:collect 150 water","legacy_challenge":"Collect 150 Water"},
{"challenge":"Produce 250 Water","reward":"25 caps","category":"daily","objective_type":"collect","target_entity":{"resource_type":"water","production_only":true},"target_amount":250,"template_key":"daily:collect 250 water","legacy_challenge":"Collect 250 Water"},
{"challenge":"Produce 150 Power","reward":"15 caps","category":"daily","objective_type":"collect","target_entity":{"resource_type":"power","production_only":true},"target_amount":150,"template_key":"daily:collect 150 power","legacy_challenge":"Collect 150 Power"},
{"challenge":"Produce 250 Power","reward":"25 caps","category":"daily","objective_type":"collect","target_entity":{"resource_type":"power","production_only":true},"target_amount":250,"template_key":"daily:collect 250 power","legacy_challenge":"Collect 250 Power"},
{"challenge":"Collect 3 Weapons","reward":"weapon:Pipe Pistol","category":"daily","objective_type":"collect","target_entity":{"item_type":"weapon"},"target_amount":3,"template_key":"daily:collect 3 weapons","legacy_challenge":"Collect 3 Weapons"},
{"challenge":"Collect 3 Outfits","reward":"outfit:Mechanic jumpsuit","category":"daily","objective_type":"collect","target_entity":{"item_type":"outfit"},"target_amount":3,"template_key":"daily:collect 3 outfits","legacy_challenge":"Collect 3 Outfits"},
{"challenge":"Build 2 Rooms","reward":"50 caps","category":"daily","objective_type":"build","target_entity":{"room_type":"*"},"target_amount":2,"template_key":"daily:build 2 rooms","legacy_challenge":"Build 2 Rooms"},
{"challenge":"Build 3 Rooms","reward":"75 caps","category":"daily","objective_type":"build","target_entity":{"room_type":"*"},"target_amount":3,"template_key":"daily:build 3 rooms","legacy_challenge":"Build 3 Rooms"},
{"challenge":"Assign 2 Dwellers","reward":"40 caps","category":"daily","objective_type":"assign","target_entity":{"distinct_dwellers":true},"target_amount":2,"template_key":"daily:assign 2 dwellers","legacy_challenge":"Assign 2 Dwellers"},
{"challenge":"Assign 3 Dwellers","reward":"60 caps","category":"daily","objective_type":"assign","target_entity":{"distinct_dwellers":true},"target_amount":3,"template_key":"daily:assign 3 dwellers","legacy_challenge":"Assign 3 Dwellers"},
{"challenge":"Assign 4 Dwellers","reward":"80 caps","category":"daily","objective_type":"assign","target_entity":{"distinct_dwellers":true},"target_amount":4,"template_key":"daily:assign 4 dwellers","legacy_challenge":"Assign 4 Dwellers"},
{"challenge":"Correctly Assign 2 Dwellers","reward":"50 caps","category":"daily","objective_type":"assign_correct","target_entity":{"distinct_dwellers":true},"target_amount":2,"template_key":"daily:correctly assign 2 dwellers","legacy_challenge":"Correctly Assign 2 Dwellers"},
{"challenge":"Correctly Assign 3 Dwellers","reward":"75 caps","category":"daily","objective_type":"assign_correct","target_entity":{"distinct_dwellers":true},"target_amount":3,"template_key":"daily:correctly assign 3 dwellers","legacy_challenge":"Correctly Assign 3 Dwellers"},
{"challenge":"Train 1 Dweller","reward":"50 caps","category":"daily","objective_type":"train","target_entity":{"distinct_dwellers":true},"target_amount":1,"template_key":"daily:train 1 dweller","legacy_challenge":"Train 1 Dweller"},
{"challenge":"Train 2 Dwellers","reward":"100 caps","category":"daily","objective_type":"train","target_entity":{"distinct_dwellers":true},"target_amount":2,"template_key":"daily:train 2 dwellers","legacy_challenge":"Train 2 Dwellers"},
{"challenge":"Scrap a Rare Weapon","reward":"38 caps","category":"daily","objective_type":"scrap","target_entity":{"item_type":"weapon","rarity":"rare"},"target_amount":1,"template_key":"daily:scrap a rare weapon","legacy_challenge":"Scrap a Rare Weapon"},
{"challenge":"Scrap a Rare Outfit","reward":"38 caps","category":"daily","objective_type":"scrap","target_entity":{"item_type":"outfit","rarity":"rare"},"target_amount":1,"template_key":"daily:scrap a rare outfit","legacy_challenge":"Scrap a Rare Outfit"},
{"challenge":"Reach 10 Dwellers","reward":"500 caps","category":"achievement","objective_type":"reach","target_entity":{"reach_type":"dweller_count"},"target_amount":10,"template_key":"achievement:reach 10 dwellers","legacy_challenge":"Reach 10 Dwellers"},
{"challenge":"Reach 25 Dwellers","reward":"1250 caps","category":"achievement","objective_type":"reach","target_entity":{"reach_type":"dweller_count"},"target_amount":25,"template_key":"achievement:reach 25 dwellers","legacy_challenge":"Reach 25 Dwellers"},
{"challenge":"Reach 50 Dwellers","reward":"2500 caps","category":"achievement","objective_type":"reach","target_entity":{"reach_type":"dweller_count"},"target_amount":50,"template_key":"achievement:reach 50 dwellers","legacy_challenge":"Reach 50 Dwellers"},
{"challenge":"Reach 75 Dwellers","reward":"3750 caps","category":"achievement","objective_type":"reach","target_entity":{"reach_type":"dweller_count"},"target_amount":75,"template_key":"achievement:reach 75 dwellers","legacy_challenge":"Reach 75 Dwellers"},
{"challenge":"Reach 100 Dwellers","reward":"5000 caps","category":"achievement","objective_type":"reach","target_entity":{"reach_type":"dweller_count"},"target_amount":100,"template_key":"achievement:reach 100 dwellers","legacy_challenge":"Reach 100 Dwellers"},
{"challenge":"Build 25 Rooms Total","reward":"1000 caps","category":"achievement","objective_type":"build","target_entity":{"room_type":"*"},"target_amount":25,"template_key":"achievement:build 25 rooms total","legacy_challenge":"Build 25 Rooms Total"},
{"challenge":"Build 50 Rooms Total","reward":"2000 caps","category":"achievement","objective_type":"build","target_entity":{"room_type":"*"},"target_amount":50,"template_key":"achievement:build 50 rooms total","legacy_challenge":"Build 50 Rooms Total"},
{"challenge":"Build a Living Quarter","reward":"40 caps","category":"achievement","objective_type":"build","target_entity":{"room_type":"living_room"},"target_amount":1,"template_key":"achievement:build a living quarter","legacy_challenge":"Build a Living Quarter"},
{"challenge":"Collect 10000 Caps Total","reward":"1000 caps","category":"achievement","objective_type":"collect","target_entity":{"resource_type":"caps"},"target_amount":10000,"template_key":"achievement:collect 10000 caps total","legacy_challenge":"Collect 10000 Caps Total"},
{"challenge":"Produce 500 Power","reward":"50 caps","category":"achievement","objective_type":"collect","target_entity":{"resource_type":"power","production_only":true},"target_amount":500,"template_key":"achievement:collect 500 power","legacy_challenge":"Collect 500 Power"},
{"challenge":"Produce 500 Food","reward":"50 caps","category":"achievement","objective_type":"collect","target_entity":{"resource_type":"food","production_only":true},"target_amount":500,"template_key":"achievement:collect 500 food","legacy_challenge":"Collect 500 Food"},
{"challenge":"Produce 500 Water","reward":"50 caps","category":"achievement","objective_type":"collect","target_entity":{"resource_type":"water","production_only":true},"target_amount":500,"template_key":"achievement:collect 500 water","legacy_challenge":"Collect 500 Water"},
{"challenge":"Collect 5 Stimpaks","reward":"125 caps","category":"achievement","objective_type":"collect","target_entity":{"item_type":"stimpak"},"target_amount":5,"template_key":"achievement:collect 5 stimpaks","legacy_challenge":"Collect 5 Stimpaks"},
{"challenge":"Collect 7 Pieces of Junk","reward":"300 caps","category":"achievement","objective_type":"collect","target_entity":{"item_type":"junk"},"target_amount":7,"template_key":"achievement:collect 7 pieces of junk","legacy_challenge":"Collect 7 Pieces of Junk"},
{"challenge":"Assign 20 Dwellers Total","reward":"1250 caps","category":"achievement","objective_type":"assign","target_entity":{"distinct_dwellers":true},"target_amount":20,"template_key":"achievement:assign 20 dwellers total","legacy_challenge":"Assign 20 Dwellers Total"},
{"challenge":"Assign 50 Dwellers Total","reward":"2500 caps","category":"achievement","objective_type":"assign","target_entity":{"distinct_dwellers":true},"target_amount":50,"template_key":"achievement:assign 50 dwellers total","legacy_challenge":"Assign 50 Dwellers Total"},
{"challenge":"Correctly Assign 10 Total","reward":"1 lunchbox","category":"achievement","objective_type":"assign_correct","target_entity":{"distinct_dwellers":true},"target_amount":10,"template_key":"achievement:correctly assign 10 total","legacy_challenge":"Correctly Assign 10 Total"},
{"challenge":"Correctly Assign 20 Total","reward":"1500 caps","category":"achievement","objective_type":"assign_correct","target_entity":{"distinct_dwellers":true},"target_amount":20,"template_key":"achievement:correctly assign 20 total","legacy_challenge":"Correctly Assign 20 Total"},
{"challenge":"Correctly Assign 50 Total","reward":"3750 caps","category":"achievement","objective_type":"assign_correct","target_entity":{"distinct_dwellers":true},"target_amount":50,"template_key":"achievement:correctly assign 50 total","legacy_challenge":"Correctly Assign 50 Total"},
{"challenge":"Train a Dweller","reward":"400 caps","category":"achievement","objective_type":"train","target_entity":{"distinct_dwellers":true},"target_amount":1,"template_key":"achievement:train a dweller","legacy_challenge":"Train a Dweller"},
{"challenge":"Train Dweller to 10 Strength","reward":"1000 caps","category":"achievement","objective_type":"train","target_entity":{"stat":"strength","target_value":10,"distinct_dwellers":true},"target_amount":1,"template_key":"achievement:train dweller to 10 strength","legacy_challenge":"Train Dweller to 10 Strength"},
{"challenge":"Train Dweller to 10 Perception","reward":"1000 caps","category":"achievement","objective_type":"train","target_entity":{"stat":"perception","target_value":10,"distinct_dwellers":true},"target_amount":1,"template_key":"achievement:train dweller to 10 perception","legacy_challenge":"Train Dweller to 10 Perception"},
{"challenge":"Train Dweller to 10 Endurance","reward":"1000 caps","category":"achievement","objective_type":"train","target_entity":{"stat":"endurance","target_value":10,"distinct_dwellers":true},"target_amount":1,"template_key":"achievement:train dweller to 10 endurance","legacy_challenge":"Train Dweller to 10 Endurance"},
{"challenge":"Train Dweller to 10 Charisma","reward":"1000 caps","category":"achievement","objective_type":"train","target_entity":{"stat":"charisma","target_value":10,"distinct_dwellers":true},"target_amount":1,"template_key":"achievement:train dweller to 10 charisma","legacy_challenge":"Train Dweller to 10 Charisma"},
{"challenge":"Train Dweller to 10 Intelligence","reward":"1000 caps","category":"achievement","objective_type":"train","target_entity":{"stat":"intelligence","target_value":10,"distinct_dwellers":true},"target_amount":1,"template_key":"achievement:train dweller to 10 intelligence","legacy_challenge":"Train Dweller to 10 Intelligence"},
{"challenge":"Train Dweller to 10 Agility","reward":"1000 caps","category":"achievement","objective_type":"train","target_entity":{"stat":"agility","target_value":10,"distinct_dwellers":true},"target_amount":1,"template_key":"achievement:train dweller to 10 agility","legacy_challenge":"Train Dweller to 10 Agility"},
{"challenge":"Train Dweller to 10 Luck","reward":"1000 caps","category":"achievement","objective_type":"train","target_entity":{"stat":"luck","target_value":10,"distinct_dwellers":true},"target_amount":1,"template_key":"achievement:train dweller to 10 luck","legacy_challenge":"Train Dweller to 10 Luck"},
{"challenge":"Complete 10 Quests Total","reward":"750 caps","category":"achievement","objective_type":"expedition","target_entity":{},"target_amount":10,"template_key":"achievement:complete 10 expeditions total","legacy_challenge":"Complete 10 Expeditions Total"},
{"challenge":"Complete 25 Quests Total","reward":"1500 caps","category":"achievement","objective_type":"expedition","target_entity":{},"target_amount":25,"template_key":"achievement:complete 25 expeditions total","legacy_challenge":"Complete 25 Expeditions Total"},
{"challenge":"Complete 50 Quests Total","reward":"3000 caps","category":"achievement","objective_type":"expedition","target_entity":{},"target_amount":50,"template_key":"achievement:complete 50 expeditions total","legacy_challenge":"Complete 50 Expeditions Total"},
{"challenge":"Complete 5 Main Quests","reward":"2500 caps","category":"achievement","objective_type":"expedition","target_entity":{"quest_type":"main"},"target_amount":5,"template_key":"achievement:complete 5 main quests","legacy_challenge":"Complete 5 Main Quests"},
{"challenge":"Level Up a Dweller","reward":"250 caps","category":"achievement","objective_type":"level_up","target_entity":{"min_level":2,"distinct_dwellers":true},"target_amount":1,"template_key":"achievement:level up a dweller","legacy_challenge":"Level Up a Dweller"},
{"challenge":"Reverse-engineer a Legendary","reward":"1000 caps","category":"achievement","objective_type":"scrap","target_entity":{"rarity":"legendary"},"target_amount":1,"template_key":"achievement:reverse-engineer a legendary","legacy_challenge":"Reverse-engineer a Legendary"},
{"challenge":"Scrap 10 Rare Items","reward":"750 caps","category":"achievement","objective_type":"scrap","target_entity":{"rarity":"rare"},"target_amount":10,"template_key":"achievement:scrap 10 rare items","legacy_challenge":"Scrap 10 Rare Items"}
]
''')


def upgrade() -> None:
    connection = op.get_bind()
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")
    op.add_column("objective", sa.Column("template_key", sa.String(160), nullable=True))
    op.create_index("ix_objective_template_key", "objective", ["template_key"], unique=True)
    op.add_column("vaultobjectiveprogresslink", sa.Column("credited_dweller_ids", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("vaultobjectiveprogresslink", sa.Column("reward_snapshot", sa.String(32), nullable=True))
    objective = sa.table("objective", sa.column("id", sa.Uuid()), sa.column("challenge", sa.String()),
                         sa.column("reward", sa.String()), sa.column("category", sa.String()),
                         sa.column("objective_type", sa.String()), sa.column("target_entity", json_type),
                         sa.column("target_amount", sa.Integer()), sa.column("sequence", sa.Integer()),
                         sa.column("description", sa.String()), sa.column("template_key", sa.String()))
    link = sa.table("vaultobjectiveprogresslink", sa.column("objective_id", sa.Uuid()),
                    sa.column("progress", sa.Integer()), sa.column("total", sa.Integer()),
                    sa.column("is_completed", sa.Boolean()), sa.column("reward_snapshot", sa.String()))
    connection.execute(link.update().where(sa.or_(link.c.progress >= link.c.total, link.c.is_completed.is_(True)))
                       .values(reward_snapshot=sa.select(objective.c.reward)
                               .where(objective.c.id == link.c.objective_id).scalar_subquery()))
    for row in _CATALOG:
        values = dict(row)
        legacy_challenge = values.pop("legacy_challenge")
        identifier = connection.execute(sa.select(objective.c.id).where(
            objective.c.category == values["category"],
            sa.func.lower(sa.func.trim(objective.c.challenge)) == legacy_challenge.strip().lower()
        ).order_by(objective.c.id)).scalars().first()
        if identifier is None:
            connection.execute(objective.insert().values(id=uuid4(), **values))
        else:
            connection.execute(objective.update().where(objective.c.id == identifier).values(**values))


def downgrade() -> None:
    # Keep earned snapshots, template identities and reduced payouts. Restoring
    # a farming exploit or removing claim history is not a safe data downgrade.
    pass
