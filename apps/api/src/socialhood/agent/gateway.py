"""The action gateway (R2; FR-AGT-08, FR-AGT-10, TR-AGT-04; agent-architecture.html §4, §8).

Every write is decided here, in code, from the tool's fixed tier and capability, the principal's
role, the workspace's agent policy and the concrete arguments (for example the number of
recipients). The model's output is never an input to the decision. In order:

1. the tool has shipped (``release``) — else refuse ``not_available``;
2. the principal's role allows it (``min_role``) — else refuse ``forbidden``;
3. the policy's switch for the tool's capability is on — else refuse ``agent_permission_off``;
4. the account supports it (TR-PL-11, ``platform_capability``) — else refuse
   ``capability_unavailable``;
5. limits: bulk size (arguments can raise the tier; more than bulk_max is refused), writes per
   hour and per day — else refuse ``limit_reached``;
6. mode and tier give execute or approval:

    tier \\ mode   read_only  copilot   supervised  autonomous (R3)
    read          run        run       run         run
    draft         run        run       run         run
    low           refuse     approval  run         run
    high          refuse     approval  approval    run within caps
    destructive   refuse     approval  approval    approval

A refusal is stored on the step as ``refuse:{reason}`` and is a step result, never an HTTP error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from socialhood.agent.registry import Principal, ToolSpec
from socialhood.models.agent import AgentPolicy, GatewayDecision

RefusalReason = Literal[
    "not_available",
    "forbidden",
    "agent_permission_off",
    "capability_unavailable",
    "limit_reached",
    "read_only",  # the mode refuses every write tier
]


@dataclass(frozen=True)
class Decision:
    outcome: GatewayDecision
    reason: RefusalReason | None = None  # refusals only

    @property
    def stored(self) -> str:
        """agent_steps.decision: ``execute``, ``approval`` or ``refuse:{reason}``."""
        if self.outcome == GatewayDecision.REFUSE:
            return f"refuse:{self.reason}"
        return self.outcome.value


def decide(
    tool: ToolSpec[Any, Any], args: BaseModel, principal: Principal, policy: AgentPolicy
) -> Decision:
    """Execute, approval or refuse for one write (R2)."""
    raise NotImplementedError("R2")
