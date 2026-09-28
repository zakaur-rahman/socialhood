"""Write the API's OpenAPI document (TR-API-08). Used by ``pnpm gen:api`` and the CI drift check.

Usage: python -m socialhood.openapi OUTPUT_PATH. The file is written directly (not via stdout,
where logs also go). The app is built with placeholder connection settings, so no database or
Valkey is needed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
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
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m socialhood.openapi OUTPUT_PATH")
    document = json.dumps(openapi_document(), indent=2, sort_keys=True) + "\n"
    Path(sys.argv[1]).write_text(document, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
