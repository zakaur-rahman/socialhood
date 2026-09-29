"""T5.3: knowledge sources, ingestion, retrieval and the test box (TR-AI-08, SEC-09, FR-KB-01…04,
F-14). Done when: a URL to 169.254.169.254 is rejected; an edit is searchable within 60 s (it is
queued at once and ingested by that job).

Ingestion runs by calling the job's service directly; embeddings come from the fake provider (a
hashed bag of words, so shared words mean similarity); web pages and file downloads are respx
mocks and DNS is a table, so nothing leaves the machine.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from socialhood.ai.fake import FakeCall, FakeProvider
from socialhood.ai.metering import quota
from socialhood.ai.provider import AIError, EmbedKind
from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.security import ssrf
from socialhood.services.knowledge import ingest
from socialhood.services.knowledge.retrieval import retrieve
from tests.support.ai import make_source
from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.inbox import make_asset
from tests.support.ingest import jobs, rows
from tests.support.knowledge import HOSTS, PUBLIC_IP, fake_dns, make_docx, make_pdf

SHIPPING_PAGE = b"""<html><head><title>Shipping | Maple Bakery</title></head><body>
<nav>Home Shop Contact</nav>
<article><h1>Shipping policy</h1>
<p>We ship across India in 3-5 days. Orders over Rs 999 ship free of charge.</p>
<p>Every cake is packed in a cool box, and we send a tracking link by SMS once your parcel leaves
our kitchen in Pune. Deliveries arrive between 10 am and 7 pm, Monday to Saturday.</p>
<h2>International</h2>
<p>We ship to the UAE and Singapore. Delivery takes 7-10 days and costs Rs 1,500.</p>
<p>International orders ship dry cakes and cookies only, because fresh cream cannot travel that
far. Customs duties, if any, are paid by the customer on delivery.</p>
</article><footer>Copyright Maple Bakery</footer></body></html>"""
HTML = {"content-type": "text/html; charset=utf-8"}


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk, queue: None) -> Ws:
    return await workspace(client, clerk)


@pytest.fixture
def maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return make_sessionmaker(engine)


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def dns(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Web-page fetches resolve through this table (a test may add hosts)."""
    table = dict(HOSTS)
    monkeypatch.setattr(ssrf, "resolve_host", fake_dns(table))
    return table


async def run_ingest(
    maker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
    ws: Ws,
    source: dict[str, Any],
    *,
    will_retry: bool = False,
) -> str:
    return await ingest.ingest_source(
        maker,
        http,
        workspace_id=uuid.UUID(ws.wid),
        source_id=uuid.UUID(source["id"]),
        version=source["version"],
        will_retry=will_retry,
    )


async def chunks(engine: AsyncEngine, source_id: str) -> list[dict[str, Any]]:
    return await rows(
        engine,
        "SELECT id, source_version, ordinal, char_count, content FROM knowledge_chunks"
        " WHERE source_id = :s ORDER BY ordinal",
        s=source_id,
    )


async def search(
    maker: async_sessionmaker[AsyncSession], wid: str, query: str, **kwargs: Any
) -> list[tuple[str, float]]:
    with workspace_scope(uuid.UUID(wid)):
        async with maker() as session:
            hits = await retrieve(session, query, **kwargs)
    return [(hit.source_title, hit.similarity) for hit in hits]


def field_errors(response: httpx.Response) -> list[str]:
    return [e["field"] for e in response.json().get("errors", [])]


# ---------------------------------------------------------------- FAQ and notes


