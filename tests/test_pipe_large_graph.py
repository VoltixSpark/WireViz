# -*- coding: utf-8 -*-
"""In-memory rendering must not deadlock on a large diagram.

THE DEFECT

`graphviz.Graph.pipe()` routes through graphviz.backend.execute._run_input_lines,
which writes every line of DOT source into the child's stdin in a blocking loop
and only calls communicate() once that loop finishes, while run_check has set
stdout=stderr=PIPE:

    popen = subprocess.Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    for line in input_lines:
        stdin_write(line)        # all of stdin, first
    stdout, stderr = popen.communicate()   # stdout drained only afterwards

Once dot has emitted enough output to fill the OS pipe buffer (64 KB on Windows,
similar on Linux) it blocks writing and stops consuming stdin. The parent is
still writing, the child is no longer reading, and the write fails:
BrokenPipeError, or a hang.

It is size and timing dependent, so it hid for a long time. Small harnesses
never produced enough output; file-based rendering goes through graph.render()
and never touches this path. It surfaced in the live GUI preview, on a worker
thread, once a harness gained a 37-pin connector.

WHAT THIS TEST DOES

Renders a harness whose SVG comfortably exceeds a pipe buffer, through the same
properties the app uses. If Harness._pipe is ever reverted to Graph.pipe(), this
is the test that has a chance of catching it.

Be honest about the limit: a race is not reliably reproducible, so a pass here
does not prove the absence of the bug. It proves the large-graph path works and
pins the output size, which is what makes the regression visible.
"""

import pytest
import yaml

import wireviz.wireviz as wv

# 64 KB is the Windows pipe buffer and the smallest of the common ones. Output
# must clear it by a real margin for the test to mean anything.
PIPE_BUFFER_BYTES = 64 * 1024

PIN_COUNT = 37  # the connector size that first exposed this in the field


def _big_harness_yaml(pins: int = PIN_COUNT) -> str:
    """A harness whose rendered SVG is far larger than one pipe buffer."""
    labels = [f"W{i}" for i in range(1, pins + 1)]
    colors = ["YE", "BK", "RD", "BU", "GN", "WH", "OG", "VT"]
    wire_colors = [colors[i % len(colors)] for i in range(pins)]
    pin_list = list(range(1, pins + 1))
    return f"""
connectors:
  J_DAQ:
    pincount: {pins}
    pinlabels: {[f"SIG{i}" for i in pin_list]}
  J_FIELD:
    pincount: {pins}
    pinlabels: {[f"FLD{i}" for i in pin_list]}
cables:
  W:
    category: bundle
    gauge: 24 AWG
    colors: {wire_colors}
    wirelabels: {labels}
    length: 36 in
connections:
- - J_DAQ: {pin_list}
  - W: {pin_list}
  - J_FIELD: {pin_list}
"""


@pytest.fixture(scope="module")
def big_harness():
    return wv.parse(
        yaml.safe_load(_big_harness_yaml()),
        return_types=("harness",),
        output_dir=".",
        output_name="big",
    )


def test_svg_of_a_large_graph_renders_in_memory(big_harness):
    """The property the live preview calls, on a graph big enough to matter."""
    svg = big_harness.svg

    assert svg.lstrip().startswith("<?xml") or "<svg" in svg[:2000], (
        "output does not look like an SVG document"
    )
    size = len(svg.encode("utf-8"))
    assert size > PIPE_BUFFER_BYTES, (
        f"the fixture rendered only {size} bytes, under the {PIPE_BUFFER_BYTES} "
        f"byte pipe buffer this test exists to exceed. Grow the harness, or the "
        f"test is no longer exercising the condition it claims to."
    )


def test_png_of_a_large_graph_renders_in_memory(big_harness):
    """The png property took the same unsafe path and needed the same fix."""
    png = big_harness.png
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "output is not a PNG"
    assert len(png) > 8192


def test_harness_does_not_use_the_unsafe_graphviz_entry_point():
    """Guard the fix itself, since the race cannot be reproduced on demand.

    A passing render is weak evidence: the deadlock is timing dependent and a
    green run does not prove it is gone. What CAN be asserted exactly is that
    the code no longer calls the method that carries the flaw.
    """
    import inspect

    from wireviz.wv_harness import Harness

    for name in ("png", "svg", "_pipe"):
        attr = getattr(Harness, name)
        func = attr.fget if isinstance(attr, property) else attr
        source = inspect.getsource(func)
        # Comments explaining the bug legitimately mention it; code must not.
        code = "\n".join(
            line for line in source.splitlines()
            if not line.strip().startswith("#")
        )
        assert ".pipe(format=" not in code, (
            f"Harness.{name} calls Graph.pipe(format=...) again. That routes "
            f"through graphviz's _run_input_lines, which writes all of stdin "
            f"before reading any stdout and deadlocks on a large diagram. Use "
            f"Harness._pipe, which passes the source as one buffer."
        )
