"""GR-35: a website crawled into knowledge. A fixture bakery site (tests/support/knowledge.py,
answered by respx behind a fake DNS: nothing leaves the machine) is crawled by the job's own
function, its pages are ingested by the existing ingest job's function, and the API shows the
site with its pages. Covers the crawl end to end, the plan's page cap, a resumed crawl, the
re-crawl (what changed, what is gone), removing a page and excluding a path, the scheduled
re-crawl, the roles, tenancy and the SSRF rules.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from socialhood.billing import plans
from socialhood.db.engine import make_sessionmaker
from socialhood.jobs.tasks import knowledge as knowledge_tasks
from socialhood.security import ssrf
from socialhood.services.knowledge import crawl, ingest
from tests.support.ai import make_site, make_source
from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.ingest import jobs, rows
from tests.support.knowledge import HOSTS, PUBLIC_IP, article, fake_dns, maple_site, serve

START = "https://maple.example/"
SITEMAP = (
    "https://maple.example/shipping",
    "https://maple.example/returns",
    "https://maple.example/about",
    "https://maple.example/private/secret",
    "https://maple.example/menu.pdf",
    "https://other.example/partner",
)
PAGES = ["/", "/shipping", "/returns", "/about", "/blog", "/blog/first"]
OTHER_IP = "93.184.216.35"


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk, queue: None) -> Ws:
    return await workspace(client, clerk)


@pytest.fixture
def maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return make_sessionmaker(engine)


@pytest.fixture
async def http() -> Any:
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture(autouse=True)
def dns(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    table = {**HOSTS, "other.example": [OTHER_IP]}
    monkeypatch.setattr(ssrf, "resolve_host", fake_dns(table))
    return table


async def no_sleep(seconds: float) -> None:
    return None


async def new_site(ws: Ws, url: str = START, **values: Any) -> dict[str, Any]:
    return await ws.ok(
        "POST", "/knowledge-sources", 201, json={"type": "site", "url": url, **values}
    )


async def run(
    maker: async_sessionmaker[AsyncSession],
    ws: Ws,
    site: dict[str, Any],
    *,
    version: int | None = None,
    budget_s: float = 120.0,
    will_retry: bool = False,
) -> str:
    return await crawl.run_crawl(
        maker,
        workspace_id=uuid.UUID(ws.wid),
        source_id=uuid.UUID(site["id"]),
        version=version or site["version"],
        will_retry=will_retry,
        delay_s=0.0,
        budget_s=budget_s,
        sleep=no_sleep,
    )


async def ingest_pending(
    maker: async_sessionmaker[AsyncSession], http: httpx.AsyncClient, ws: Ws, engine: AsyncEngine
) -> list[str]:
    """Run the ingest job's function for every page-source waiting; their urls."""
    pending = await rows(
        engine,
        "SELECT id, version, url FROM knowledge_sources"
        " WHERE type = 'page' AND status = 'pending' ORDER BY url",
    )
    for source in pending:
        outcome = await ingest.ingest_source(
            maker,
            http,
            workspace_id=uuid.UUID(ws.wid),
            source_id=source["id"],
            version=source["version"],
            will_retry=False,
        )
        assert outcome == "ready", source["url"]
    return [source["url"] for source in pending]


async def pages(ws: Ws, site: dict[str, Any], **query: Any) -> dict[str, dict[str, Any]]:
    listing = await ws.ok("GET", f"/knowledge-sources/{site['id']}/pages", params=query)
    assert listing["total"] == len(listing["items"])
    return {item["url"].removeprefix("https://maple.example"): item for item in listing["items"]}


def requested() -> list[str]:
    return [call.request.url.path for call in respx.calls]


async def get_site(ws: Ws, site: dict[str, Any]) -> dict[str, Any]:
    return await ws.ok("GET", f"/knowledge-sources/{site['id']}")


async def chunk_sources(engine: AsyncEngine) -> dict[str, int]:
    found = await rows(
        engine,
        "SELECT s.url, c.source_version FROM knowledge_chunks c JOIN knowledge_sources s"
        " ON s.id = c.source_id ORDER BY s.url",
    )
    return {
        row["url"].removeprefix("https://maple.example"): row["source_version"] for row in found
    }


# ---------------------------------------------------------------- the crawl, end to end