async def test_an_faq_is_queued_ingested_and_found(
    ws: Ws,
    engine: AsyncEngine,
    maker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
    fake_ai: FakeProvider,
) -> None:
    answer = "Yes. We ship to Dubai and the rest of the UAE in 7-10 days for Rs 1,500."
    created = await ws.ok(
        "POST",
        "/knowledge-sources",
        201,
        json={"type": "faq", "question": "Do you ship to Dubai?", "body": answer},
    )

    assert (created["status"], created["version"], created["title"]) == (
        "pending",
        1,
        "Do you ship to Dubai?",
    )
    assert created["char_count"] == len("Do you ship to Dubai?") + len(answer)
    [job] = await jobs("ingest_knowledge_source")
    assert job["queue_name"] == "bulk"
    assert job["queueing_lock"] == f"kb:{created['id']}:1"
    assert job["args"] == {"workspace_id": ws.wid, "source_id": created["id"], "version": 1}
    assert not job["deferred"]  # queued at once: searchable within 60 s (FR-KB-02)

    assert await run_ingest(maker, http, ws, created) == "ready"

    source = await ws.ok("GET", f"/knowledge-sources/{created['id']}")
    assert (source["status"], source["chunk_count"], source["error"]) == ("ready", 1, None)
    assert source["last_ingested_at"] is not None
    [chunk] = await chunks(engine, created["id"])
    assert chunk["content"] == (
        "[Do you ship to Dubai?] Q: Do you ship to Dubai?\n"
        "A: Yes. We ship to Dubai and the rest of the UAE in 7-10 days for Rs 1,500."
    )
    assert fake_ai.embed_calls[-1][1] == "document"
    hits = await search(maker, ws.wid, "Do you ship to Dubai?")
    assert [title for title, _ in hits] == ["Do you ship to Dubai?"]
    assert hits[0][1] >= 0.6
    assert fake_ai.embed_calls[-1] == (["Do you ship to Dubai?"], "query")


async def test_a_note_is_split_into_titled_chunks(
    ws: Ws, engine: AsyncEngine, maker: async_sessionmaker[AsyncSession], http: httpx.AsyncClient
) -> None:
    body = "\n\n".join(
        f"## Zone {n}\n\n" + " ".join(f"Deliveries to zone {n} take {n} days." for _ in range(20))
        for n in range(1, 4)
    )
    created = await ws.ok(
        "POST", "/knowledge-sources", 201, json={"type": "text", "title": "Delivery", "body": body}
    )

    assert await run_ingest(maker, http, ws, created) == "ready"

    stored = await chunks(engine, created["id"])
    assert len(stored) >= 3
    assert [c["ordinal"] for c in stored] == list(range(len(stored)))
    assert all(c["content"].startswith("[Delivery] ") for c in stored)
    assert all(len(c["content"]) <= len("[Delivery] ") + 1200 for c in stored)
    source = await ws.ok("GET", f"/knowledge-sources/{created['id']}")
    assert (source["char_count"], source["chunk_count"]) == (len(body), len(stored))


@pytest.mark.parametrize(
    ("body", "status", "fields"),
    [
        ({"type": "faq", "question": "Do you deliver?"}, 422, ["body"]),
        ({"type": "faq", "body": "Yes"}, 422, ["question"]),
        ({"type": "faq", "question": "Q?", "body": "A", "url": "https://a.example"}, 422, ["url"]),
        ({"type": "text", "body": "Our policy"}, 422, ["title"]),
        (
            {"type": "text", "title": "Policy", "body": "x", "gap_id": str(uuid.uuid4())},
            422,
            ["gap_id"],
        ),
        ({"type": "url"}, 422, ["url"]),
        ({"type": "url", "url": "ftp://maple.example/menu"}, 422, ["url"]),
        ({"type": "url", "url": "http://169.254.169.254/latest/meta-data/"}, 422, ["url"]),
        ({"type": "url", "url": "http://127.0.0.1:8000/"}, 422, ["url"]),
        ({"type": "file"}, 422, ["file_asset_id"]),
        ({"type": "file", "file_asset_id": str(uuid.uuid4())}, 422, ["file_asset_id"]),
        ({"type": "note", "body": "x"}, 422, None),
    ],
)
async def test_create_checks_each_type(
    ws: Ws, body: dict[str, Any], status: int, fields: list[str] | None
) -> None:
    response = await ws.call("POST", "/knowledge-sources", json=body)
    assert response.status_code == status, response.text
    assert response.json()["code"] == "validation_error"
    if fields is not None:
        assert field_errors(response) == fields
    assert await jobs("ingest_knowledge_source") == []


