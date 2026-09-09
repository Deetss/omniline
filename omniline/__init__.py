"""Shared core for building terminal statuslines across AI coding harnesses.

Layout:
  render.py        ANSI colors, bar meters, pct->color. Pure functions.
  pace.py           Burn-aware coloring for rate-limit windows.
  sources/          Reusable data lookups (clauth account, git branch,
                    edgentic token log) any adapter can call.
  adapters/         One module per harness. Each maps that harness's own
                    stdin JSON shape onto render/pace/sources calls and
                    prints the joined result. This is the only part that
                    should ever need to know a specific harness's schema.
"""