@respx.mock
async def test_a_site_is_crawled_into_page_sources_and_found(
    ws: Ws,
    engine: AsyncEngine,
    maker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
) -> None:
    maple_site(sitemap=SITEMAP)
    other = respx.get(f"https://{OTHER_IP}/partner").respond(200)

    site = await new_site(ws)
    assert (site["type"], site["status"], site["version"]) == ("site", "pending", 1)
    assert site["title"] == "maple.example"
    assert site["site"]["status"] == "queued"
    assert site["site"]["recrawl"] == "weekly"
    assert site["site"]["page_cap"] == plans.ENTITLEMENTS["crawl_pages"]["free"]
    [job] = await jobs("crawl_site")
    assert job["queue_name"] == "bulk"
    assert job["queueing_lock"] == f"crawl:{site['id']}:1"
    assert job["args"] == {"workspace_id": ws.wid, "source_id": site["id"], "version": 1}
    assert await jobs("ingest_knowledge_source") == []  # a site is crawled, not ingested

    assert await run(maker, ws, site) == "done"

    # Sitemap first, then breadth first; only same-site pages robots.txt allows.
    assert requested() == ["/robots.txt", "/sitemap.xml", *PAGES]
    assert not other.called
    site = await get_site(ws, site)
    assert (site["status"], site["error"], site["char_count"]) == ("ready", None, 0)
    assert site["last_ingested_at"] is not None
    info = site["site"]
    assert (info["status"], info["pages_found"], info["pages_done"]) == ("done", 6, 6)
    assert (info["pages_failed"], info["pages_skipped"], info["truncated"]) == (0, 0, False)
    assert info["started_at"] is not None
    assert info["finished_at"] is not None
    assert info["next_crawl_at"] is not None

    listing = await pages(ws, site)
    assert list(listing) == PAGES  # shallowest first, then in the order found
    assert listing["/shipping"]["title"] == "Shipping policy"
    assert {item["status"] for item in listing.values()} == {"done"}
    assert {item["ingest_status"] for item in listing.values()} == {"pending"}

    # Each page is a source of its own, queued for the existing ingest job.
    queued = await jobs("ingest_knowledge_source")
    assert len(queued) == 6
    assert all(job["queueing_lock"].endswith(":1") for job in queued)
    await ingest_pending(maker, http, ws, engine)
    assert await chunk_sources(engine) == {p: 1 for p in PAGES}
    listing = await pages(ws, site)
    assert {item["ingest_status"] for item in listing.values()} == {"ready"}
    assert listing["/shipping"]["chunk_count"] >= 1

    # The main list shows the site only, with the pages' characters in the usage.
    everything = await ws.ok("GET", "/knowledge-sources")
    assert [item["id"] for item in everything["items"]] == [site["id"]]
    assert everything["usage"]["characters_used"] > 0
    assert everything["items"][0]["site"]["pages_done"] == 6

    # Retrieval finds a page by what it says.
    hits = await rows(
        engine,
        "SELECT s.title FROM knowledge_chunks c JOIN knowledge_sources s ON s.id = c.source_id"
        " WHERE c.content ILIKE '%UAE%'",
    )
    assert {hit["title"] for hit in hits} == {"Shipping policy"}