async def test_the_metadata_address_is_refused_in_plain_words(ws: Ws) -> None:
    response = await ws.call(
        "POST",
        "/knowledge-sources",
        json={"type": "url", "url": "http://169.254.169.254/latest/meta-data/iam/"},
    )
    assert response.status_code == 422
    assert response.json()["errors"] == [
        {
            "field": "url",
            "message": "This address points to a private network. Use a public web page.",
        }
    ]


# ---------------------------------------------------------------- web pages (SEC-09)


@respx.mock
async def test_a_web_page_is_fetched_safely_and_named_by_its_heading(
    ws: Ws,
    engine: AsyncEngine,
    maker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
    dns: dict[str, list[str]],
) -> None:
    route = respx.get(f"https://{PUBLIC_IP}/shipping").respond(
        200, headers=HTML, content=SHIPPING_PAGE
    )
    created = await ws.ok(
        "POST",
        "/knowledge-sources",
        201,
        json={"type": "url", "url": "https://maple.example/shipping"},
    )
    assert created["title"] == "maple.example/shipping"

    assert await run_ingest(maker, http, ws, created) == "ready"

    assert route.calls.last.request.headers["host"] == "maple.example"
    source = await ws.ok("GET", f"/knowledge-sources/{created['id']}")
    assert source["title"] == "Shipping policy"
    assert source["status"] == "ready"
    stored = await chunks(engine, created["id"])
    assert all(c["content"].startswith("[Shipping policy] ") for c in stored)
    assert any("We ship to the UAE and Singapore." in c["content"] for c in stored)
    assert not any("Copyright" in c["content"] for c in stored)
    hits = await search(maker, ws.wid, "do you ship to the UAE", min_similarity=0.2)
    assert hits
    assert hits[0][0] == "Shipping policy"


@respx.mock
async def test_a_page_on_a_private_network_fails_without_a_request(
    ws: Ws,
    engine: AsyncEngine,
    maker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
    dns: dict[str, list[str]],
) -> None:
    dns["cloud.maple.example"] = ["169.254.169.254"]
    respx.get(f"https://{PUBLIC_IP}/moved").respond(
        302, headers={"location": "https://intranet.maple.example/prices"}
    )
    outcomes = {}
    for url in (
        "https://intranet.maple.example/prices",
        "http://cloud.maple.example/latest/meta-data/",
        "https://maple.example/moved",
    ):
        created = await ws.ok("POST", "/knowledge-sources", 201, json={"type": "url", "url": url})
        assert await run_ingest(maker, http, ws, created) == "failed"
        source = await ws.ok("GET", f"/knowledge-sources/{created['id']}")
        outcomes[url] = (source["status"], source["error"], source["chunk_count"])
        assert await chunks(engine, created["id"]) == []

    private = ("failed", ssrf.BLOCKED, 0)
    assert outcomes == {
        "https://intranet.maple.example/prices": private,
        "http://cloud.maple.example/latest/meta-data/": private,
        "https://maple.example/moved": private,
    }
    assert len(respx.calls) == 1  # only the public page that redirected


