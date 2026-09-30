"""TA.1: the Ask Social Hood API (§2.15 …/agent/*; FR-AGT-01, FR-AGT-03, FR-AGT-07, FR-AGT-10,
TR-AGT-08). Asking stores a queued run and queues run_agent; a member sees and cancels their own
runs, owners and admins every run; threads are personal; the policy is read_only in R1. Another
workspace's ids are covered by the tenancy suite (tests/tenancy); here, another member's.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.agent import orchestrator
from socialhood.agent.planner import use_model, use_tools
from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.models.agent import DEFAULT_LIMITS, DEFAULT_PERMISSIONS
from socialhood.platforms.deps import deps_from
from socialhood.settings import Settings
from tests.support.agent import make_agent_run
from tests.support.agent_runtime import COMMENT, Calls, Script, call, say, scripted_tools
from tests.support.analysis import use_credits
from tests.support.api import Clerk, sign_in
from tests.support.ingest import jobs, stream


@dataclass
class Team:
    client: httpx.AsyncClient
    clerk: Clerk
    engine: AsyncEngine
    redis: Redis
    wid: str
    owner: str  # clerk ids
    owner_id: str  # user ids
    member: str
    member_id: str

    def url(self, path: str) -> str:
        return f"/v1/w/{self.wid}{path}"

    async def get(self, path: str, who: str | None = None, **params: Any) -> httpx.Response:
        headers = self.clerk.headers(who or self.owner)
        return await self.client.get(self.url(path), headers=headers, params=params)

    async def post(
        self, path: str, body: dict[str, Any] | None = None, who: str | None = None
    ) -> httpx.Response:
        headers = self.clerk.headers(who or self.owner)
        return await self.client.post(self.url(path), headers=headers, json=body)

    async def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        async with self.engine.connect() as conn:
            return [dict(r._mapping) for r in await conn.execute(text(sql), params)]

    async def execute(self, sql: str, **params: Any) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text(sql), params)

    async def run(self, **values: Any) -> uuid.UUID:
        """A finished run of the owner's (unless ``requested_by_user_id`` says otherwise)."""
        values.setdefault("requested_by_user_id", self.owner_id)
        return (await make_agent_run(self.engine, workspace_id=self.wid, **values)).id

    async def join(self, clerk_id: str, role: str) -> str:
        """A signed-in user (with a workspace of their own) joins this one with ``role``."""
        _, me = await sign_in(
            self.client, self.clerk, clerk_id=clerk_id, email=f"{clerk_id}@example.com"
        )
        await self.execute(
            "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (:w, :u, :r)",
            w=self.wid,
            u=me["id"],
            r=role,
        )
        return str(me["id"])


@pytest.fixture
async def team(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, redis: Redis) -> Team:
    owner, me = await sign_in(client, clerk, email="owner@example.com", first_name="Olivia")
    wid = me["workspaces"][0]["id"]
    member_clerk = clerk.add(email="member@example.com", first_name="Ben", last_name="Das")
    member_me = (await client.get("/v1/me", headers=clerk.headers(member_clerk))).json()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO workspace_members (workspace_id, user_id, role)"
                " VALUES (:w, :u, 'agent')"
            ),
            {"w": wid, "u": member_me["id"]},
        )
    return Team(client, clerk, engine, redis, wid, owner, me["id"], member_clerk, member_me["id"])


# ---------------------------------------------------------------- asking (FR-AGT-01)


async def test_asking_stores_a_queued_run_and_queues_the_job(team: Team, queue: None) -> None:
    response = await team.post("/agent/runs", {"request": "  How did my latest post do?  "})
    assert response.status_code == 202, response.text
    run = response.json()
    assert run["status"] == "queued"
    assert run["thread_id"] == run["id"]  # a new thread's id is its first run's id
    assert (run["request"], run["source"], run["mode"]) == (
        "How did my latest post do?",
        "ask",
        "read_only",
    )
    assert run["requested_by"] == {"id": team.owner_id, "name": "Olivia Nair"}
    assert (run["answer"], run["answer_refs"], run["action_cards"], run["credits"]) == (
        None,
        [],
        [],
        0,
    )
    [stored] = await team.rows("SELECT * FROM agent_runs WHERE id = :id", id=run["id"])
    assert (stored["status"], stored["requested_by_user_id"]) == (
        "queued",
        uuid.UUID(team.owner_id),
    )

    [job] = await jobs("run_agent")
    assert (job["queue_name"], job["queueing_lock"]) == ("interactive", f"agent:{run['id']}")
    assert job["args"] == {"run_id": run["id"], "workspace_id": team.wid}

    events = [(k, p) for k, p in await stream(team.redis, team.wid) if k.startswith("agent.")]
    assert events == [
        (
            "agent.run.updated",
            {
                "run": {
                    "id": run["id"],
                    "thread_id": run["id"],
                    "requested_by_user_id": team.owner_id,
                    "status": "queued",
                    "step_count": 0,
                    "error": None,
                }
            },
        )
    ]

    follow_up = await team.post(
        "/agent/runs", {"request": "And the one before?", "thread_id": run["id"]}
    )
    assert follow_up.status_code == 202
    assert follow_up.json()["thread_id"] == run["id"]