@respx.mock
async def test_the_plans_page_cap_stops_the_crawl_and_says_so(
    ws: Ws,
    maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(plans.ENTITLEMENTS["crawl_pages"], "free", 3)
    maple_site(sitemap=SITEMAP)

    site = await new_site(ws)
    assert site["site"]["page_cap"] == 3
    assert await run(maker, ws, site) == "done"

    info = (await get_site(ws, site))["site"]
    assert (info["pages_found"], info["truncated"]) == (3, True)
    assert list(await pages(ws, site)) == ["/", "/shipping", "/returns"]  # the start page first
    assert "/about" not in requested()


@respx.mock
async def test_a_better_plan_reads_more_pages(
    ws: Ws,
    engine: AsyncEngine,
    maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(plans.ENTITLEMENTS["crawl_pages"], "free", 2)
    monkeypatch.setitem(plans.ENTITLEMENTS["crawl_pages"], "pro", 50)
    await set_plan(engine, ws.wid, "pro")
    maple_site(sitemap=SITEMAP)
    site = await new_site(ws)
    assert site["site"]["page_cap"] == 50
    assert await run(maker, ws, site) == "done"
    assert (await get_site(ws, site))["site"]["pages_done"] == 6


@respx.mock
async def test_a_crawl_that_runs_out_of_time_carries_on_where_it_stopped(
    ws: Ws, maker: async_sessionmaker[AsyncSession]
) -> None:
    maple_site(sitemap=SITEMAP)
    site = await new_site(ws)

    assert await run(maker, ws, site, budget_s=-1.0) == "more"
    info = (await get_site(ws, site))["site"]
    assert info["status"] == "running"
    assert info["pages_found"] == 4  # the start page and the sitemap's three
    assert info["pages_done"] == 0
    assert (await get_site(ws, site))["status"] == "processing"

    assert await run(maker, ws, site) == "done"
    assert (await get_site(ws, site))["site"]["pages_done"] == 6
    assert list(await pages(ws, site)) == PAGES  # no page twice
    assert requested().count("/sitemap.xml") == 1  # seeded once
    assert requested().count("/") == 1


@respx.mock
async def test_a_job_for_an_older_crawl_or_a_finished_one_does_nothing(
    ws: Ws, maker: async_sessionmaker[AsyncSession]
) -> None:
    maple_site()
    site = await new_site(ws)
    assert await run(maker, ws, site, version=99) == "stale"
    assert not respx.calls
    assert await run(maker, ws, site) == "done"
    calls = len(respx.calls)
    assert await run(maker, ws, site) == "stale"  # a repeated job
    assert len(respx.calls) == calls
    gone = await ws.call("DELETE", f"/knowledge-sources/{site['id']}")
    assert gone.status_code == 204
    assert await run(maker, ws, site) == "stale"


@respx.mock
async def test_links_without_a_sitemap_are_followed_breadth_first(
    ws: Ws, maker: async_sessionmaker[AsyncSession]
) -> None:
    maple_site()  # no sitemap: /sitemap.xml answers 404
    site = await new_site(ws)
    assert await run(maker, ws, site) == "done"
    assert requested() == [
        "/robots.txt",
        "/sitemap.xml",
        "/",
        "/shipping",
        "/returns",
        "/blog",
        "/about",
        "/blog/first",
    ]


@respx.mock
async def test_robots_noindex_and_other_sites_are_skipped_not_added(
    ws: Ws, maker: async_sessionmaker[AsyncSession]
) -> None:
    routes = maple_site()
    routes["/returns"].respond(
        200,
        headers={"content-type": "text/html"},
        content=b'<meta name="robots" content="noindex"><p>Hidden</p>',
    )
    site = await new_site(ws)
    assert await run(maker, ws, site) == "done"

    assert "/private/secret" not in requested()
    assert "/menu.pdf" not in requested()
    listing = await pages(ws, site)
    assert listing["/returns"]["status"] == "skipped"
    assert "indexed" in listing["/returns"]["error"]
    assert "/private/secret" not in listing
    assert (await get_site(ws, site))["site"]["pages_skipped"] == 1


@respx.mock
async def test_a_failing_page_does_not_stop_the_crawl(
    ws: Ws, maker: async_sessionmaker[AsyncSession]
) -> None:
    routes = maple_site()
    routes["/shipping"].respond(503)
    site = await new_site(ws)
    assert await run(maker, ws, site) == "done"
    info = (await get_site(ws, site))["site"]
    assert (info["pages_failed"], info["pages_done"]) == (1, 4)  # its links aren't found
    failed = (await pages(ws, site))["/shipping"]
    assert failed["status"] == "failed"
    assert "503" in failed["error"]
    assert requested().count("/shipping") == 2  # one retry


@respx.mock
async def test_a_site_whose_start_page_cannot_be_read_fails_with_the_reason(
    ws: Ws, maker: async_sessionmaker[AsyncSession]
) -> None:
    routes = maple_site()
    routes["/"].respond(404)
    site = await new_site(ws)
    assert await run(maker, ws, site) == "failed"
    after = await get_site(ws, site)
    assert after["status"] == "failed"
    assert after["error"] == after["site"]["error"]
    assert after["error"]


@respx.mock
async def test_a_site_that_disallows_us_is_not_crawled(
    ws: Ws, maker: async_sessionmaker[AsyncSession]
) -> None:
    maple_site(robots="User-agent: *\nDisallow: /\n")
    site = await new_site(ws)
    assert await run(maker, ws, site) == "failed"
    assert (await get_site(ws, site))["error"] == crawl.START_BLOCKED
    assert requested() == ["/robots.txt"]


@respx.mock
async def test_a_redirect_to_the_www_host_is_the_same_site(
    ws: Ws, maker: async_sessionmaker[AsyncSession]
) -> None:
    maple_site()
    respx.get(f"https://{PUBLIC_IP}/old-home").respond(
        301, headers={"location": "https://www.maple.example/returns"}
    )
    site = await new_site(ws, url="https://maple.example/old-home")
    assert await run(maker, ws, site) == "done"
    listing = await pages(ws, site)
    # Stored under the address it ended at, not the one that redirected.
    assert list(listing) == ["https://www.maple.example/returns"]


# ---------------------------------------------------------------- re-crawl


def conditional(routes: dict[str, Any], path: str, etag: str) -> None:
    """The page answers 304 to a request that holds its current ETag."""
    body = article("Shipping policy", "Shipping to the UAE and India", ("/about",))

    def answer(request: httpx.Request) -> httpx.Response:
        if request.headers.get("if-none-match") == etag:
            return httpx.Response(304)
        return httpx.Response(
            200, headers={"content-type": "text/html", "etag": etag}, content=body
        )

    routes[path].mock(side_effect=answer)


@respx.mock
async def test_a_recrawl_reads_again_only_what_changed_and_removes_what_is_gone(
    ws: Ws,
    engine: AsyncEngine,
    maker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
) -> None:
    routes = maple_site(sitemap=SITEMAP)
    conditional(routes, "/shipping", '"ship1"')
    site = await new_site(ws)
    assert await run(maker, ws, site) == "done"
    await ingest_pending(maker, http, ws, engine)
    assert await chunk_sources(engine) == {p: 1 for p in PAGES}
    versions = {
        row["url"].removeprefix("https://maple.example"): row["version"]
        for row in await rows(
            engine, "SELECT url, version FROM knowledge_sources WHERE type='page'"
        )
    }
    assert set(versions.values()) == {1}

    # The site changes: /returns has new text, /blog/first is gone, /blog links a new page,
    # /shipping is unchanged (ETag), /about is unchanged but has no ETag (the text hash decides).
    routes["/returns"].respond(
        200,
        headers={"content-type": "text/html"},
        content=article("Returns", "Returns and refunds now take 14 days"),
    )
    routes["/blog/first"].respond(404)
    routes["/blog"].respond(
        200,
        headers={"content-type": "text/html"},
        content=article("Blog", "News from the bakery", ("/blog/first", "/blog/second")),
    )
    serve("/blog/second", article("Second post", "Our second blog post"))
    respx.calls.reset()

    again = await ws.ok("POST", f"/knowledge-sources/{site['id']}/recrawl")
    assert (again["version"], again["status"], again["site"]["status"]) == (2, "pending", "queued")
    assert again["site"]["pages_found"] == 6  # the pages stay listed while it runs
    again_twice = await ws.ok("POST", f"/knowledge-sources/{site['id']}/recrawl")
    assert again_twice["version"] == 2  # one crawl at a time: nothing changed
    crawls = await jobs("crawl_site")
    assert [job["queueing_lock"] for job in crawls] == [
        f"crawl:{site['id']}:1",
        f"crawl:{site['id']}:2",
    ]

    assert await run(maker, ws, site, version=2) == "done"

    assert requested().count("/shipping") == 1  # asked, and told it hasn't changed
    sent = [c.request for c in respx.calls if c.request.url.path == "/shipping"]
    assert sent[0].headers["if-none-match"] == '"ship1"'
    after = {
        row["url"].removeprefix("https://maple.example"): row
        for row in await rows(
            engine, "SELECT url, version, status FROM knowledge_sources WHERE type='page'"
        )
    }
    assert after["/returns"]["version"] == 2  # changed: a new version, ingested again
    assert after["/returns"]["status"] == "pending"
    assert after["/shipping"]["version"] == 1  # 304
    assert after["/about"]["version"] == 1  # same text hash
    assert after["/blog/second"]["version"] == 1  # new
    assert "/blog/first" not in after  # gone: its source goes with its chunks
    listing = await pages(ws, site)
    assert listing["/blog/first"]["status"] == "gone"
    assert listing["/blog/second"]["status"] == "done"
    assert (await get_site(ws, site))["site"]["pages_found"] == 6  # 6 - 1 gone + 1 new

    # Only the changed and the new pages are ingested again; the rest keep their chunks.
    locks = {job["queueing_lock"] for job in await jobs("ingest_knowledge_source")}
    [returns] = await rows(engine, "SELECT id FROM knowledge_sources WHERE url LIKE '%/returns'")
    assert f"kb:{returns['id']}:2" in locks
    assert len(locks) == 6 + 2
    assert sorted(await ingest_pending(maker, http, ws, engine)) == [
        "https://maple.example/blog/second",
        "https://maple.example/returns",
    ]
    assert await chunk_sources(engine) == {
        "/about": 1,
        "/blog": 1,
        "/blog/second": 1,
        "/returns": 2,
        "/shipping": 1,
        "/": 1,
    }
    final = await get_site(ws, site)
    assert (final["status"], final["site"]["status"]) == ("ready", "done")


@respx.mock
async def test_a_page_that_comes_back_after_being_gone_is_added_again(
    ws: Ws, maker: async_sessionmaker[AsyncSession]
) -> None:
    routes = maple_site(sitemap=SITEMAP)
    routes["/about"].respond(404)
    site = await new_site(ws)
    assert await run(maker, ws, site) == "done"
    assert (await pages(ws, site))["/about"]["status"] == "gone"
    routes["/about"].respond(
        200, headers={"content-type": "text/html"}, content=article("About us", "Our story")
    )
    await ws.ok("POST", f"/knowledge-sources/{site['id']}/recrawl")
    assert await run(maker, ws, site, version=2) == "done"
    assert (await pages(ws, site))["/about"]["status"] == "done"


@respx.mock
async def test_a_recrawl_is_refused_quietly_while_one_runs(
    ws: Ws, maker: async_sessionmaker[AsyncSession]
) -> None:
    maple_site()
    site = await new_site(ws)
    assert await run(maker, ws, site, budget_s=-1.0) == "more"  # running
    still = await ws.ok("POST", f"/knowledge-sources/{site['id']}/recrawl")
    assert (still["version"], still["site"]["status"]) == (1, "running")
    assert len(await jobs("crawl_site")) == 1
    assert await run(maker, ws, site) == "done"
    next_run = await ws.ok("POST", f"/knowledge-sources/{site['id']}/recrawl")
    assert (next_run["version"], next_run["site"]["status"]) == (2, "queued")
    # `reingest` in an edit is the same request.
    await ws.ok("PATCH", f"/knowledge-sources/{site['id']}", json={"reingest": True})
    assert await run(maker, ws, site, version=2) == "done"
    edited = await ws.ok("PATCH", f"/knowledge-sources/{site['id']}", json={"reingest": True})
    assert edited["version"] == 3


# ---------------------------------------------------------------- remove a page, exclude a path


@respx.mock
async def test_a_removed_page_leaves_knowledge_and_is_not_added_back(
    ws: Ws,
    engine: AsyncEngine,
    maker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
) -> None:
    maple_site(sitemap=SITEMAP)
    site = await new_site(ws)
    await run(maker, ws, site)
    await ingest_pending(maker, http, ws, engine)
    returns = (await pages(ws, site))["/returns"]

    response = await ws.call("DELETE", f"/knowledge-sources/{site['id']}/pages/{returns['id']}")
    assert response.status_code == 204
    assert "/returns" not in await chunk_sources(engine)
    assert (await pages(ws, site))["/returns"]["status"] == "removed"
    assert (await pages(ws, site, status="removed")).keys() == {"/returns"}

    respx.calls.reset()
    await ws.ok("POST", f"/knowledge-sources/{site['id']}/recrawl")
    await run(maker, ws, site, version=2)
    assert "/returns" not in requested()
    assert (await pages(ws, site))["/returns"]["status"] == "removed"
    assert "/returns" not in await chunk_sources(engine)

    missing = await ws.call("DELETE", f"/knowledge-sources/{site['id']}/pages/{uuid.uuid4()}")
    assert missing.status_code == 404


@respx.mock
async def test_an_excluded_path_removes_its_pages_and_is_not_crawled(
    ws: Ws,
    engine: AsyncEngine,
    maker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
) -> None:
    maple_site(sitemap=SITEMAP)
    site = await new_site(ws)
    await run(maker, ws, site)
    await ingest_pending(maker, http, ws, engine)
    assert {"/blog", "/blog/first"} <= set(await chunk_sources(engine))

    excluded = await ws.ok(
        "POST",
        f"/knowledge-sources/{site['id']}/excluded-paths",
        json={"path": "https://maple.example/blog/"},
    )
    assert excluded["site"]["excluded_paths"] == ["/blog"]
    listing = await pages(ws, site)
    assert (listing["/blog"]["status"], listing["/blog/first"]["status"]) == (
        "excluded",
        "excluded",
    )
    assert not {"/blog", "/blog/first"} & set(await chunk_sources(engine))
    assert excluded["site"]["pages_found"] == 4

    respx.calls.reset()
    await ws.ok("POST", f"/knowledge-sources/{site['id']}/recrawl")
    await run(maker, ws, site, version=2)
    assert not {"/blog", "/blog/first"} & set(requested())

    # Taking the path off the list lets the next crawl read it again.
    patched = await ws.ok("PATCH", f"/knowledge-sources/{site['id']}", json={"excluded_paths": []})
    assert patched["site"]["excluded_paths"] == []
    await ws.ok("POST", f"/knowledge-sources/{site['id']}/recrawl")
    await run(maker, ws, site, version=3)
    assert {"/blog", "/blog/first"} <= set(requested())
    assert (await pages(ws, site))["/blog/first"]["status"] == "done"


async def test_excluded_paths_are_checked(ws: Ws) -> None:
    site = await new_site(ws)
    for path in ("/", "https://maple.example/", "   "):
        response = await ws.call(
            "POST", f"/knowledge-sources/{site['id']}/excluded-paths", json={"path": path}
        )
        assert response.status_code == 422, path
    too_many = [f"/p{n}" for n in range(51)]
    response = await ws.call(
        "PATCH", f"/knowledge-sources/{site['id']}", json={"excluded_paths": too_many}
    )
    assert response.status_code == 422
    response = await ws.call(
        "PATCH", f"/knowledge-sources/{site['id']}", json={"excluded_paths": ["/"]}
    )
    assert response.status_code == 422
    assert [e["field"] for e in response.json()["errors"]] == ["excluded_paths"]


# ---------------------------------------------------------------- the scheduled re-crawl


@respx.mock
async def test_a_weekly_site_is_crawled_again_when_it_is_due(
    ws: Ws, engine: AsyncEngine, maker: async_sessionmaker[AsyncSession]
) -> None:
    maple_site()
    weekly = await new_site(ws)
    off = await new_site(ws, url="https://www.maple.example/", recrawl="off")
    assert off["site"]["recrawl"] == "off"
    await run(maker, ws, weekly)
    await run(maker, ws, off)
    done = (await get_site(ws, weekly))["site"]
    assert done["next_crawl_at"] is not None
    assert (await get_site(ws, off))["site"]["next_crawl_at"] is None  # never

    assert await knowledge_tasks.start_due_crawls(maker) == []  # not due yet

    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE site_crawls SET next_crawl_at = now() - interval '1 minute'")
        )
    started = await knowledge_tasks.start_due_crawls(maker)
    assert started == [(uuid.UUID(ws.wid), uuid.UUID(weekly["id"]), 2)]  # not the "off" one
    after = await get_site(ws, weekly)
    assert (after["version"], after["site"]["status"], after["status"]) == (2, "queued", "pending")
    locks = [job["queueing_lock"] for job in await jobs("crawl_site")]
    assert f"crawl:{weekly['id']}:2" in locks
    assert f"crawl:{off['id']}:2" not in locks

    assert await knowledge_tasks.start_due_crawls(maker) == []  # queued: left alone
    assert await run(maker, ws, weekly, version=2) == "done"
    assert (await get_site(ws, weekly))["site"]["next_crawl_at"] is not None


@respx.mock
async def test_a_crawl_whose_job_was_lost_is_queued_again_under_its_own_version(
    ws: Ws, engine: AsyncEngine, maker: async_sessionmaker[AsyncSession]
) -> None:
    maple_site()
    site = await new_site(ws)
    assert await knowledge_tasks.start_due_crawls(maker) == []  # queued a moment ago
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE site_crawls SET updated_at = now() - interval '2 hours'"))
    started = await knowledge_tasks.start_due_crawls(maker)
    assert started == [(uuid.UUID(ws.wid), uuid.UUID(site["id"]), 1)]
    assert (await get_site(ws, site))["version"] == 1
    assert await knowledge_tasks.start_due_crawls(maker) == []  # given another 30 minutes
    assert await run(maker, ws, site) == "done"


async def test_the_re_crawl_setting_can_be_changed(ws: Ws) -> None:
    site = await new_site(ws)
    assert site["site"]["recrawl"] == "weekly"
    off = await ws.ok("PATCH", f"/knowledge-sources/{site['id']}", json={"recrawl": "off"})
    assert (off["site"]["recrawl"], off["site"]["next_crawl_at"], off["version"]) == (
        "off",
        None,
        1,
    )
    renamed = await ws.ok("PATCH", f"/knowledge-sources/{site['id']}", json={"title": "Our shop"})
    assert (renamed["title"], renamed["version"]) == ("Our shop", 1)  # not a new crawl
    assert len(await jobs("crawl_site")) == 1
    bad = await ws.call("PATCH", f"/knowledge-sources/{site['id']}", json={"recrawl": "daily"})
    assert bad.status_code == 422


# ---------------------------------------------------------------- SSRF (SEC-09)


async def test_a_literal_private_start_address_is_refused_when_adding(ws: Ws) -> None:
    for url in (
        "http://169.254.169.254/",
        "http://127.0.0.1:8000/",
        "http://[::1]/",
        "ftp://maple.example/",
    ):
        response = await ws.call("POST", "/knowledge-sources", json={"type": "site", "url": url})
        assert response.status_code == 422, url
        assert [e["field"] for e in response.json()["errors"]] == ["url"]
    assert await jobs("crawl_site") == []


@respx.mock
async def test_a_start_address_that_resolves_to_a_private_network_fails_without_a_request(
    ws: Ws, maker: async_sessionmaker[AsyncSession]
) -> None:
    site = await new_site(ws, url="https://intranet.maple.example/")
    assert await run(maker, ws, site) == "failed"
    after = await get_site(ws, site)
    assert (after["status"], after["error"]) == ("failed", ssrf.BLOCKED)
    assert not respx.calls


@respx.mock
async def test_nothing_private_is_requested_from_links_sitemaps_or_redirects(
    ws: Ws, maker: async_sessionmaker[AsyncSession], dns: dict[str, list[str]]
) -> None:
    dns["cloud.example"] = ["169.254.169.254"]
    routes = maple_site(
        robots="User-agent: *\nDisallow: /private\n"
        "Sitemap: http://169.254.169.254/sitemap.xml\n"
        "Sitemap: https://intranet.maple.example/sitemap.xml\n",
        sitemap=(
            "https://maple.example/shipping",
            "http://169.254.169.254/latest/meta-data/",
            "https://intranet.maple.example/prices",
            "https://cloud.example/x",
        ),
    )
    routes["/"].respond(
        200,
        headers={"content-type": "text/html"},
        content=article(
            "Maple Bakery",
            "Fresh cakes and bread",
            (
                "http://169.254.169.254/latest/meta-data/",
                "http://127.0.0.1:8000/admin",
                "https://intranet.maple.example/prices",
                "/returns",
                "/moved",
            ),
        ),
    )
    respx.get(f"https://{PUBLIC_IP}/moved").respond(
        302, headers={"location": "http://169.254.169.254/latest/meta-data/"}
    )
    site = await new_site(ws)

    assert await run(maker, ws, site) == "done"

    assert {call.request.url.host for call in respx.calls} == {PUBLIC_IP}
    listing = await pages(ws, site)
    assert listing["/moved"]["status"] == "failed"  # the redirect target was refused
    assert listing["/returns"]["status"] == "done"
    assert set(listing) == {"/", "/shipping", "/returns", "/moved", "/about"}


@respx.mock
async def test_a_page_that_redirects_to_a_private_address_fails_and_the_crawl_goes_on(
    ws: Ws, maker: async_sessionmaker[AsyncSession]
) -> None:
    routes = maple_site()
    routes["/returns"].respond(302, headers={"location": "http://169.254.169.254/x"})
    site = await new_site(ws)
    assert await run(maker, ws, site) == "done"
    failed = (await pages(ws, site))["/returns"]
    assert failed["status"] == "failed"
    assert failed["error"] == "The page redirects to an address that can't be used."
    assert {call.request.url.host for call in respx.calls} == {PUBLIC_IP}


# ---------------------------------------------------------------- the API's rules


@respx.mock
async def test_pages_are_a_site_s_and_cannot_be_reached_as_sources(
    ws: Ws, engine: AsyncEngine, maker: async_sessionmaker[AsyncSession]
) -> None:
    maple_site()
    site = await new_site(ws)
    await run(maker, ws, site)
    [child, *_] = await rows(engine, "SELECT id FROM knowledge_sources WHERE type = 'page'")
    child_id = str(child["id"])
    for method, body in (("GET", None), ("PATCH", {"title": "x"}), ("DELETE", None)):
        response = await ws.call(method, f"/knowledge-sources/{child_id}", json=body)
        assert response.status_code == 404, method
    assert (await ws.call("GET", f"/knowledge-sources/{child_id}/pages")).status_code == 404
    assert (await ws.call("POST", f"/knowledge-sources/{child_id}/recrawl")).status_code == 404

    faq = await ws.ok(
        "POST", "/knowledge-sources", 201, json={"type": "faq", "question": "Q?", "body": "A."}
    )
    for method, path in (
        ("GET", "/pages"),
        ("POST", "/recrawl"),
        ("POST", "/excluded-paths"),
        ("DELETE", f"/pages/{uuid.uuid4()}"),
    ):
        response = await ws.call(
            method,
            f"/knowledge-sources/{faq['id']}{path}",
            json={"path": "/a"} if method == "POST" else None,
        )
        assert response.status_code == 404, path


async def test_a_site_takes_only_its_own_fields(ws: Ws) -> None:
    created = await ws.call(
        "POST", "/knowledge-sources", json={"type": "site", "url": START, "body": "text"}
    )
    assert created.status_code == 422
    assert [e["field"] for e in created.json()["errors"]] == ["body"]
    site = await new_site(ws)
    for patch in ({"url": "https://other.example/"}, {"body": "x"}, {"question": "x"}):
        response = await ws.call("PATCH", f"/knowledge-sources/{site['id']}", json=patch)
        assert response.status_code == 422, patch
    page_type = await ws.call("POST", "/knowledge-sources", json={"type": "page", "url": START})
    assert page_type.status_code == 422  # a page is made by a crawl
    faq = await ws.call(
        "POST",
        "/knowledge-sources",
        json={"type": "faq", "question": "Q?", "body": "A.", "recrawl": "off"},
    )
    assert faq.status_code == 422


async def test_a_site_is_not_added_at_the_knowledge_limit(ws: Ws, engine: AsyncEngine) -> None:
    await make_source(engine, workspace_id=ws.wid, chunks=False, char_count=200_000)
    response = await ws.call("POST", "/knowledge-sources", json={"type": "site", "url": START})
    assert response.status_code == 402
    assert response.json()["code"] == "quota_exceeded"


@respx.mock
async def test_deleting_a_site_deletes_its_pages_and_their_knowledge(
    ws: Ws,
    engine: AsyncEngine,
    maker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
) -> None:
    maple_site()
    site = await new_site(ws)
    await run(maker, ws, site)
    await ingest_pending(maker, http, ws, engine)
    assert (await ws.call("DELETE", f"/knowledge-sources/{site['id']}")).status_code == 204
    for table in ("knowledge_sources", "knowledge_chunks", "site_pages", "site_crawls"):
        assert await rows(engine, f"SELECT id FROM {table}") == [], table  # noqa: S608
    assert (await ws.ok("GET", "/knowledge-sources"))["items"] == []


@respx.mock
async def test_a_page_over_the_knowledge_limit_fails_on_its_own(
    ws: Ws,
    engine: AsyncEngine,
    maker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
) -> None:
    maple_site()
    site = await new_site(ws)
    await run(maker, ws, site)
    await make_source(engine, workspace_id=ws.wid, chunks=False, char_count=199_990)
    pending = await rows(
        engine, "SELECT id, version FROM knowledge_sources WHERE type='page' LIMIT 1"
    )
    outcome = await ingest.ingest_source(
        maker,
        http,
        workspace_id=uuid.UUID(ws.wid),
        source_id=pending[0]["id"],
        version=pending[0]["version"],
        will_retry=False,
    )
    assert outcome == "failed"
    listing = await pages(ws, site)
    assert [item["status"] for item in listing.values()].count("failed") == 1
    failed = next(item for item in listing.values() if item["status"] == "failed")
    assert "more than" in failed["error"]


async def test_site_routes_are_for_admins(ws: Ws, engine: AsyncEngine) -> None:
    site = await new_site(ws)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspace_members SET role = 'agent' WHERE workspace_id = :w"),
            {"w": ws.wid},
        )
    page = uuid.uuid4()
    for method, path in (
        ("GET", f"/knowledge-sources/{site['id']}/pages"),
        ("DELETE", f"/knowledge-sources/{site['id']}/pages/{page}"),
        ("POST", f"/knowledge-sources/{site['id']}/excluded-paths"),
        ("POST", f"/knowledge-sources/{site['id']}/recrawl"),
    ):
        response = await ws.call(method, path, json={"path": "/a"} if method == "POST" else None)
        assert response.status_code == 403, f"{method} {path}"


