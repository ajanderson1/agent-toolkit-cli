"""Repeatable headless interaction benchmark; never reads the user's assets.

Run: uv run python scripts/benchmark_tui.py --rows 500 --samples 7
"""
from __future__ import annotations

import argparse
import asyncio
import cProfile
import json
import statistics
from time import perf_counter

from textual.app import App, ComposeResult

from agent_toolkit_tui.skill_state import SkillCell, SkillRow, interactive_agents
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


class BenchmarkApp(App):
    def __init__(self, count: int) -> None:
        super().__init__()
        self.rows = [
            SkillRow(
                slug=f"skill-{i:05d}", source=f"example/source-{i // 10}",
                ref="main", state="clean",
                cells={
                    (harness, "global"): SkillCell(False, False, False)
                    for harness in interactive_agents()
                },
                collection_key=(f"example/source-{i // 10}", "main"),
                collection_label=f"source-{i // 10}",
                display_name=f"skill-{i:05d}",
            )
            for i in range(count)
        ]

    def compose(self) -> ComposeResult:
        yield SkillGrid(self.rows, id="grid")


async def measure(count: int, samples: int, profile: str | None) -> None:
    app = BenchmarkApp(count)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        grid = app.query_one(SkillGrid)
        # Keep the measured workload independent of collapsed-by-default UX.
        grid._collapsed.clear()
        grid.set_filter("")
        grid.cursor_to_cell(row_slug=grid.row_slugs[0], agent_name="standard")
        await pilot.pause()
        profiler = cProfile.Profile() if profile else None
        if profiler:
            profiler.enable()
        timings: dict[str, list[float]] = {"toggle": [], "filter": []}
        for _ in range(samples):
            start = perf_counter()
            grid.action_toggle_cell()
            await pilot._wait_for_screen()
            timings["toggle"].append((perf_counter() - start) * 1000)
            start = perf_counter()
            grid.set_filter("skill-000")
            grid.set_filter("")
            await pilot._wait_for_screen()
            timings["filter"].append((perf_counter() - start) * 1000)
        if profiler:
            profiler.disable()
            profiler.dump_stats(profile)
        print(json.dumps({
            "rows": count, "samples": samples,
            "milliseconds": {
                name: {"median": round(statistics.median(values), 2),
                       "min": round(min(values), 2), "max": round(max(values), 2)}
                for name, values in timings.items()
            },
        }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=500)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--profile")
    args = parser.parse_args()
    asyncio.run(measure(args.rows, args.samples, args.profile))
