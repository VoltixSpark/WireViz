# -*- coding: utf-8 -*-
"""Regression tests for legible wire color bands (D3).

Each wire in a cable/bundle is drawn as a vertical stack of GraphViz HTML cells:
a thin black separator, the color band(s), then a thin black separator. Two
properties keep similar colors (orange/brown, blue/black) distinguishable in
dense bundles:

1. The color bands are taller than the black separators, so the wire color
   dominates the line instead of being a thin stripe sandwiched by black.
2. A single-color wire always renders the full (3-band) color region, whether or
   not the harness happens to contain a multi-color wire, so thickness does not
   silently depend on unrelated wires.

We render the GraphViz source (`gv`) and inspect the cell attributes.
"""

import re

import wireviz.wireviz as wv

# A bundle of single-color wires only (RD = #ff0000, BU = #0000ff).
SINGLE = """
connectors:
  X1: {pincount: 2}
  X2: {pincount: 2}
cables:
  W:
    category: bundle
    gauge: 22 AWG
    length: 10 in
    colors: [RD, BU]
connections:
  - - X1: [1, 2]
    - W: [1, 2]
    - X2: [1, 2]
"""

# Same, plus a multi-color wire (GNYE) so the harness contains a striped wire.
MULTI = """
connectors:
  X1: {pincount: 3}
  X2: {pincount: 3}
cables:
  W:
    category: bundle
    gauge: 22 AWG
    length: 10 in
    colors: [RD, BU, GNYE]
connections:
  - - X1: [1, 2, 3]
    - W: [1, 2, 3]
    - X2: [1, 2, 3]
"""


def _gv(tmp_path, harness, name="t"):
    import yaml

    data = yaml.safe_load(harness)
    wv.parse(data, output_formats=["gv"], output_dir=str(tmp_path), output_name=name)
    with open(tmp_path / f"{name}.gv", encoding="utf-8") as f:
        return f.read()


def _count_color_bands(gv, hexcolor):
    """Color band cells carry the wire color as bgcolor at the band height (2)."""
    return len(re.findall(rf'bgcolor="{hexcolor}"[^>]*height="2"', gv, re.I))


def test_color_bands_taller_than_black_separators(tmp_path):
    gv = _gv(tmp_path, SINGLE)
    # color bands render at the band height (2)
    assert re.search(r'bgcolor="#ff0000"[^>]*height="2"', gv, re.I), \
        "wire color should render at the band height"
    # black separators render thin (1) so the color dominates the line
    assert re.search(r'bgcolor="#000000"[^>]*height="1"', gv, re.I), \
        "black wire separators should be 1pt so the color dominates the line"


def test_single_color_wire_has_consistent_three_bands(tmp_path):
    gv_single = _gv(tmp_path, SINGLE, "s")
    gv_multi = _gv(tmp_path, MULTI, "m")
    n_single = _count_color_bands(gv_single, "#ff0000")
    n_multi = _count_color_bands(gv_multi, "#ff0000")
    assert n_single == 3, \
        f"single-color wire should render 3 color bands, got {n_single}"
    assert n_multi == 3, \
        f"thickness must not depend on an unrelated multi-color wire, got {n_multi}"
