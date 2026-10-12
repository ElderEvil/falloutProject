"""Map-domain services: bio registration, discovery, and map reads.

The public surface (``MapService`` + ``map_service`` singleton) lives in
``app.services.map_service``; this package holds the role-named collaborators it
orchestrates: ``bio_registration`` (bio places, the home marker, and failure
notification), ``discovery`` (journey discoveries, routes, and the reclear
sweep), and ``reads`` (location detail and full map assembly).
"""
