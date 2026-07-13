import importlib.util
import os
import pathlib
import threading
import time
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "services" / "task_serial_executor.py"
spec = importlib.util.spec_from_file_location("task_serial_executor", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError("task_serial_executor module spec not found")
task_serial_executor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task_serial_executor)
ConcurrentTaskExecutor = task_serial_executor.ConcurrentTaskExecutor
SerialTaskExecutor = task_serial_executor.SerialTaskExecutor


class TestTaskSerialExecutor(unittest.TestCase):
    def test_default_executor_runs_tasks_concurrently(self):
        with patch.dict(os.environ, {"TASK_MAX_WORKERS": "3"}, clear=False):
            executor = ConcurrentTaskExecutor()
        self.assertEqual(executor._max_workers, 3)
        state_lock = threading.Lock()
        state = {"active": 0, "peak_active": 0}
        barrier = threading.Barrier(2)

        def critical_work():
            with state_lock:
                state["active"] += 1
                state["peak_active"] = max(state["peak_active"], state["active"])
            try:
                barrier.wait(timeout=1)
                time.sleep(0.05)
            finally:
                with state_lock:
                    state["active"] -= 1

        threads = [threading.Thread(target=lambda: executor.run(critical_work)) for _ in range(2)]
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(state["peak_active"], 2)
        finally:
            executor.shutdown()

    def test_serial_executor_name_remains_compatible(self):
        self.assertIs(SerialTaskExecutor, ConcurrentTaskExecutor)

    def test_executor_can_be_configured_as_serial(self):
        executor = ConcurrentTaskExecutor(max_workers=1)
        state_lock = threading.Lock()
        state = {"active": 0, "peak_active": 0}

        def critical_work():
            with state_lock:
                state["active"] += 1
                state["peak_active"] = max(state["peak_active"], state["active"])
            try:
                time.sleep(0.05)
            finally:
                with state_lock:
                    state["active"] -= 1

        threads = [threading.Thread(target=lambda: executor.run(critical_work)) for _ in range(2)]
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(state["peak_active"], 1)
        finally:
            executor.shutdown()

    def test_exception_is_propagated_and_executor_remains_usable(self):
        executor = ConcurrentTaskExecutor(max_workers=2)

        def fail():
            raise ValueError("expected failure")

        try:
            with self.assertRaises(ValueError):
                executor.run(fail)
            self.assertEqual(executor.run(lambda: 42), 42)
        finally:
            executor.shutdown()


if __name__ == "__main__":
    unittest.main()
