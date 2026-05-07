"""BrowseComp judge: LLM-based answer correctness evaluation.

Sends the question, final assistant response, and gold answer to an LLM that
judges whether the final response matches the correct answer. Falls back to
exact-match when no LLM config is available.

Reference: external/deepagent-test/judge.py
"""

from __future__ import annotations

import logging
import re

from ..framework.config import DistillConfig
from ..framework.judge import BaseJudge, JudgeResult
from ..framework.llm import generate_judge
from ..framework.trajectory import Trajectory, final_assistant_text, strip_thinking

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """\
Judge whether the following [response] to [question] is correct or not based on the precise and unambiguous [correct_answer] below.

[question]: {question}

[response]: {response}

Your judgement must be in the format and criteria specified below:
extracted_final_answer: The final exact answer extracted from the [response]. Put the extracted answer as 'None' if there is no exact, final answer to extract from the response.

[correct_answer]: {answer}

reasoning: Explain why the extracted_final_answer is correct or incorrect based on [correct_answer], focusing only on if there are meaningful differences between [correct_answer] and the extracted_final_answer. Do not comment on any background to the problem, do not attempt to solve the problem, do not argue for any answer different than [correct_answer], focus only on whether the answers match.

correct: Answer 'yes' if extracted_final_answer matches the [correct_answer] given above, or is within a small margin of error for numerical problems. Answer 'no' otherwise, i.e. if there if there is any inconsistency, ambiguity, non-equivalency, or if the extracted answer is incorrect."""


def parse_llm_judgment(llm_response: str) -> bool:
    if not llm_response:
        return False

    # Judge may itself be a thinking model; the chain-of-thought often quotes
    # the rubric ("...output `correct: yes or no`...") and the leading match
    # would override the real verdict. Drop everything before the final
    # </think> so we only parse the actual answer.
    answer = strip_thinking(llm_response)
    if not answer:
        return False

    text = answer.lower().replace("*", "").replace("\n", "")

    matches = re.findall(r"correct:\s*(yes|no)", text)
    if matches:
        return matches[-1] == "yes"

    for pattern in [
        r"correct[:\s]+yes", r"correct[:\s]+no",
        r"answer[:\s]+yes", r"answer[:\s]+no",
        r"judgment[:\s]*:?[:\s]*yes", r"judgment[:\s]*:?[:\s]*no",
    ]:
        found = re.findall(pattern, text)
        if found:
            return "yes" in found[-1]

    for line in reversed(answer.lower().split("\n")):
        if "correct" in line:
            if "yes" in line and "no" not in line:
                return True
            if "no" in line and "yes" not in line:
                return False
    return False


class BrowseCompJudge(BaseJudge):
    def __init__(self) -> None:
        self._config: DistillConfig | None = None

    def load(self, config: DistillConfig) -> None:
        self._config = config

    def judge(self, example: dict, trajectory: Trajectory) -> JudgeResult:
        steps = trajectory.steps
        if steps and steps[-1].role in ("user", "tool"):
            response = ""
        else:
            response = final_assistant_text(trajectory)
        gold = example["questions"][0]["answer"]
        question = example["questions"][0]["question"]

        predicted = response.strip()

        if self._config is not None:
            return self._llm_judge(question, response, gold, predicted)
        return self._exact_match(gold, predicted)

    def _llm_judge(self, question: str, response: str,
                   gold: str, predicted: str) -> JudgeResult:
        prompt = JUDGE_PROMPT.format(
            question=question,
            response=response,
            answer=gold,
        )
        try:
            llm_response = generate_judge(prompt, self._config) or ""
            passed = parse_llm_judgment(llm_response)
        except Exception as e:
            logger.error("LLM judge failed, falling back to exact match: %s", e)
            return self._exact_match(gold, predicted)

        return JudgeResult(
            passed=passed,
            details=[{
                "type": "llm_judge",
                "passed": passed,
                "predicted": predicted,
                "gold": gold,
                "llm_judgment": llm_response,
            }],
            metadata={"judge_type": "llm"},
        )

    @staticmethod
    def _exact_match(gold: str, predicted: str) -> JudgeResult:
        norm = lambda t: " ".join(t.strip().lower().split())
        passed = norm(predicted) == norm(gold) if predicted else False
        return JudgeResult(
            passed=passed,
            details=[{
                "type": "exact_match",
                "passed": passed,
                "predicted": predicted,
                "gold": gold,
            }],
            metadata={"judge_type": "exact_match"},
        )
