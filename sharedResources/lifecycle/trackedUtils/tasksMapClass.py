
from __future__ import annotations
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Callable, Optional, Literal
import warnings
import traceback
import asyncio
import logging
# sharedResources/generalUtils
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))
from sharedResources.lifecycle.trackedUtils.trackedItem import TaskFinishRecord , TrackedItem
from sharedResources.lifecycle.trackedUtils.taskStats import TaskStats, print_task_stats_report
from sharedResources.debuggingResources.error_tracker import monitor_error, log_error_forensics_plus

class TasksMapClass:
    """ Gerencia tasks rastreadas: vivas e histórico """
    # ========================
    # Tasks vivas
    # ========================
    
    alive: dict[str, list[TrackedItem]] = defaultdict(list)
    removed_while_running: list[TrackedItem] = []  # para casos de tarefas finalizadas antes do cancelamento comum do shutdown
    lock = threading.RLock()  # para threadsafe
    # lock = asyncio.Lock()
    register_log = None
    default_cleanup_event = None
    STRICT_MODE = False  # dev

    # ========================
    # sizes 
    # ========================
    
    history_max = 10000
    # history_per_name = 500
    # by_status = 5000

    # ========================
    # Histórico de tasks
    # ========================
    
    history: deque[TaskStats] = deque(maxlen=history_max)
    # ========================
    # Adicionar task
    # ========================
    @classmethod
    def add_tracked(cls, tracked_item: TrackedItem):
        name = tracked_item.name or f"unnamedTask-{id(tracked_item)}"
        with cls.lock:
            cls.alive.setdefault(name,[]).append(tracked_item)
            # print("[add_tracked]the task's name type added is: ",type(name))
            # print("[add_tracked]the task's name added is: ",name)
            # print("[add_tracked]the tasks that exists now are:")
            # for x in cls.alive:
            #     print(x)
            # if x == name:
            #     print("the tasks under this name are: ")
            #     for task_atual in cls.alive[x]:
            #         print(task_atual)

    @classmethod
    def register_task(
        cls,
        task : asyncio.Task,
        name : str | None,
        created_from : str ,
        *                   ,
        cleanup_event = None,
        cleanup_function = None , 
        protected : bool = False,
        ):
        """ Registra uma asyncio.Task como TrackedItem

            created_from é um campo pra que eu consiga humanamente entender onde ela foi criada por exemplo:
            "EventBuffer.start" 
            ou algo parecido.
            vai ser uma string capaz de me fazer entender o contexto e onde localizar no codigo
        
        """


        task_name = name or task.get_name()

        selfCleanUpEvent    = cleanup_event or cls.default_cleanup_event   # pensado para fazer operações internas de limpeza
        if selfCleanUpEvent is not cls.default_cleanup_event:
            selfCleanUpEventUse = True  # flag para  a task usar o evento de self cleanup
        else:
            selfCleanUpEventUse = False
        
        current_task_item     = TrackedItem(
            obj = task,
            cleanup_event = selfCleanUpEvent, 
            cleanup_enabled = selfCleanUpEventUse,
            name = task_name, 
            kind = "task",
            created_from = created_from,
            cleanup_function = cleanup_function,
            protected = protected)
        
        ######################## setando a task no mapa de tasks ########################
        cls.add_tracked(current_task_item)

        # cls.tasksMap.get_alive().setdefault(task_name, []).append(current_task_item)

        # cls.register_log(
        #     f"[TrackedTask] registered {task_name} (protected={protected}) from {created_from}",
        #     "tasks",
        #     )
        

    @classmethod
    def get_alive_tracked_from_task (cls, task : asyncio.Task):
        """returns the tracked item corresponding to the task given or return None"""
        task_name = task.get_name()
        items = cls.alive.get(task_name, [])
        tracked_or_nothing  = [item for item in items if item.obj is task]
        if tracked_or_nothing:
            return tracked_or_nothing[0]
        else:
            print("the alive property is: ",cls.alive)
            print("the task not found is: ",task)
            # warnings.warn("task finished but was not registered properly in the alive property!")
            return None 
    # ========================
    # Remover task
    # ========================

    @classmethod
    def remove_tracked_from_alive_map(cls, tracked_item: TrackedItem):
        try:
            with cls.lock:
                name = tracked_item.name or f"unnamedTask-{id(tracked_item)}"

                # remove da lista alive
                if name in cls.alive.keys():
                    if tracked_item in cls.alive[name]:

                            cls.alive[name].remove(tracked_item)
                            if not cls.alive[name]:
                                del cls.alive[name]
                                # print("[remove_tracked_from_alive_map] removi o nome: " , name," do cls.alive")
                    else:
                        print(f"name: {name} is not in cla.alive[name] that is: {cls.alive[name]}")
                else:
                    print(f"name: {name} is not in cls.alive that is: {cls.alive}")
            return True
        except Exception as e:
            print(f"[remove_tracked_from_alive_map] deu erro e foi: {e}")
            # pass  # já tinha sido removido
            log_error_forensics_plus(e)
            return False

    @classmethod
    def remove_task_while_running(cls, task: asyncio.Task):
        """Remove uma task do mapa de vivas de forma segura, sem cancelar a task (para casos de tarefas que se auto-limpam)"""
        tracked = cls.get_alive_tracked_from_task(task)
        if tracked:
            result = cls.remove_tracked_from_alive_map(tracked)
            if result:
                cls.removed_while_running.append(tracked)
            return result
        else:
            print("task não encontrada para remoção segura: ", task)
            return False
        
    @staticmethod
    def build_record(tracked: TrackedItem):
        task = tracked.obj
        
        try:
            if task.cancelled():
                status = "cancelled"
                exception = None
            else:
                task_exception = task.exception()
                if task_exception:
                    status = "error"
                    exception = task_exception
                else:
                    status = "success"
                    exception = None
        except asyncio.CancelledError:
            status = "cancelled"
            exception = None

        # if task.cancelled():
        #     status = "cancelled"
        # else:
        #     task_exception = task.exception()
            
        #     if task_exception:
        #         status = "error"
        #         exception = task_exception
        #         traceback = None # tenho que implementar isso ainda!!!!!!!!!
        #     else:                
        #         status = "success"
        # Implementação do Traceback que faltava
        tb_str = None
        if exception:
            tb_str = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))

        return TaskFinishRecord(
            name = tracked.name,
            kind = tracked.kind,
            status = status,
            created_from = tracked.created_from,
            protected = tracked.obj.protected, # Task já tem o atributo via setattr no MyLoop
            created_at = tracked.created_at,
            exception = exception,
            traceback = tb_str,
            thread_name = tracked.thread_name,
        )
        # record = TaskFinishRecord(
        #     name = name,
        #     kind = kind,
        #     status = status,
        #     created_from = created_from,
        #     protected = protected,
        #     created_at =created_at,
        #     exception = exception,
        #     traceback = tb_str,
        #     thread_name = thread_name,
            
        #     )       
        # return record

    @classmethod
    def upgrade_task_stats(cls, record: TaskFinishRecord) -> TaskStats:

        try:
        
            # 1️⃣ tenta achar stats existente
            stats = next(
                (s for s in cls.history if s.name == record.name and s.kind == record.kind),
                None
            )

            # 2️⃣ se não existir, cria
            if stats is None:
                stats = TaskStats(name=record.name, kind=record.kind, protected = record.protected)
                cls.history.append(stats)

            # 3️⃣ atualiza contadores
            stats.total_runs += 1

            if record.status == "success":
                stats.success += 1
            elif record.status == "cancelled":
                stats.cancelled += 1
            elif record.status == "error":
                stats.error += 1

            # 4️⃣ duração
            duration = record.finished_at - record.created_at
            stats.total_duration += duration
            stats.min_duration = min(stats.min_duration, duration)
            stats.max_duration = max(stats.max_duration, duration)
            stats.durations_list.append({"start": record.created_at,"finish": record.finished_at})

            # 5️⃣ últimos dados
            stats.last_finished_at = record.finished_at

            if record.status == "error":
                stats.last_exception = record.exception
                stats.last_traceback = record.traceback

            # 6️⃣ histórico curto
            stats.last_records.append(record)

            return stats
        except Exception as e:
            print(f"[upgrade_task_stats] deu erro e foi {e}")
            log_error_forensics_plus(e)


    # ========================
    # Consultas
    # ========================

    @classmethod
    def get_alive(cls) -> list[TrackedItem]:
        with cls.lock:
            return cls.alive

    @classmethod
    def get_history(cls) -> list[TaskFinishRecord]:
        with cls.lock:
            return list(cls.history)

    @classmethod
    def get_by_name(cls, name: str) -> list[TaskFinishRecord]:
        with cls.lock:
            return list(cls.by_name.get(name, []))

    @classmethod
    def get_by_status(cls, status: Literal["success","error","cancelled"]) -> list[TaskFinishRecord]:
        with cls.lock:
            return list(cls.by_status.get(status, []))


    # @classmethod
    # def cancel_during_execution(cls,task: asyncio.Task):
    #     """Cancela todas as tasks vivas de forma segura, aguardando sua finalização e limpando o mapa de vivas"""
    #     tracked = cls.get_alive_tracked_from_task(task)
    #     cls.remove_tracked_from_alive_map(tracked)
    #     if not  task.done():
    #         task.cancel()
    #         # print("task cancelada: ", task)

    @staticmethod
    def _on_task_finish(task: asyncio.Task):
        try:

            tracked = TasksMapClass.get_alive_tracked_from_task(task)
            if not tracked:
                for tracked_already_finished in TasksMapClass.removed_while_running:
                    if tracked_already_finished.obj is task:
                        print("task encontrada na removed_while_running: ", task)
                        tracked = tracked_already_finished
                        return 
                if not tracked:
                    warnings.warn(f"task que acabou de acabar não consta na lista das tasks vivas! task é: {task}")
                    return 

            record = TasksMapClass.build_record(tracked)

            with TasksMapClass.lock:            
                TasksMapClass.remove_tracked_from_alive_map(tracked)
                
                TasksMapClass.upgrade_task_stats(record)

            if tracked.cleanup_function:
                try:
                    tracked.cleanup_function(tracked)
                except Exception as e:
                    print(f"Erro no cleanup da task {tracked.name}: {e}")
        
        except Exception as e:
            print(f"[_on_task_finish] deu erro e foi: {e}")
            log_error_forensics_plus(e)
       
        if record.status == "error":
            if record.exception is None:
                raise RuntimeError(
                    f"Task '{record.name}' failed but no exception was recorded"
                )

            if TasksMapClass.STRICT_MODE:
                raise record.exception
            else:
                string  = f"Task '{record.name}' failed" +"\n"
                string += f" exception ={record.exception} "+ "\n"
                string += f"traceback: {record.traceback}"
                warnings.warn(
                    string,
                    RuntimeWarning,
                    stacklevel=2,
                )
    # ========================
    # Debug / Logs
    # ========================
    @classmethod
    def debug_print(cls):
        with cls.lock:
            print("=== Alive tasks ===")
            for name, lst in cls.alive.items():
                print(f"{name}: {len(lst)} tasks")
            print("=== History count ===")
            print(f"Total finished: {len(cls.history)}")
            for status, dq in cls.by_status.items():
                print(f"{status}: {len(dq)}")

    @classmethod
    def set_register_log(cls,register_function_log):
        if cls.register_log is None:
            cls.register_log = register_function_log
        else:
            print(f"tentei register o register_log de novo com {register_function_log}")
        
    @classmethod
    def set_default_cleanup_event(cls,cleanup_event):
        if cls.default_cleanup_event is None:
            cls.default_cleanup_event  = cleanup_event
        else:
            print("[TrackedTask] default_cleanup_event already set!")
    
    @classmethod
    def relatorio(cls):
        try:
            print_task_stats_report(cls.history)
        except Exception as e:
            print(f"[relatorio] deu merda e foi: {e}")
            log_error_forensics_plus(e)