@respx.mock
async def test_page_failures_have_plain_reasons_and_transient_ones_retry(
    ws: Ws,
    maker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
    dns: dict[str, list[str]],
) -> None:
    respx.get(f"https://{PUBLIC_IP}/menu.pdf").respond(
        200, headers={"content-type": "application/pdf"}, content=b"%PDF"
    )
    respx.get(f"https://{PUBLIC_IP}/down").respond(503, headers=HTML)

    pdf = await ws.ok(
        "POST",
        "/knowledge-sources",
        201,
        json={"type": "url", "url": "https://maple.example/menu.pdf"},
    )
    assert await run_ingest(maker, http, ws, pdf) == "failed"
    failed = await ws.ok("GET", f"/knowledge-sources/{pdf['id']}")
    assert (
        failed["error"] == "This address isn't a web page. Add documents as a File source instead."
    )

    down = await ws.ok(
        "POST", "/knowledge-sources", 201, json={"type": "url", "url": "https://maple.example/down"}
    )
    with pytest.raises(ingest.RetryLater):
        await run_ingest(maker, http, ws, down, will_retry=True)
    assert (await ws.ok("GET", f"/knowledge-sources/{down['id']}"))["status"] == "processing"
    assert await run_ingest(maker, http, ws, down, will_retry=False) == "failed"  # final attempt
    last = await ws.ok("GET", f"/knowledge-sources/{down['id']}")
    assert (last["status"], last["error"]) == ("failed", "The page returned an error (503).")


# ---------------------------------------------------------------- files


@pytest.mark.parametrize(
    ("fmt", "content", "expected"),
    [
        (
            "pdf",
            make_pdf(["Opening hours", "We open at 9 am and close at 8 pm."]),
            "We open at 9 am",
        ),
        (
            "docx",
            make_docx([("h1", "Opening hours"), ("p", "We open at 9 am and close at 8 pm.")]),
            "# Opening hours\n\nWe open at 9 am",
        ),
        ("txt", b"We open at 9 am and close at 8 pm.", "We open at 9 am"),
        ("md", b"# Opening hours\n\nWe open at 9 am and close at 8 pm.", "We open at 9 am"),
    ],
    ids=["pdf", "docx", "txt", "md"],
)
@respx.mock
async def test_a_file_is_downloaded_and_read(
    ws: Ws,
    engine: AsyncEngine,
    maker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
    fmt: str,
    content: bytes,
    expected: str,
) -> None:
    asset_id = await make_asset(
        engine,
        workspace_id=ws.wid,
        purpose="knowledge",
        resource_type="raw",
        fmt=fmt,
        size=len(content),
    )
    [asset] = await rows(
        engine, "SELECT public_id, secure_url FROM media_assets WHERE id = :i", i=asset_id
    )
    respx.get(asset["secure_url"]).respond(200, content=content)

    created = await ws.ok(
        "POST", "/knowledge-sources", 201, json={"type": "file", "file_asset_id": str(asset_id)}
    )
    name = asset["public_id"].rsplit("/", 1)[-1] + f".{fmt}"
    assert (created["file_name"], created["title"]) == (name, name)
    assert await run_ingest(maker, http, ws, created) == "ready"

    source = await ws.ok("GET", f"/knowledge-sources/{created['id']}")
    assert source["status"] == "ready"
    [chunk] = await chunks(engine, created["id"])
    assert expected in chunk["content"]
    assert source["char_count"] == len(chunk["content"]) - len(f"[{name}] ")


async def test_only_knowledge_files_up_to_10_mb_are_accepted(ws: Ws, engine: AsyncEngine) -> None:
    image = await make_asset(engine, workspace_id=ws.wid)
    big = await make_asset(
        engine,
        workspace_id=ws.wid,
        purpose="knowledge",
        resource_type="raw",
        fmt="pdf",
        size=11 * 1024**2,
    )
    for asset_id in (image, big):
        response = await ws.call(
            "POST", "/knowledge-sources", json={"type": "file", "file_asset_id": str(asset_id)}
        )
        assert response.status_code == 415, response.text
        assert response.json()["detail"] == (
            "Knowledge files can be PDF, Word (DOCX), TXT or Markdown, up to 10 MB."
        )


