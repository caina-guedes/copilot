from datetime import datetime
from dataclasses import dataclass, field
from collections import deque
from typing import Literal 
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))
from sharedResources.lifecycle.trackedUtils.trackedItem import TaskFinishRecord



@dataclass
class TaskStats:
    name: str
    kind: Literal["task"]

    protected : bool
    total_runs: int = 0
    success: int = 0
    cancelled: int = 0
    error: int = 0

    total_duration: float = 0.0
    min_duration: float = float("inf")
    max_duration: float = 0.0
    durations_list: list = field(default_factory=list)


    last_finished_at: float | None = None
    last_exception: BaseException | None = None
    last_traceback: str | None = None

    # guarda só os últimos N eventos, não tudo
    last_records: deque[TaskFinishRecord] = field(
        default_factory=lambda: deque(maxlen=20)
    )



def print_task_stats_report(history: deque["TaskStats"]) -> None:
    if not history:
        print("\n[TaskStats] Nenhuma task registrada ainda.\n")
        return

    print("\n" + "=" * 80)
    print("📊 TASK EXECUTION REPORT")
    print("=" * 80)

    for stats in history:
        avg_duration = (
            stats.total_duration / stats.total_runs
            if stats.total_runs > 0
            else 0.0
        )

        success_rate = (
            (stats.success / stats.total_runs) * 100
            if stats.total_runs > 0
            else 0.0
        )

        last_time = (
            datetime.fromtimestamp(stats.last_finished_at).strftime("%Y-%m-%d %H:%M:%S")
            if stats.last_finished_at
            else "N/A"
        )

        print(f"\n🧩 Task: {stats.name}"
        f"           protected : {stats.protected}")
        print("-" * 80)

        print(f"Executions : {stats.total_runs}"
            )
        print(
            f"Status     : "
            f"✅ {stats.success} | "
            f"❌ {stats.error} | "
            f"🚫 {stats.cancelled} "
            f"(success rate: {success_rate:.2f}%)"
        )

        print(
            f"Duration   : "
            f"avg {avg_duration:.3f}s | "
            f"min {stats.min_duration:.3f}s | "
            f"max {stats.max_duration:.3f}s | "
            f"total {stats.total_duration:.2f}s"
        )

        print(f"Last run   : {last_time}")

        if stats.last_exception:
            print("Last error :")
            print(f"  {type(stats.last_exception).__name__}: {stats.last_exception}")
            if stats.last_traceback:
                print("  Traceback (last):")
                print(
                    "\n".join(
                        "    " + line
                        for line in stats.last_traceback.splitlines()[-5:]
                    )
                )

    print("\n" + "=" * 80 + "\n")
