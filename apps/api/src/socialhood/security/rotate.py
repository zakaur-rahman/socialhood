"""Re-encrypt every stored platform token with the newest key (SEC-03).

Usage:
    uv run python -m socialhood.security.rotate            # rotate all tokens
    uv run python -m socialhood.security.rotate --new-key  # print a fresh key to put first

Put the new key first in TOKEN_ENCRYPTION_KEYS, keep the old ones after it, deploy, run this,
then remove the old keys. This maintenance command deliberately spans every workspace, so it
works on raw rows rather than tenant-scoped models.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from socialhood.security.crypto import TokenCipher, new_key
from socialhood.settings import get_settings

# Every encrypted column (SEC-03: they all end in _enc).
ENCRYPTED_COLUMNS = (("social_accounts", "access_token_enc"),)


async def rotate_all(database_url: str, cipher: TokenCipher) -> int:
    engine = create_async_engine(database_url)
    rotated = 0
    try:
        async with engine.begin() as conn:
            for table, column in ENCRYPTED_COLUMNS:
                rows = await conn.execute(
                    text(f"SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL FOR UPDATE")  # noqa: S608
                )
                for row_id, blob in rows.all():
                    await conn.execute(
                        text(f"UPDATE {table} SET {column} = :blob WHERE id = :id"),  # noqa: S608
                        {"blob": cipher.rotate(blob), "id": row_id},
                    )
                    rotated += 1
    finally:
        await engine.dispose()
    return rotated


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--new-key", action="store_true", help="print a new Fernet key and exit")
    args = parser.parse_args()
    if args.new_key:
        print(new_key())
        return
    settings = get_settings()
    count = asyncio.run(
        rotate_all(settings.database_url, TokenCipher(settings.token_encryption_keys))
    )
    print(f"Re-encrypted {count} token(s) with the newest key.", file=sys.stderr)


if __name__ == "__main__":
    main()