async def test_only_your_own_thread_can_be_continued(team: Team) -> None:
    theirs = await team.run(requested_by_user_id=team.member_id)
    response = await team.post(
        "/agent/runs", {"request": "What did Ben ask?", "thread_id": str(theirs)}
    )
    assert response.status_code == 404
    unknown = await team.post("/agent/runs", {"request": "Hello?", "thread_id": str(uuid.uuid4())})
    assert unknown.status_code == 404
    assert len(await team.rows("SELECT id FROM agent_runs")) == 1


async def test_without_credits_asking_is_402_and_stores_nothing(team: Team) -> None:
    await use_credits(team.engine, uuid.UUID(team.wid), 200, now=datetime.now(UTC))
    response = await team.post("/agent/runs", {"request": "How did my latest post do?"})
    assert response.status_code == 402
    problem = response.json()
    assert (problem["code"], problem["entitlement"], problem["limit"]) == (
        "quota_exceeded",
        "ai_credits_monthly",
        200,
    )
    assert await team.rows("SELECT id FROM agent_runs") == []


@pytest.mark.parametrize(
    "body",
    [
        {"request": ""},
        {"request": "   "},
        {"request": "x" * 2001},
        {"request": "Hi", "mode": "autonomous"},
        {},
    ],
)
async def test_a_request_must_be_1_to_2000_characters(team: Team, body: dict[str, Any]) -> None:
    response = await team.post("/agent/runs", body)
    assert response.status_code == 422


# ---------------------------------------------------------------- history (FR-AGT-07)


async def test_members_see_their_own_runs_and_admins_see_every_run(team: Team) -> None:
    base = datetime.now(UTC) - timedelta(hours=1)
    mine = [
        await team.run(created_at=base + timedelta(minutes=n), request=f"Owner question {n}")
        for n in range(3)
    ]
    theirs = await team.run(
        requested_by_user_id=team.member_id, created_at=base - timedelta(minutes=1)
    )

    owner_view = (await team.get("/agent/runs")).json()
    assert [r["id"] for r in owner_view["items"]] == [str(i) for i in [*reversed(mine), theirs]]
    member_view = (await team.get("/agent/runs", who=team.member)).json()
    assert [r["id"] for r in member_view["items"]] == [str(theirs)]
    assert member_view["items"][0]["requested_by"] == {"id": team.member_id, "name": "Ben Das"}

    await team.join("user_admin", "admin")
    admin_view = (await team.get("/agent/runs", who="user_admin")).json()
    assert len(admin_view["items"]) == 4

    first = (await team.get("/agent/runs", limit=2)).json()
    assert [r["id"] for r in first["items"]] == [str(mine[2]), str(mine[1])]
    rest = (await team.get("/agent/runs", limit=2, cursor=first["next_cursor"])).json()
    assert [r["id"] for r in rest["items"]] == [str(mine[0]), str(theirs)]
    assert rest["next_cursor"] is None
    bad = await team.get("/agent/runs", cursor="not-a-cursor")
    assert bad.status_code == 422


async def test_a_thread_filter_lists_only_your_own_runs(team: Team) -> None:
    first = await team.run()
    follow_up = await team.run(thread_id=first, created_at=datetime.now(UTC) + timedelta(seconds=5))
    theirs = await team.run(requested_by_user_id=team.member_id)
    assert [
        r["id"] for r in (await team.get("/agent/runs", thread_id=str(first))).json()["items"]
    ] == [
        str(follow_up),
        str(first),
    ]
    # An owner sees every run in the history, but another member's thread lists nothing.
    listed = (await team.get("/agent/runs", thread_id=str(theirs))).json()
    assert listed["items"] == []


