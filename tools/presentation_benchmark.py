"""Mesures reproductibles du coût de la projection de présentation."""

import json
from statistics import median
from time import perf_counter
import tracemalloc

from core.presentation import PresentationProjector, snapshot_delta


def benchmark_presentation(engine, *, iterations=5):
    """Mesure projection, sérialisation et delta sans avancer le moteur."""
    if type(iterations) is not int or not 1 <= iterations <= 100:
        raise ValueError("iterations must be between 1 and 100")

    latency_tracing_active = tracemalloc.is_tracing()
    owns_trace = not latency_tracing_active
    if owns_trace:
        tracemalloc.start()
    try:
        PresentationProjector(engine).snapshot(revision=0)
        _, peak_memory_bytes = tracemalloc.get_traced_memory()
    finally:
        if owns_trace:
            tracemalloc.stop()

    previous = PresentationProjector(engine).snapshot(revision=0)
    projection_ms = []
    serialization_ms = []
    delta_ms = []
    pipeline_ms = []
    encoded = b""
    for revision in range(1, iterations + 1):
        started = perf_counter()
        current = PresentationProjector(engine).snapshot(revision=revision)
        projection_ms.append((perf_counter() - started) * 1000.0)

        started = perf_counter()
        encoded = json.dumps(
            current,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        serialization_ms.append((perf_counter() - started) * 1000.0)

        started = perf_counter()
        snapshot_delta(previous, current)
        delta_ms.append((perf_counter() - started) * 1000.0)
        pipeline_ms.append(
            projection_ms[-1] + serialization_ms[-1] + delta_ms[-1]
        )
        previous = current

    return {
        "iterations": iterations,
        "cells": int(engine.world["width"]) * int(engine.world["height"]),
        "snapshot_bytes": len(encoded),
        "projection": _durations(projection_ms),
        "serialization": _durations(serialization_ms),
        "delta": _durations(delta_ms),
        "pipeline": _durations(pipeline_ms),
        "peak_memory_bytes": peak_memory_bytes,
        "latency_tracing_active": latency_tracing_active,
    }


def _durations(values):
    return {
        "median_ms": median(values),
        "maximum_ms": max(values),
    }
