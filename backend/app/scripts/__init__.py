"""One-off maintenance jobs, run by hand via `python -m app.scripts.<name>`.

Not imported by the application. Kept under `app/` rather than a top-level
`scripts/` directory so they are inside the container image and share the app's
models and settings.
"""