async def test_the_history_filters_by_status_and_searches_requests(team: Team) -> None:
    """Settings → Agent's chips and search (C-066): any case, LIKE wildcards taken literally."""
    base = datetime.now(UTC) - timedelta(hours=1)
    answered = await team.run(request="How did my latest post do?", created_at=base)
    partly = await team.run(
        request="Top posts, 100% honest", status="partial", created_at=base + timedelta(minutes=1)
    )
    failed = await team.run(
        request="Which POSTS got negative comments?",
        status="failed",
        answer=None,
        created_at=base + timedelta(minutes=2),
    )
    theirs = await team.run(
        requested_by_user_id=team.member_id,
        request="Posts this week",
        status="failed",
        answer=None,
        created_at=base + timedelta(minutes=3),
    )

    async def ids(who: str | None = None, **params: Any) -> list[str]:
        response = await team.get("/agent/runs", who=who, **params)
        assert response.status_code == 200, response.text
        return [r["id"] for r in response.json()["items"]]

    assert await ids(status=["succeeded", "partial"]) == [str(partly), str(answered)]
    assert await ids(status="failed") == [str(theirs), str(failed)]
    assert await ids(q="posts") == [str(theirs), str(failed), str(partly)]
    assert await ids(q="%") == [str(partly)]
    assert await ids(q="  negative ", status="failed") == [str(failed)]
    assert await ids(status="awaiting_approval") == []
    # A member's filters still reach only their own runs.
    assert await ids(who=team.member, status="failed") == [str(theirs)]
    assert (await team.get("/agent/runs", status="done")).status_code == 422

    page = (await team.get("/agent/runs", q="posts", limit=2)).json()
    rest = await ids(q="posts", limit=2, cursor=page["next_cursor"])
    assert [r["id"] for r in page["items"]] + rest == [str(theirs), str(failed), str(partly)]


async def test_a_run_opens_with_its_steps_for_its_member_and_admins(team: Team) -> None:
    theirs = await team.run(requested_by_user_id=team.member_id)
    own = await team.get(f"/agent/runs/{theirs}", who=team.member)
    assert own.status_code == 200
    detail = own.json()
    assert (detail["model"], detail["prompt_version"], detail["credits"]) == (
        "fake-model",
        "agent.v1",
        2,
    )
    assert [(s["ordinal"], s["kind"], s["status"]) for s in detail["steps"]] == [
        (0, "tool", "succeeded"),
        (1, "report", "succeeded"),
    ]
    assert detail["steps"][0]["summary"] == "Found your latest post, a reel published 26 hours ago"
    assert detail["steps"][0]["label"]  # the tool in plain words
    assert detail["steps"][1]["label"] == "Writing the answer"
    assert "input_tokens" not in detail  # tokens stay in the table (SEC-02)

    assert (await team.get(f"/agent/runs/{theirs}")).status_code == 200  # the owner
    mine = await team.run()
    hidden = await team.get(f"/agent/runs/{mine}", who=team.member)
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "not_found"
    assert (await team.get(f"/agent/runs/{uuid.uuid4()}")).status_code == 404


# ---------------------------------------------------------------- cancel (§9)


async def test_cancel_stops_an_unfinished_run(team: Team) -> None:
    run_id = await team.run(
        requested_by_user_id=team.member_id, status="running", answer=None, completed_at=None
    )
    response = await team.post(f"/agent/runs/{run_id}/cancel", who=team.member)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["completed_at"] is not None
    kinds = [
        (k, p["run"]["status"], p["run"]["step_count"])
        for k, p in await stream(team.redis, team.wid)
        if k.startswith("agent.")
    ]
    assert kinds == [
        ("agent.run.updated", "cancelled", 2),
        ("agent.completed", "cancelled", 2),
    ]
    again = await team.post(f"/agent/runs/{run_id}/cancel", who=team.member)
    assert again.json()["status"] == "cancelled"
    assert len([k for k, _ in await stream(team.redis, team.wid)]) == 2  # nothing new


async def test_a_finished_run_is_returned_as_it_is(team: Team) -> None:
    run_id = await team.run()
    response = await team.post(f"/agent/runs/{run_id}/cancel")
    assert response.json()["status"] == "succeeded"


async def test_only_the_asker_or_an_admin_can_cancel(team: Team) -> None:
    mine = await team.run(status="queued", answer=None, completed_at=None)
    refused = await team.post(f"/agent/runs/{mine}/cancel", who=team.member)
    assert refused.status_code == 404
    assert (await team.rows("SELECT status FROM agent_runs WHERE id = :id", id=mine))[0][
        "status"
    ] == "queued"
    theirs = await team.run(
        requested_by_user_id=team.member_id, status="queued", answer=None, completed_at=None
    )
    assert (await team.post(f"/agent/runs/{theirs}/cancel")).json()["status"] == "cancelled"


