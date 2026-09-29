"""Export members' analysis corrections (FR-AI-04) in messages.jsonl's format (TR-AI-10).

    cd apps/api
    uv run python -m tests.ai_eval.export_corrections --workspace <id> --out corrections.jsonl

Each corrected analysis becomes one case: the message, up to 11 earlier messages as context, and
the labels (the member's intent or sentiment where they corrected it, the model's otherwise; the
model's needs_human). Real customer text: anonymise names, numbers and addresses and review the
labels before adding lines to messages.jsonl. Reads DATABASE_URL like the app.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from socialhood.settings import get_settings

CONTEXT = 11

CORRECTED = text(
    "SELECT a.id, a.conversation_id, a.needs_human, m.text, m.occurred_at,"
    " coalesce(a.corrected_intent, a.intent) AS intent,"
    " coalesce(a.corrected_sentiment, a.sentiment) AS sentiment"
    " FROM message_analyses a JOIN messages m ON m.id = a.message_id"
    " WHERE a.workspace_id = :w AND a.corrected_at >= :since"
    " ORDER BY a.corrected_at"
)
EPOCH = datetime(2000, 1, 1, tzinfo=UTC)
EARLIER = text(
    "SELECT direction, text FROM messages"
    " WHERE conversation_id = :c AND direction <> 'system' AND occurred_at < :at"
    " ORDER BY occurred_at DESC LIMIT :n"
)


async def export(workspace_id: uuid.UUID, since: datetime | None) -> list[str]:
    """One JSON line per corrected analysis of the workspace, oldest correction first."""
    engine = create_async_engine(get_settings().database_url)
    lines: list[str] = []
    try:
        async with engine.connect() as conn:
            params = {"w": workspace_id, "since": since or EPOCH}
            for row in (await conn.execute(CORRECTED, params)).all():
                earlier = (
                    await conn.execute(
                        EARLIER, {"c": row.conversation_id, "at": row.occurred_at, "n": CONTEXT}
                    )
                ).all()
                case = {
                    "id": f"corr-{row.id}",
                    "source": "correction",
                    "needs_review": True,
                    "context": [
                        {
                            "from": "customer" if e.direction == "inbound" else "business",
                            "text": e.text or "",
                        }
                        for e in reversed(earlier)
                    ],
                    "text": row.text or "",
                    "labels": {
                        "intent": row.intent,
                        "sentiment": row.sentiment,
                        "needs_human": row.needs_human,
                    },
                }
                lines.append(json.dumps(case, ensure_ascii=False))
    finally:
        await engine.dispose()
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", type=uuid.UUID, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--since", type=datetime.fromisoformat, default=None)
    args = parser.parse_args(argv)
    lines = asyncio.run(export(args.workspace, args.since))
    args.out.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    print(f"{len(lines)} corrections written to {args.out}; anonymise them before adding them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
