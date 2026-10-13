"""Reward-domain services: item/dweller grants, resource grants, lunchboxes, settlement.

The public surface (``RewardService`` + ``reward_service`` singleton) lives in
``app.services.reward_service``; this package holds the role-named collaborators it
orchestrates: ``items`` (catalog-backed item builds plus dweller/template grants),
``resources`` (caps, vault resources, experience, and medication grants),
``lunchbox`` (mint, roll, and open), and ``settlement`` (quest/objective reward
processing and parsing).
"""
