import unittest
from unittest import mock

from core.culture import load_config
from core.random_service import RandomService
from core.simulation_engine import SimulationEngine


class PresentationBenchmarkTests(unittest.TestCase):
    def test_benchmark_reports_projection_serialization_delta_and_memory(self):
        from tools.presentation_benchmark import benchmark_presentation

        config = load_config("template.json")
        RandomService.initialize(1850)
        engine = SimulationEngine.create(config, 1850, 8, 4)
        before = RandomService.get_state()

        report = benchmark_presentation(engine, iterations=3)

        self.assertEqual(report["iterations"], 3)
        self.assertEqual(report["cells"], 32)
        self.assertGreater(report["snapshot_bytes"], 0)
        self.assertGreaterEqual(report["projection"]["median_ms"], 0.0)
        self.assertGreaterEqual(report["serialization"]["median_ms"], 0.0)
        self.assertGreaterEqual(report["delta"]["median_ms"], 0.0)
        self.assertGreaterEqual(report["pipeline"]["median_ms"], 0.0)
        self.assertGreaterEqual(
            report["pipeline"]["maximum_ms"],
            report["projection"]["maximum_ms"],
        )
        self.assertGreater(report["peak_memory_bytes"], 0)
        self.assertEqual(RandomService.get_state(), before)

    def test_benchmark_rejects_invalid_iteration_budgets(self):
        from tools.presentation_benchmark import benchmark_presentation

        for value in (0, -1, True, 101):
            with self.subTest(iterations=value):
                with self.assertRaises(ValueError):
                    benchmark_presentation(object(), iterations=value)

    def test_memory_tracing_stops_before_latency_is_measured(self):
        import tools.presentation_benchmark as benchmark

        events = []
        projector_type = benchmark.PresentationProjector

        class TrackedProjector:
            def __init__(self, engine):
                self._projector = projector_type(engine)

            def snapshot(self, *, revision):
                events.append("snapshot")
                return self._projector.snapshot(revision=revision)

        config = load_config("template.json")
        RandomService.initialize(1851)
        engine = SimulationEngine.create(config, 1851, 8, 4)
        with (
            mock.patch.object(
                benchmark.tracemalloc, "is_tracing", return_value=False,
            ),
            mock.patch.object(
                benchmark.tracemalloc,
                "start",
                side_effect=lambda: events.append("trace-start"),
            ),
            mock.patch.object(
                benchmark.tracemalloc,
                "get_traced_memory",
                return_value=(64, 128),
            ),
            mock.patch.object(
                benchmark.tracemalloc,
                "stop",
                side_effect=lambda: events.append("trace-stop"),
            ),
            mock.patch.object(benchmark, "PresentationProjector", TrackedProjector),
        ):
            report = benchmark.benchmark_presentation(engine, iterations=1)

        self.assertEqual(report["peak_memory_bytes"], 128)
        self.assertFalse(report["latency_tracing_active"])
        snapshot_events = [
            index for index, event in enumerate(events) if event == "snapshot"
        ]
        self.assertGreaterEqual(len(snapshot_events), 2)
        self.assertLess(events.index("trace-stop"), snapshot_events[1])


if __name__ == "__main__":
    unittest.main()
