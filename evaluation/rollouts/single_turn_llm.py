"""Single-turn LLM rollout: prompt in, one assistant reply out.

Used by math-style / instruction-following benchmarks. The prompt comes from
a configurable field on the example (`prompt_field`, defaults to "instruction");
an optional `system_prompt` can be prepended.

The resulting `Trajectory` is length 2 (user + assistant), plus an optional
system step.
"""

from __future__ import annotations

from typing import Optional

from ..framework.config import DistillConfig
from ..framework.llm import agenerate
from ..framework.rollout import BaseRollout
from ..framework.trajectory import Step, Trajectory


class SingleTurnLLMRollout(BaseRollout):
    def __init__(self, prompt_field: str = "instruction",
                 system_prompt: str = "") -> None:
        self.prompt_field = prompt_field
        self.system_prompt = system_prompt
        self._config: Optional[DistillConfig] = None

    def setup(self, config: DistillConfig) -> None:
        self._config = config

    async def arollout(self, example: dict) -> Trajectory:
        assert self._config is not None, "setup() must be called before arollout()"
        prompt = example[self.prompt_field]
        response = await agenerate(prompt, self._config) or ""

        steps: list[Step] = []
        if self.system_prompt:
            steps.append(Step(role="system", content=self.system_prompt))
        steps.append(Step(role="user", content=prompt))
        steps.append(Step(role="assistant", content=response))

        metadata: dict = {"prompt_field": self.prompt_field,
                          "model": self._config.model}
        if not response.strip():
            metadata["empty_response"] = True
        return Trajectory(steps=steps, metadata=metadata)
