"""Generic distillation / test pipeline.

Single concrete class, never subclassed. Benchmarks plug in their components
(Rollout, Judge, Formatter) via the registry; the Pipeline handles:

  * loading examples,
  * generating `rollout_n` trajectories per example,
  * judging each one,
  * logging every rollout (pass or fail) to `full_data.jsonl`,
  * post-run: filter passed → apply keep_per_example → random-sample
    trajectories to target_count / target_num → format → write `data.jsonl`,
  * resume-on-restart via (example_hash, rollout_idx) dedup,
  * concurrency via an asyncio worker pool,
  * writing `report.json` with pass@1 / pass@N and optional benchmark-specific
    stats.

`target_count` and `target_num` cap the number of kept trajectories (applied
during post-processing, not during rollout). A kept trajectory may format into
multiple training rows in `data.jsonl`. Pass 0 for both to keep all passing
trajectories.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import threading
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from typing import Optional

from tqdm import tqdm

from .config import DistillConfig
from .formatter import BaseFormatter
from .judge import BaseJudge, JudgeResult
from .registry import BenchmarkSpec
from .rollout import BaseRollout
from .trajectory import Step, Trajectory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def example_hash(example: dict) -> str:
    raw = json.dumps(example, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _trajectory_to_dict(traj: Trajectory) -> dict:
    steps = [asdict(s) if is_dataclass(s) else dict(s) for s in traj.steps]
    out = {"steps": steps, "metadata": traj.metadata}
    if traj.prejudged is not None:
        out["prejudged"] = asdict(traj.prejudged)
    return out


def _judge_result_to_dict(jr: JudgeResult) -> dict:
    return asdict(jr)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class Pipeline:
    def __init__(self, config: DistillConfig, rollout: BaseRollout,
                 judge: BaseJudge, formatter: BaseFormatter,
                 spec: Optional[BenchmarkSpec] = None):
        self.config = config
        self.rollout = rollout
        self.judge = judge
        self.formatter = formatter
        self.spec = spec

        self._all_judge_results: list[JudgeResult] = []
        self._kept_per_example: dict[str, int] = defaultdict(int)
        self._rollouts_per_example: dict[str, int] = defaultdict(int)
        self._passes_per_example: dict[str, int] = defaultdict(int)

    # --- data loading --------------------------------------------------

    def _load_data(self) -> list[dict]:
        if self.config.data_path:
            path = self.config.data_path
        else:
            candidates = [
                os.path.join(self.config.submission_dir, "output", "generated_data.jsonl"),
                os.path.join(self.config.submission_dir, "generated_data.jsonl"),
            ]
            path = next((p for p in candidates if os.path.exists(p)), None)
            if path is None:
                raise FileNotFoundError(
                    f"generated_data.jsonl not found in {self.config.submission_dir}/output/ "
                    f"or {self.config.submission_dir}/"
                )

        examples: list[dict] = []
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    examples.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"[WARN] skipping malformed line {i} in {path}")
        if not examples:
            raise ValueError(f"no valid examples found in {path}")
        # Apply start/end slice before shuffle
        total = len(examples)
        s, e = self.config.start, self.config.end
        if s or e is not None:
            examples = examples[s:e]
            print(f"Sliced [{s}:{e}] → {len(examples)} of {total} examples")
        else:
            print(f"Loaded {len(examples)} examples from {path}")
        return examples

    # --- output prep & resume -----------------------------------------

    def _prepare_output(self) -> tuple[set[tuple[str, int]], int]:
        """Return (done_pairs, kept_rows). `done_pairs` is a set of
        (example_hash, rollout_idx) already recorded in full_data.jsonl.
        """
        os.makedirs(self.config.output_dir, exist_ok=True)

        if self.config.force_rewrite:
            for p in (self.config.output_path, self.config.detail_path,
                      self.config.report_path):
                if os.path.exists(p):
                    open(p, "w").close()
            print("[INFO] force_rewrite: cleared output directory")
            return set(), 0

        done: set[tuple[str, int]] = set()
        if os.path.exists(self.config.detail_path):
            with open(self.config.detail_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    h = rec.get("example_hash")
                    idx = rec.get("rollout_idx")
                    if h is None or idx is None:
                        continue
                    done.add((h, int(idx)))
                    self._rollouts_per_example[h] += 1
                    if rec.get("passed"):
                        self._passes_per_example[h] += 1

        kept = 0
        if os.path.exists(self.config.output_path):
            with open(self.config.output_path, "r", encoding="utf-8") as f:
                kept = sum(1 for line in f if line.strip())

        if done:
            print(f"[RELOAD] {len(done)} rollouts, {kept} kept rows. Resuming…")
        return done, kept

    # --- file IO -------------------------------------------------------

    @staticmethod
    def _append_jsonl(path: str, obj: dict,
                      lock: Optional[threading.Lock] = None) -> None:
        if lock is not None:
            with lock:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        else:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    # --- per-rollout processing ---------------------------------------

    def _build_detail_record(self, example: dict, h: str, rollout_idx: int,
                             idx: int, trajectory: Trajectory,
                             judge_result: JudgeResult, kept: bool) -> dict:
        return {
            "index": idx,
            "example_hash": h,
            "rollout_idx": rollout_idx,
            "passed": bool(judge_result.passed),
            "kept": kept,
            "judge_result": _judge_result_to_dict(judge_result),
            "trajectory": _trajectory_to_dict(trajectory),
            "example": example,
        }

    def _keep_limit(self) -> Optional[int]:
        k = self.config.normalized_keep()
        return None if k == "all" else int(k)

    # --- early stop ---------------------------------------------------

    def _check_early_stop(self, attempted: int, passed: int,
                          warned: bool) -> tuple[bool, bool]:
        if self.config.min_pass_rate <= 0 or attempted < 100:
            return False, warned
        rate = passed / attempted if attempted else 0.0
        if not warned:
            tqdm.write(f"\n[CHECK] {attempted} rollouts reached — "
                       f"pass rate: {rate:.3f}, min_pass_rate: {self.config.min_pass_rate}")
            warned = True
        if rate < self.config.min_pass_rate:
            tqdm.write(f"[EARLY STOP] pass rate {rate:.3f} < "
                       f"{self.config.min_pass_rate} after {attempted} rollouts.")
            return True, warned
        return False, warned

    # --- async entry ---------------------------------------------------

    async def arun(self, concurrency: int = 20) -> dict:
        examples = self._load_data()
        self.rollout.setup(self.config)

        done_pairs, _ = self._prepare_output()

        rng = random.Random(self.config.seed)
        rng.shuffle(examples)

        N = self.config.rollout_n
        is_distill = getattr(self.config, "mode", "test") == "distill"

        lock = asyncio.Lock()
        file_lock = threading.Lock()

        # Counters — include resumed data so stats are consistent (Fix #4)
        resumed_rollouts = sum(self._rollouts_per_example.values())
        resumed_passed = sum(self._passes_per_example.values())
        rollouts_done = 0
        total_passed = 0
        early_stopped = False
        warned = False

        _SENTINEL = None  # poison pill for worker shutdown

        if is_distill:
            work_queue: asyncio.Queue = asyncio.Queue()
            resumed_complete = 0
            for idx, ex in enumerate(examples):
                h = example_hash(ex)
                if self._passes_per_example.get(h, 0) > 0:
                    resumed_complete += 1
                    continue
                first_undone = 0
                while first_undone < N and (h, first_undone) in done_pairs:
                    first_undone += 1
                if first_undone >= N:
                    resumed_complete += 1
                    continue
                work_queue.put_nowait((idx, ex, h, first_undone))

            pbar = tqdm(total=len(examples), initial=resumed_complete,
                        desc="examples", unit="ex")

            all_rollouts = resumed_rollouts
            all_passed = resumed_passed

            def _postfix():
                pbar.set_postfix_str(
                    f"pass={all_passed}/{max(all_rollouts, 1)}"
                )

            # Track pending items so we know when to send sentinels
            pending_items = work_queue.qsize()

            async def worker():
                nonlocal rollouts_done, total_passed, early_stopped, \
                    warned, pending_items, all_rollouts, all_passed

                while True:
                    item = await work_queue.get()
                    if item is _SENTINEL:
                        work_queue.task_done()
                        return

                    idx, ex, h, r = item

                    if (h, r) in done_pairs:
                        if r + 1 < N and self._passes_per_example.get(h, 0) == 0:
                            work_queue.put_nowait((idx, ex, h, r + 1))
                            async with lock:
                                pending_items += 1
                        else:
                            async with lock:
                                pbar.update(1)
                        async with lock:
                            pending_items -= 1
                        work_queue.task_done()
                        continue

                    async with lock:
                        if early_stopped:
                            pending_items -= 1
                            work_queue.task_done()
                            continue

                    try:
                        traj = await self.rollout.arollout(ex)
                    except Exception as exc:
                        traj = Trajectory(
                            steps=[],
                            metadata={"rollout_error": repr(exc)},
                        )

                    if traj.prejudged is not None:
                        jr = traj.prejudged
                    else:
                        try:
                            jr = await self.judge.ajudge(ex, traj)
                        except Exception as exc:
                            jr = JudgeResult(
                                passed=False,
                                details=[{"type": "judge_error", "passed": False,
                                          "error": repr(exc)}],
                            )

                    enqueue_retry = False
                    async with lock:
                        rollouts_done += 1
                        all_rollouts += 1
                        self._all_judge_results.append(jr)
                        self._rollouts_per_example[h] += 1

                        if jr.passed:
                            total_passed += 1
                            all_passed += 1
                            self._passes_per_example[h] += 1
                            pbar.update(1)
                        else:
                            if r + 1 < N:
                                enqueue_retry = True
                            else:
                                pbar.update(1)

                    async with lock:
                        _postfix()
                        stop, warned = self._check_early_stop(
                            all_rollouts, all_passed, warned)
                        if stop:
                            early_stopped = True

                    detail = self._build_detail_record(
                        ex, h, r, idx, traj, jr, False)
                    self._append_jsonl(self.config.detail_path, detail, file_lock)

                    if enqueue_retry:
                        work_queue.put_nowait((idx, ex, h, r + 1))
                        async with lock:
                            pending_items += 1

                    async with lock:
                        pending_items -= 1

                    work_queue.task_done()

            # Fix #5: persistent workers with sentinel-based shutdown
            n_workers = max(1, concurrency)
            workers = [asyncio.create_task(worker()) for _ in range(n_workers)]

            await work_queue.join()

            for _ in range(n_workers):
                work_queue.put_nowait(_SENTINEL)
            await asyncio.gather(*workers)

        else:
            # Test mode: pre-build all work items, run all N per example.
            work: list[tuple[int, dict, str, int]] = []
            for idx, ex in enumerate(examples):
                h = example_hash(ex)
                for r in range(N):
                    work.append((idx, ex, h, r))
            work_iter = iter(work)

            pbar = tqdm(total=len(work), initial=len(done_pairs),
                        desc="rollouts", unit="r")

            all_rollouts = resumed_rollouts
            all_passed = resumed_passed

            def _postfix():
                pbar.set_postfix_str(
                    f"pass@1={all_passed}/{max(all_rollouts, 1)}"
                )

            async def worker():
                nonlocal rollouts_done, total_passed, early_stopped, \
                    warned, all_rollouts, all_passed

                while True:
                    async with lock:
                        if early_stopped:
                            return
                        try:
                            idx, ex, h, r = next(work_iter)
                        except StopIteration:
                            return

                    if (h, r) in done_pairs:
                        async with lock:
                            pbar.update(1)
                        continue

                    try:
                        traj = await self.rollout.arollout(ex)
                    except Exception as exc:
                        traj = Trajectory(
                            steps=[],
                            metadata={"rollout_error": repr(exc)},
                        )

                    if traj.prejudged is not None:
                        jr = traj.prejudged
                    else:
                        try:
                            jr = await self.judge.ajudge(ex, traj)
                        except Exception as exc:
                            jr = JudgeResult(
                                passed=False,
                                details=[{"type": "judge_error", "passed": False,
                                          "error": repr(exc)}],
                            )

                    async with lock:
                        if jr.passed:
                            total_passed += 1
                            all_passed += 1
                            self._passes_per_example[h] += 1
                        self._all_judge_results.append(jr)
                        self._rollouts_per_example[h] += 1

                    detail = self._build_detail_record(
                        ex, h, r, idx, traj, jr, False)
                    self._append_jsonl(self.config.detail_path, detail, file_lock)

                    async with lock:
                        rollouts_done += 1
                        all_rollouts += 1
                        pbar.update(1)
                        _postfix()
                        stop, warned = self._check_early_stop(
                            all_rollouts, all_passed, warned)
                        if stop:
                            early_stopped = True
                            return

            workers = [asyncio.create_task(worker())
                       for _ in range(max(1, concurrency))]
            await asyncio.gather(*workers)

        pbar.close()

        kept_trajectories, kept_rows = self._build_data_jsonl()

        print(f"Wrote {kept_rows} rows from {kept_trajectories} kept "
              f"trajectories to {self.config.output_path}")
        print(f"Wrote {rollouts_done + len(done_pairs)} detail rows to "
              f"{self.config.detail_path}")

        # Fix #4: pass total counts (resumed + current) for consistent stats
        return self._write_report(len(examples), kept_trajectories, kept_rows,
                                  rollouts_done + resumed_rollouts,
                                  total_passed + resumed_passed,
                                  early_stopped)

    # --- post-processing: build data.jsonl ----------------------------

    def _build_data_jsonl(self) -> tuple[int, int]:
        """Filter full_data.jsonl → passed → keep_per_example → format →
        drop empty → random-sample trajectories to target_num/target_count →
        write data.jsonl. Returns (kept_trajectories, written_rows)."""
        path = self.config.detail_path
        if not os.path.exists(path):
            return 0, 0

        keep_limit = self._keep_limit()
        per_example_count: dict[str, int] = defaultdict(int)
        detail_records: list[dict] = []
        passed_records: list[tuple[int, dict]] = []

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                detail_idx = len(detail_records)
                rec["kept"] = False
                detail_records.append(rec)
                if not rec.get("passed"):
                    continue
                h = rec.get("example_hash", "")
                if keep_limit is not None and per_example_count[h] >= keep_limit:
                    continue
                per_example_count[h] += 1
                passed_records.append((detail_idx, rec))

        # Format all candidates and drop empty results before sampling.  The
        # sampling unit is one passed rollout/trajectory, even if its formatter
        # emits multiple rows (e.g. deep-search conversation segments).
        formatted_trajectories: list[tuple[int, list[dict]]] = []
        for detail_idx, rec in passed_records:
            ex = rec.get("example", {})
            traj_dict = rec.get("trajectory", {})
            jr_dict = rec.get("judge_result", {})
            steps = [Step(**s) for s in traj_dict.get("steps", [])]
            traj = Trajectory(steps=steps, metadata=traj_dict.get("metadata", {}))
            if traj_dict.get("prejudged"):
                traj.prejudged = JudgeResult(**traj_dict["prejudged"])
            jr = JudgeResult(**jr_dict)
            result = self.formatter.format(ex, traj, jr)
            rows = result if isinstance(result, list) else [result]
            if rows:
                formatted_trajectories.append((detail_idx, rows))

        rng = random.Random(self.config.seed)
        target_num = getattr(self.config, "target_num", 0)
        target_count = self.config.target_count
        final_target = target_num if target_num > 0 else target_count
        if final_target > 0 and len(formatted_trajectories) > final_target:
            formatted_trajectories = rng.sample(formatted_trajectories, final_target)

        kept_detail_indices = {detail_idx for detail_idx, _ in formatted_trajectories}
        for detail_idx in kept_detail_indices:
            detail_records[detail_idx]["kept"] = True

        with open(path, "w", encoding="utf-8") as f:
            for rec in detail_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        written = 0
        with open(self.config.output_path, "w", encoding="utf-8") as f:
            for _, rows in formatted_trajectories:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    written += 1

        return len(formatted_trajectories), written

    # --- report --------------------------------------------------------

    def _write_report(self, total_examples: int, kept_trajectories: int,
                      kept_rows: int,
                      rollouts_done: int, total_passed: int,
                      early_stopped: bool) -> dict:
        # Aggregate per-example stats (combining resumed + new)
        attempted = len([h for h, n in self._rollouts_per_example.items() if n > 0])
        succeeded_any = len([h for h, p in self._passes_per_example.items() if p > 0])

        pass_at_1 = (total_passed / rollouts_done) if rollouts_done else 0.0
        pass_at_N = (succeeded_any / attempted) if attempted else 0.0

        # per-example pass distribution
        pass_distribution: dict[str, int] = defaultdict(int)
        for _, p in self._passes_per_example.items():
            pass_distribution[str(p)] += 1

        benchmark_stats: dict = {}
        if self.spec is not None and self.spec.stats_fn is not None:
            try:
                benchmark_stats = self.spec.stats_fn(self._all_judge_results)
            except Exception as exc:  # noqa: BLE001
                benchmark_stats = {"_error": repr(exc)}

        report = {
            "config": {
                "benchmark": self.config.benchmark,
                "mode": getattr(self.config, "mode", "test"),
                "submission_dir": self.config.submission_dir,
                "target_count": self.config.target_count,
                "target_num": getattr(self.config, "target_num", 0),
                "rollout_n": self.config.rollout_n,
                "keep_per_example": self.config.keep_per_example,
                "seed": self.config.seed,
                "model": self.config.model,
            },
            "results": {
                "queries_available": total_examples,
                "queries_attempted": attempted,
                "queries_succeeded": succeeded_any,
                "total_rollouts": rollouts_done,
                "total_passed_rollouts": total_passed,
                "kept_trajectories": kept_trajectories,
                "kept_rows": kept_rows,
                "pass_at_1": round(pass_at_1, 4),
                f"pass_at_{self.config.rollout_n}": round(pass_at_N, 4),
                "early_stopped": early_stopped,
            },
            "pass_distribution": dict(
                sorted(pass_distribution.items(), key=lambda x: int(x[0]))),
            "benchmark_stats": benchmark_stats,
        }

        with open(self.config.report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Wrote report to {self.config.report_path}")

        self._write_parquet()

        return report

    # --- parquet export ---------------------------------------------------

    def _write_parquet(self) -> None:
        """Convert data.jsonl → data.parquet if pandas is available."""
        jsonl_path = self.config.output_path
        if not os.path.exists(jsonl_path):
            return
        parquet_path = jsonl_path.rsplit(".", 1)[0] + ".parquet"
        try:
            import pandas as pd
            rows: list[dict] = []
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
            if not rows:
                return
            df = pd.DataFrame(rows)
            df.to_parquet(parquet_path, index=False)
            print(f"Wrote {len(df)} rows to {parquet_path}")
        except ImportError:
            print("[WARN] pandas not installed, skipping parquet export")
        except Exception as e:
            print(f"[WARN] parquet export failed: {e}")
