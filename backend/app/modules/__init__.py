"""Domain modules — each one owns its ORM models, schemas, service and router.

The package itself does not aggregate them; `app.main` does that explicitly,
which keeps module load-order simple and avoids circular imports.
"""
