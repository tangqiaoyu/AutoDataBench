"""Benchmark composition declarations.

Each file here calls `framework.registry.register_benchmark(...)` at import
time. `framework.run` imports the right module after parsing `--benchmark`.
"""
