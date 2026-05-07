"""BrowseComp benchmark: composition declaration."""

from __future__ import annotations

import argparse

from ..formatters.segments import SegmentsFormatter
from ..framework.config import DistillConfig
from ..framework.registry import BenchmarkSpec, register_benchmark
from ..judges.browse_comp import BrowseCompJudge
from ..rollouts.browse_comp import BrowseCompRollout
from ..tools.tool_config import get_fetch_config, get_search_config


def _add_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max_iterations", type=int, default=15,
                        help="Max tool-calling iterations per question")
    parser.add_argument("--threshold", type=int, default=1024 * 16,
                        help="Chat-template token threshold to trigger tool-response omission")
    parser.add_argument("--tool_timeout", type=float, default=300.0,
                        help="Timeout in seconds for tool execution")
    parser.add_argument("--tool_call_parser", type=str, default="qwen",
                        help="SGLang tool_call parser type. 'qwen'/'qwen25' = "
                             "JSON tool calls inside <tool_call>...</tool_call>; "
                             "'qwen3_coder' = XML <function=.../><parameter=.../> "
                             "tool calls. Selects both the system prompt and the "
                             "parsing path. Default: 'qwen'.")

    search_cfg = get_search_config()
    fetch_cfg = get_fetch_config()
    parser.add_argument("--search_api_endpoint", type=str,
                        default=search_cfg["endpoint"],
                        help="Search API endpoint (env: SEARCH_API_ENDPOINT)")
    parser.add_argument("--search_api_key", type=str,
                        default=search_cfg["api_key"],
                        help="Search API key (env: SEARCH_API_KEY)")
    parser.add_argument("--fetch_api_endpoint", type=str,
                        default=fetch_cfg["endpoint"],
                        help="Fetch/Firecrawl API endpoint (env: FETCH_API_ENDPOINT)")
    parser.add_argument("--fetch_api_key", type=str,
                        default=fetch_cfg["api_key"],
                        help="Fetch/Firecrawl API key (env: FETCH_API_KEY)")


def _build(args: argparse.Namespace, config: DistillConfig):
    rollout = BrowseCompRollout(
        max_iterations=args.max_iterations,
        threshold=args.threshold,
        tool_timeout=args.tool_timeout,
        search_api_endpoint=args.search_api_endpoint,
        search_api_key=args.search_api_key,
        fetch_api_endpoint=args.fetch_api_endpoint,
        fetch_api_key=args.fetch_api_key,
        tool_call_parser=args.tool_call_parser,
    )
    judge = BrowseCompJudge()
    judge.load(config)
    formatter = SegmentsFormatter()
    return rollout, judge, formatter


register_benchmark(BenchmarkSpec(
    name="browse_comp",
    build_fn=_build,
    add_args_fn=_add_args,
))