@respx.mock
async def test_an_unreadable_file_fails_with_its_reason(
    ws: Ws, engine: AsyncEngine, maker: async_sessionmaker[AsyncSession], http: httpx.AsyncClient
) -> None:
    asset_id = await make_asset(
        engine, workspace_id=ws.wid, purpose="knowledge", resource_type="raw", fmt="pdf", size=100
    )
    [asset] = await rows(engine, "SELECT secure_url FROM media_assets WHERE id = :i", i=asset_id)
    respx.get(asset["secure_url"]).respond(200, content=make_pdf([]))

    created = await ws.ok(
        "POST",
        "/knowledge-sources",
        201,
        json={"type": "file", "file_asset_id": str(asset_id), "title": "Menu"},
    )
    assert await run_ingest(maker, http, ws, created) == "failed"
    source = await ws.ok("GET", f"/knowledge-sources/{created['id']}")
    assert source["title"] == "Menu"
    assert source["error"].startswith("Couldn't find any text in this PDF.")
    assert (source["char_count"], source["chunk_count"]) == (0, 0)


# ---------------------------------------------------------------- edits and deletes


async def test_an_edit_replaces_the_chunks_atomically_and_older_jobs_are_dropped(
    ws: Ws,
    engine: AsyncEngine,
    maker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
    fake_ai: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    v1 = await ws.ok(
        "POST",
        "/knowledge-sources",
        201,
        json={"type": "faq", "question": "How much is shipping?", "body": "Shipping costs Rs 50."},
    )
    await run_ingest(maker, http, ws, v1)
    [old] = await chunks(engine, v1["id"])

    v2 = await ws.ok("PATCH", f"/knowledge-sources/{v1['id']}", json={"body": "Shipping is free."})
    assert (v2["version"], v2["status"], v2["body"]) == (2, "pending", "Shipping is free.")
    queued = await jobs("ingest_knowledge_source")
    assert [j["queueing_lock"] for j in queued] == [f"kb:{v1['id']}:1", f"kb:{v1['id']}:2"]
    assert not queued[-1]["deferred"]
    # Until the new version is ready, the source isn't used (only ready sources are searched).
    assert await search(maker, ws.wid, "How much is shipping?") == []

    seen_during_embedding: list[list[dict[str, Any]]] = []
    embed = fake_ai.embed

    async def watching(texts: list[str], *, kind: EmbedKind) -> list[list[float]]:
        if kind == "document":
            seen_during_embedding.append(await chunks(engine, v1["id"]))
        return await embed(texts, kind=kind)

    monkeypatch.setattr(fake_ai, "embed", watching)
    assert await run_ingest(maker, http, ws, v2) == "ready"

    assert seen_during_embedding == [[old]]  # the old chunk stays until the swap
    [new] = await chunks(engine, v1["id"])
    assert new["id"] != old["id"]
    assert (new["source_version"], new["content"]) == (
        2,
        "[How much is shipping?] Q: How much is shipping?\nA: Shipping is free.",
    )
    assert [t for t, _ in await search(maker, ws.wid, "How much is shipping?")] == [
        "How much is shipping?"
    ]
    # The version-1 job arriving late changes nothing.
    assert await run_ingest(maker, http, ws, v1) == "stale"
    assert await chunks(engine, v1["id"]) == [new]


async def test_edits_follow_the_type_and_reingest_on_request(ws: Ws, engine: AsyncEngine) -> None:
    faq = await ws.ok(
        "POST",
        "/knowledge-sources",
        201,
        json={"type": "faq", "question": "Do you deliver?", "body": "Yes, in Pune."},
    )
    renamed = await ws.ok(
        "PATCH", f"/knowledge-sources/{faq['id']}", json={"question": "Do you deliver on Sundays?"}
    )
    assert (renamed["title"], renamed["version"]) == ("Do you deliver on Sundays?", 2)

    same = await ws.ok("PATCH", f"/knowledge-sources/{faq['id']}", json={"body": "Yes, in Pune."})
    assert same["version"] == 2  # nothing changed: no new version, no job
    again = await ws.ok("PATCH", f"/knowledge-sources/{faq['id']}", json={"reingest": True})
    assert again["version"] == 3

    wrong = await ws.call(
        "PATCH", f"/knowledge-sources/{faq['id']}", json={"url": "https://a.example"}
    )
    assert (wrong.status_code, field_errors(wrong)) == (422, ["url"])

    page = await ws.ok(
        "POST", "/knowledge-sources", 201, json={"type": "url", "url": "https://maple.example/a"}
    )
    moved = await ws.ok(
        "PATCH", f"/knowledge-sources/{page['id']}", json={"url": "https://maple.example/b"}
    )
    assert (moved["url"], moved["title"], moved["version"]) == (
        "https://maple.example/b",
        "maple.example/b",
        2,
    )
    blocked = await ws.call(
        "PATCH", f"/knowledge-sources/{page['id']}", json={"url": "http://169.254.169.254/"}
    )
    assert (blocked.status_code, field_errors(blocked)) == (422, ["url"])

    locks = [j["queueing_lock"] for j in await jobs("ingest_knowledge_source")]
    assert locks == [
        f"kb:{faq['id']}:1",
        f"kb:{faq['id']}:2",
        f"kb:{faq['id']}:3",
        f"kb:{page['id']}:1",
        f"kb:{page['id']}:2",
    ]


async def test_delete_removes_the_source_and_its_chunks(ws: Ws, engine: AsyncEngine) -> None:
    source_id = await make_source(engine, workspace_id=ws.wid)

    assert (await ws.call("DELETE", f"/knowledge-sources/{source_id}")).status_code == 204
    assert await chunks(engine, str(source_id)) == []
    assert (await ws.call("GET", f"/knowledge-sources/{source_id}")).status_code == 404
    assert (await ws.call("DELETE", f"/knowledge-sources/{source_id}")).status_code == 404


async def added_knowledge(ws: Ws) -> bool:
    """Home's checklist step (FR-ACC-04)."""
    steps = (await ws.ok("GET", "/overview"))["checklist"]["steps"]
    return bool(next(s["done"] for s in steps if s["key"] == "add_knowledge"))


async def test_the_list_shows_every_source_and_the_usage(ws: Ws, engine: AsyncEngine) -> None:
    empty = await ws.ok("GET", "/knowledge-sources")
    assert empty == {"items": [], "usage": {"characters_used": 0, "characters_limit": 200_000}}
    assert not await added_knowledge(ws)

    await make_source(engine, workspace_id=ws.wid, question="Q1?", body="A" * 100)
    assert await added_knowledge(ws)
    await ws.ok(
        "POST", "/knowledge-sources", 201, json={"type": "text", "title": "Hours", "body": "9 to 5"}
    )

    listed = await ws.ok("GET", "/knowledge-sources")
    assert [s["title"] for s in listed["items"]] == ["Hours", "Q1?"]  # newest first
    assert listed["usage"] == {"characters_used": 3 + 100 + 6, "characters_limit": 200_000}

    await set_plan(engine, ws.wid, "pro")
    assert (await ws.ok("GET", "/knowledge-sources"))["usage"]["characters_limit"] == 5_000_000


async def test_the_knowledge_characters_limit(
    ws: Ws,
    engine: AsyncEngine,
    maker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
    dns: dict[str, list[str]],
) -> None:
    big = await make_source(engine, workspace_id=ws.wid, char_count=199_980)

    over = await ws.call(
        "POST",
        "/knowledge-sources",
        json={"type": "faq", "question": "Do you ship?", "body": "Yes, across India."},
    )
    assert over.status_code == 402
    assert over.json()["code"] == "quota_exceeded"
    assert "200,000 characters" in over.json()["detail"]
    fits = await ws.ok(
        "POST", "/knowledge-sources", 201, json={"type": "text", "title": "Hi", "body": "Hello"}
    )
    grow = await ws.call("PATCH", f"/knowledge-sources/{fits['id']}", json={"body": "Hello" * 10})
    assert grow.status_code == 402

    # A page's length is known only once it is read: it fails then, with the reason.
    with respx.mock:
        respx.get(f"https://{PUBLIC_IP}/shipping").respond(200, headers=HTML, content=SHIPPING_PAGE)
        page = await ws.ok(
            "POST",
            "/knowledge-sources",
            201,
            json={"type": "url", "url": "https://maple.example/shipping"},
        )
        assert await run_ingest(maker, http, ws, page) == "failed"
    failed = await ws.ok("GET", f"/knowledge-sources/{page['id']}")
    assert "left on your plan" in failed["error"]

    async with engine.begin() as conn:  # at the limit: nothing of unknown length is accepted
        await conn.execute(
            text("UPDATE knowledge_sources SET char_count = 200000 WHERE id = :i"), {"i": big}
        )
    at_limit = await ws.call(
        "POST", "/knowledge-sources", json={"type": "url", "url": "https://maple.example/more"}
    )
    assert at_limit.status_code == 402
    # Over the limit, a source can still be shortened.
    await ws.ok("PATCH", f"/knowledge-sources/{fits['id']}", json={"body": "Hi"})

    await set_plan(engine, ws.wid, "pro")
    await ws.ok(
        "POST",
        "/knowledge-sources",
        201,
        json={"type": "faq", "question": "Do you ship?", "body": "Yes, across India."},
    )


# ---------------------------------------------------------------- retrieval (TR-AI-08)


async def test_retrieval_keeps_similar_chunks_of_ready_sources_in_this_workspace(
    engine: AsyncEngine, maker: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    from tests.support.inbox import make_workspace

    a, b = await make_workspace(engine), await make_workspace(engine)
    question, answer = "What are your opening hours?", "We open at 9 am."
    await make_source(engine, workspace_id=a, question=question, body=answer)
    await make_source(engine, workspace_id=b, question=question, body=answer, title="B's hours")
    await make_source(engine, workspace_id=a, question="Do you sell gift cards?", body="No.")
    await make_source(
        engine, workspace_id=a, question=question, body=answer, title="Draft", status="processing"
    )

    hits = await search(maker, str(a), "what are your opening hours")
    assert [title for title, _ in hits] == [
        "What are your opening hours?"
    ]  # not B's, not the draft
    assert hits[0][1] >= 0.6
    assert await search(maker, str(a), "refund policy for damaged cakes") == []  # below 0.60
    assert await search(maker, str(a), "   ") == []


async def test_retrieval_returns_at_most_six_of_the_eight_nearest(
    engine: AsyncEngine, maker: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    from tests.support.inbox import make_workspace

    wid = await make_workspace(engine)
    for n in range(10):
        await make_source(
            engine, workspace_id=wid, question=f"Cake price {n}?", body=f"Cake price {n}."
        )

    hits = await search(maker, str(wid), "cake price", min_similarity=0.0)
    assert len(hits) == 6
    assert [s for _, s in hits] == sorted((s for _, s in hits), reverse=True)
    assert len(await search(maker, str(wid), "cake price", min_similarity=0.0, limit=10)) == 10


async def test_the_retrieval_session_scans_iteratively(
    engine: AsyncEngine, maker: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    from tests.support.inbox import make_workspace

    wid = await make_workspace(engine)
    with workspace_scope(wid):
        async with maker() as session:
            await retrieve(session, "anything")
            setting = await session.scalar(text("SHOW hnsw.iterative_scan"))
    assert setting == "relaxed_order"


# ---------------------------------------------------------------- the test box (FR-KB-03)


async def set_credits_used(
    maker: async_sessionmaker[AsyncSession], engine: AsyncEngine, wid: str, used: int
) -> None:
    with workspace_scope(uuid.UUID(wid)):
        async with maker() as session:
            await quota(session, now=datetime.now(UTC))
            await session.commit()
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE usage_counters SET used = :u WHERE workspace_id = :w"),
            {"u": used, "w": wid},
        )


async def test_the_test_box_drafts_an_answer_with_its_sources(
    ws: Ws, engine: AsyncEngine, fake_ai: FakeProvider
) -> None:
    source_id = await make_source(
        engine,
        workspace_id=ws.wid,
        question="How much is shipping to Dubai?",
        body="Shipping to Dubai costs Rs 1,500.",
    )
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE ai_settings SET business_description = 'Cakes from Pune', tone = 'playful'"
                " WHERE workspace_id = :w"
            ),
            {"w": ws.wid},
        )

    def answer(call: FakeCall) -> dict[str, Any]:
        knowledge = call.contents[0].text
        assert knowledge.startswith("KNOWLEDGE")
        assert (
            "[k1] (How much is shipping to Dubai?) Q: How much is shipping to Dubai?" in knowledge
        )
        return {
            "can_answer": True,
            "reply": " Shipping to Dubai costs Rs 1,500. ",
            "confidence": 0.9,
            "used_source_ids": ["k1", "k7", "[K1]"],
        }

    fake_ai.respond("suggest", answer)
    result = await ws.ok(
        "POST", "/knowledge/test", json={"question": "How much is shipping to Dubai?"}
    )

    assert result == {
        "can_answer": True,
        "answer": "Shipping to Dubai costs Rs 1,500.",
        "missing_info": None,
        "sources": [{"id": str(source_id), "title": "How much is shipping to Dubai?"}],
    }
    [call] = fake_ai.calls_for("suggest")
    assert "Cakes from Pune" in call.system
    assert "Voice: playful" in call.system
    assert "Rs 1,500" not in call.system  # knowledge is data in the contents (SEC-10)
    assert (call.temperature, call.max_output_tokens, call.timeout_s) == (0.4, 600, 12.0)
    assert call.contents[-1].text.endswith("How much is shipping to Dubai?")
    [counter] = await rows(
        engine, "SELECT used FROM usage_counters WHERE workspace_id = :w", w=ws.wid
    )
    assert counter["used"] == 1
    [event] = await rows(engine, "SELECT feature, credits FROM ai_usage_events")
    assert event == {"feature": "knowledge_test", "credits": 1}
    assert await rows(engine, "SELECT id FROM reply_suggestions") == []  # nothing is stored


async def test_not_in_your_knowledge(ws: Ws, fake_ai: FakeProvider) -> None:
    fake_ai.respond(
        "suggest",
        {
            "can_answer": False,
            "reply": None,
            "missing_info": "whether you ship to Dubai",
            "missing_topic": "shipping to uae",
            "confidence": 0.2,
            "used_source_ids": [],
        },
    )
    result = await ws.ok("POST", "/knowledge/test", json={"question": "Do you ship to Dubai?"})

    assert result == {
        "can_answer": False,
        "answer": None,
        "missing_info": "whether you ship to Dubai",
        "sources": [],
    }
    [call] = fake_ai.calls_for("suggest")
    assert call.contents[0].text.startswith("KNOWLEDGE: nothing")


async def test_the_test_box_needs_a_credit_and_a_working_ai(
    ws: Ws, engine: AsyncEngine, maker: async_sessionmaker[AsyncSession], fake_ai: FakeProvider
) -> None:
    await set_credits_used(maker, engine, ws.wid, 200)
    spent = await ws.call("POST", "/knowledge/test", json={"question": "Hi?"})
    assert (spent.status_code, spent.json()["code"]) == (402, "quota_exceeded")
    assert fake_ai.calls == []

    await set_credits_used(maker, engine, ws.wid, 0)
    fake_ai.respond("suggest", AIError("timeout", retryable=True))
    down = await ws.call("POST", "/knowledge/test", json={"question": "Hi?"})
    assert (down.status_code, down.json()["code"]) == (503, "service_unavailable")
    [counter] = await rows(
        engine, "SELECT used FROM usage_counters WHERE workspace_id = :w", w=ws.wid
    )
    assert counter["used"] == 0  # refunded


async def test_knowledge_is_for_admins(ws: Ws, engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspace_members SET role = 'agent' WHERE workspace_id = :w"),
            {"w": ws.wid},
        )
    for method, path in (
        ("GET", "/knowledge-sources"),
        ("GET", "/knowledge-gaps"),
    ):
        response = await ws.call(method, path)
        assert response.status_code == 403, f"{method} {path}"
