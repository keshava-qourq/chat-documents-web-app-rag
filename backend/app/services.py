"""The backing services this application is configured to reach.

Each entry maps a service to the environment variable that addresses it. The
MinIO value comes from docker-compose.yml through .env.example; GEMINI_API_KEY
is set by the product owner before deployment, not by the scaffold, so this
reports `false` until then rather than failing anything. Either way, the
health check reports what the running deployment can actually reach -- it
never calls Gemini itself.
"""

import os

SERVICES = {
    "minio": "MINIO_ENDPOINT",
    "gemini": "GEMINI_API_KEY",
}


def configured_services() -> dict[str, bool]:
    """Each service mapped to whether its connection variable is set."""
    return {name: bool(os.getenv(var)) for name, var in SERVICES.items()}
