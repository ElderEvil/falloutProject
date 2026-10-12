"""Vault-domain services: initialization, resources, and reads.

The public surface (``VaultService`` + ``vault_service`` singleton) lives in
``app.services.vault_service``; this package holds the role-named collaborators
it orchestrates: ``seeding`` (vault initialization), ``economy`` (resource and
capacity management), and ``reads`` (vault-with-counts assembly).
"""