# ---------------------------------------------------------------- threads


async def test_threads_are_the_callers_own_most_recent_first(team: Team) -> None:
    base = datetime.now(UTC) - timedelta(hours=2)
    long_question = "How did " + "my latest reel " * 10 + "do?"
    old = await team.run(request=long_question, created_at=base)
    await team.run(
        thread_id=old,
        request="And comments?",
        status="failed",
        created_at=base + timedelta(hours=1),
    )
    recent = await team.run(request="What's scheduled?", created_at=base + timedelta(minutes=30))
    await team.run(requested_by_user_id=team.member_id)

    listed = (await team.get("/agent/threads")).json()
    assert [t["id"] for t in listed["items"]] == [str(old), str(recent)]
    first = listed["items"][0]
    assert len(first["title"]) == 80
    assert first["title"].endswith("…")
    assert first["title"].startswith("How did my latest reel")
    assert (first["run_count"], first["last_status"]) == (2, "failed")
    assert first["created_at"] < first["last_run_at"]

    page = (await team.get("/agent/threads", limit=1)).json()
    assert [t["id"] for t in page["items"]] == [str(old)]
    rest = (await team.get("/agent/threads", limit=1, cursor=page["next_cursor"])).json()
    assert [t["id"] for t in rest["items"]] == [str(recent)]
    assert rest["next_cursor"] is None

    member_threads = (await team.get("/agent/threads", who=team.member)).json()
    assert len(member_threads["items"]) == 1


async def test_lists_never_show_another_workspaces_runs(team: Team) -> None:
    _, other = await sign_in(team.client, team.clerk, email="other@example.com")
    await make_agent_run(
        team.engine, workspace_id=other["workspaces"][0]["id"], requested_by_user_id=team.owner_id
    )
    assert (await team.get("/agent/runs")).json()["items"] == []
    assert (await team.get("/agent/threads")).json()["items"] == []


# ---------------------------------------------------------------- policy (FR-AGT-10)


async def test_the_policy_is_read_only_with_everything_off(team: Team) -> None:
    response = await team.get("/agent/policy")
    assert response.status_code == 200
    policy = response.json()
    assert policy["mode"] == "read_only"
    assert policy["permissions"] == DEFAULT_PERMISSIONS
    assert policy["limits"] == DEFAULT_LIMITS
    assert policy["updated_by"] is None
    assert (await team.get("/agent/policy", who=team.member)).status_code == 403

    await team.execute("DELETE FROM agent_policies WHERE workspace_id = :w", w=team.wid)
    assert (await team.get("/agent/policy")).json()["mode"] == "read_only"
    assert (
        len(await team.rows("SELECT id FROM agent_policies WHERE workspace_id = :w", w=team.wid))
        == 1
    )


# ---------------------------------------------------------------- the whole way


async def test_a_question_is_answered_through_the_api(
    team: Team, api_settings: Settings, queue: None
) -> None:
    asked = (await team.post("/agent/runs", {"request": "Reply thanks to the top comment"})).json()
    calls = Calls()
    script = Script(
        call("prepare_comment_reply", comment_id=str(COMMENT), text="Thank you!"),
        say("I prepared a reply to the comment [1]. Send it from the post."),
    )
    wid = uuid.UUID(team.wid)
    async with httpx.AsyncClient() as http:
        with use_model(script.model()), use_tools(scripted_tools(calls)), workspace_scope(wid):
            await orchestrator.run(
                make_sessionmaker(team.engine),
                team.redis,
                deps_from(http, api_settings),
                run_id=uuid.UUID(asked["id"]),
                workspace_id=wid,
            )
        with use_tools(scripted_tools(calls)):
            detail = (await team.get(f"/agent/runs/{asked['id']}")).json()
    assert detail["status"] == "succeeded"
    assert detail["answer"] == "I prepared a reply to the comment [1]. Send it from the post."
    assert [r["kind"] for r in detail["answer_refs"]] == ["comment"]
    assert [c["kind"] for c in detail["action_cards"]] == ["reply_to_comment"]
    assert detail["action_cards"][0]["prefill"]["text"] == "Thank you!"
    assert [(s["label"], s["tier"]) for s in detail["steps"]] == [
        ("Preparing a reply", "draft"),
        ("Writing the answer", None),
    ]
    assert detail["credits"] == 2
    listed = (await team.get("/agent/runs")).json()["items"]
    assert listed[0]["action_cards"] == detail["action_cards"]
