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
    durations_list: deque = field(default_factory=lambda: deque(maxlen=100))


    last_finished_at: float | None = None
    last_exception: BaseException | None = None
    last_traceback: str | None = None

    # guarda só os últimos N eventos, não tudo
    last_records: deque[TaskFinishRecord] = field(
        default_factory=lambda: deque(maxlen=20)
    )



def print_task_stats_report(history: deque["TaskStats"]) -> None:
    try:
        if not history:
            print("\n[TaskStats] Nenhuma task registrada ainda.\n")
            return
        print("começando o print_task_stats_report")
        resposta = []
        def add_linha(linha,resposta = resposta):
            resposta.append(linha)
        add_linha("\n" + "=" * 80)
        add_linha("📊 TASK EXECUTION REPORT")
        add_linha("=" * 80)

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

            add_linha(f"\n🧩 Task: {stats.name}"+
            f"           protected : {stats.protected}")
            add_linha("-" * 80)

            add_linha(f"Executions : {stats.total_runs}"
                )
            add_linha(
                f"Status     : " +
                f"✅ {stats.success} | " +
                f"❌ {stats.error} | "+
                f"🚫 {stats.cancelled} " +
                f"(success rate: {success_rate:.2f}%)"
            )

            add_linha(
                f"Duration   : " +
                f"avg {avg_duration:.3f}s | " +
                f"min {stats.min_duration:.3f}s | "+
                f"max {stats.max_duration:.3f}s | "+
                f"total {stats.total_duration:.2f}s" 
            )

            add_linha(f"Last run   : {last_time}")

            if stats.last_exception:
                add_linha("Last error :")
                add_linha(f"  {type(stats.last_exception).__name__}: {stats.last_exception}")
                if stats.last_traceback:
                    add_linha("  Traceback (last):")
                    add_linha(
                        "\n".join(
                            "    " + line
                            for line in stats.last_traceback.splitlines()[-5:]
                        )
                    )

        add_linha("\n" + "=" * 80 + "\n")
        print("\n".join(resposta))
    except Exception as e:
        print(f"[print_task_stats_report] deu erro e foi {e}")