async def test_another_workspace_s_site_is_not_found(
    ws: Ws,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
) -> None:
    other = await workspace(client, clerk, email="other@example.com")
    site_id, page_id = await make_site(engine, workspace_id=other.wid)
    mine = await new_site(ws)

    for method, path, body in (
        ("GET", f"/knowledge-sources/{site_id}", None),
        ("GET", f"/knowledge-sources/{site_id}/pages", None),
        ("DELETE", f"/knowledge-sources/{site_id}/pages/{page_id}", None),
        ("POST", f"/knowledge-sources/{site_id}/excluded-paths", {"path": "/blog"}),
        ("POST", f"/knowledge-sources/{site_id}/recrawl", None),
        ("PATCH", f"/knowledge-sources/{site_id}", {"recrawl": "off"}),
        ("DELETE", f"/knowledge-sources/{site_id}/pages/{uuid.uuid4()}", None),
        # My site with the other workspace's page.
        ("DELETE", f"/knowledge-sources/{mine['id']}/pages/{page_id}", None),
    ):
        response = await ws.call(method, path, json=body)
        assert response.status_code == 404, f"{method} {path}"
        assert response.json()["code"] == "not_found"

    # Untouched: still there, with its page.
    assert [
        r["id"] for r in await rows(engine, "SELECT id FROM site_pages WHERE id = :p", p=page_id)
    ] == [page_id]
    assert [item["id"] for item in (await ws.ok("GET", "/knowledge-sources"))["items"]] == [
        mine["id"]
    ]
