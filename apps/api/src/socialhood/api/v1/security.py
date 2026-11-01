"""GitHub secret scanning reports (C-167): POST /v1/security/secret-scanning.

Public and outside any workspace: GitHub's signature on the raw body stands in for a sign-in
(services/secret_scanning.py). Rate limited per IP (``secret_scanning``). A request that isn't
signed by GitHub is 401 with nothing looked up; a signed one gets GitHub's feedback array.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from socialhood.auth.deps import Session
from socialhood.errors import ApiError
from socialhood.security import ratelimit
from socialhood.services import secret_scanning

router = APIRouter(prefix="/v1/security", tags=["security"])


async def _limit(request: Request) -> None:
    await ratelimit.enforce(request, "secret_scanning", ratelimit.client_ip(request))


@router.post(
    "/secret-scanning",
    operation_id="report_leaked_secrets",
    dependencies=[Depends(_limit)],
    response_model=list[secret_scanning.Feedback],
    include_in_schema=True,
)
async def report_leaked_secrets(request: Request, session: Session) -> JSONResponse:
    """GitHub's secret scanning partner alert: a JSON array of ``{token, type, url, source}``,
    signed with ``Github-Public-Key-Identifier`` and ``Github-Public-Key-Signature``. Each
    token that is one of our keys is revoked and its workspace told. 401 when the signature
    doesn't verify."""
    body = await request.body()
    try:
        await secret_scanning.verify(
            request.app.state.http,
            body,
            request.headers.get("github-public-key-identifier"),
            request.headers.get("github-public-key-signature"),
        )
    except secret_scanning.Unverified as refused:
        raise ApiError("unauthorized", "This request isn't signed by GitHub.") from refused
    alerts = secret_scanning.parse(body)
    feedback = await secret_scanning.handle(session, alerts, now=datetime.now(UTC))
    await session.commit()
    return JSONResponse([f.model_dump() for f in feedback])
