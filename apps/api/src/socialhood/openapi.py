"""Print the API's OpenAPI document (TR-API-08). Used by ``pnpm gen:api`` and the CI drift check.

The app is built with placeholder connection settings, so no database or Valkey is needed.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from socialhood.main import create_app
from socialhood.settings import AppEnv, Settings


def openapi_document() -> dict[str, Any]:
    settings = Settings(
        _env_file=None,
        app_env=AppEnv.LOCAL,
        database_url="postgresql+asyncpg://openapi:openapi@localhost/openapi",
        database_url_direct="postgresql://openapi:openapi@localhost/openapi",
        redis_url="redis://localhost:6379/0",
    )
    return create_app(settings).openapi()


def main() -> None:
    sys.stdout.write(json.dumps(openapi_document(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
