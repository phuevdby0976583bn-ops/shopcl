# -*- coding: utf-8 -*-
"""
core.batch_runner
Multithreaded batch processing engine.
Accepts task lists and result callbacks for integration with external systems, APIs, or queues.
"""

import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Callable, Optional, Dict, Any, Union
from dataclasses import dataclass, field

from core.models import RegistrationInput, RegistrationResult
from core.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)


@dataclass
class BatchSummary:
    """Summary of batch run execution."""
    total: int = 0
    completed: int = 0
    success_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    elapsed_seconds: float = 0.0
    results: List[RegistrationResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "completed": self.completed,
            "success": self.success_count,
            "failed": self.failed_count,
            "error": self.error_count,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }


class BatchRunner:
    """
    Thread pool runner for executing tasks in parallel.
    Streams execution results via callbacks to decoupling persistence and presentation.
    """

    def __init__(
        self,
        max_workers: int = 4,
        proxy_manager: Optional[ProxyManager] = None,
        on_result: Optional[Callable[[RegistrationResult], None]] = None,
        on_progress: Optional[Callable[[int, int, RegistrationResult], None]] = None,
    ):
        self.max_workers = max_workers
        self.proxy_manager = proxy_manager
        self.on_result = on_result
        self.on_progress = on_progress
        self.stop_event = threading.Event()
        self._lock = threading.Lock()

    def stop(self) -> None:
        """Signal batch execution to gracefully stop."""
        self.stop_event.set()

    def run(
        self,
        tasks: List[RegistrationInput],
        service_worker: Callable[[RegistrationInput], RegistrationResult],
    ) -> BatchSummary:
        """
        Execute a batch of tasks against a registration worker service.
        """
        start_time = time.time()
        summary = BatchSummary(total=len(tasks))
        completed_count = 0

        if not tasks:
            return summary

        def _execute_single(task: RegistrationInput) -> RegistrationResult:
            if self.stop_event.is_set():
                return RegistrationResult(
                    success=False,
                    status="cancelled",
                    identifier=task.identifier,
                    error_message="Batch execution stopped",
                )

            # Giãn cách Anti-Sybil giữa các luồng để tránh cụm request dồn dập
            try:
                from integrity_engine import HumanBehaviorDynamics
                jitter = HumanBehaviorDynamics.sample_cognitive_pause(min_sec=1.5, max_sec=4.0)
                time.sleep(jitter)
            except Exception:
                time.sleep(1.5)

            # Auto-assign proxy from rotation pool if task doesn't already have one
            if not task.proxy and self.proxy_manager:
                task.proxy = self.proxy_manager.next_proxy()

            try:
                res = service_worker(task)
            except Exception as e:
                res = RegistrationResult(
                    success=False,
                    status="error",
                    identifier=task.identifier,
                    error_message=f"Unhandled worker error: {e}",
                )

            # Inform proxy manager about outcome
            if task.proxy and self.proxy_manager and hasattr(task.proxy, "host"):
                if res.success:
                    self.proxy_manager.mark_success(task.proxy)
                elif "proxy" in (res.error_message or "").lower():
                    self.proxy_manager.mark_failed(task.proxy)

            return res

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(_execute_single, task) for task in tasks]

            for future in as_completed(futures):
                if self.stop_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                try:
                    result = future.result()
                except Exception as e:
                    result = RegistrationResult(
                        success=False,
                        status="error",
                        error_message=f"Future execution error: {e}",
                    )

                with self._lock:
                    completed_count += 1
                    summary.completed = completed_count
                    summary.results.append(result)

                    if result.success:
                        summary.success_count += 1
                    elif result.status == "failed":
                        summary.failed_count += 1
                    else:
                        summary.error_count += 1

                # Invoke real-time callback
                if self.on_result:
                    try:
                        self.on_result(result)
                    except Exception as e:
                        logger.error(f"Error in on_result callback: {e}")

                # Invoke progress callback
                if self.on_progress:
                    try:
                        self.on_progress(completed_count, summary.total, result)
                    except Exception as e:
                        logger.error(f"Error in on_progress callback: {e}")

        summary.elapsed_seconds = time.time() - start_time
        return summary


def run_batch(
    tasks: List[RegistrationInput],
    worker_fn: Callable[[RegistrationInput], RegistrationResult],
    max_workers: int = 4,
    proxy_manager: Optional[ProxyManager] = None,
    on_result: Optional[Callable[[RegistrationResult], None]] = None,
    on_progress: Optional[Callable[[int, int, RegistrationResult], None]] = None,
    stop_event: Optional[threading.Event] = None,
) -> BatchSummary:
    """
    Convenience function to run a list of registration tasks across multiple threads.
    
    :param tasks: List of RegistrationInput items to process.
    :param worker_fn: Function or Service.register method that takes RegistrationInput and returns RegistrationResult.
    :param max_workers: Number of concurrent threads.
    :param proxy_manager: Optional ProxyManager for automatic proxy rotation.
    :param on_result: Real-time callback invoked with RegistrationResult as each task completes.
    :param on_progress: Callback invoked with (current_index, total, result).
    :param stop_event: Threading event to cancel execution.
    :return: BatchSummary object with all results and metrics.
    """
    runner = BatchRunner(
        max_workers=max_workers,
        proxy_manager=proxy_manager,
        on_result=on_result,
        on_progress=on_progress,
    )
    if stop_event:
        runner.stop_event = stop_event

    return runner.run(tasks, worker_fn)
