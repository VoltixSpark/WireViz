# -*- coding: utf-8 -*-
"""Regression tests for the `show_bom_references` BOM-bubble option.

Each diagram box may carry a small rounded badge with the item's BOM line
number (its `#` in the BOM table), so a connector / cable / wire / crimp box
can be cross-referenced to the BOM. Badges are on by default and gated by the
`show_bom_references` option. The rounded outline lives on the <table>
(GraphViz only honors STYLE="ROUNDED" there, not on a <td>).
"""

import wireviz.wireviz as wv
from wireviz.wv_graphviz import bom_bubble

# Rounded outline must be on the <table>, not the <td>.
ROUNDED_MARKER = 'style="rounded"'

HARNESS = """
{options}
connectors:
  X1:
    pincount: 2
  X2:
    pincount: 2
cables:
  W1:
    gauge: 22 AWG
    length: 10 in
    colors: [RD, BK]
connections:
  - - X1: [1, 2]
    - W1: [1, 2]
    - X2: [1, 2]
"""


def _gv_text(tmp_path, options_block, name="t"):
    import yaml

    data = yaml.safe_load(HARNESS.format(options=options_block))
    wv.parse(
        data,
        output_formats=["gv"],
        output_dir=str(tmp_path),
        output_name=name,
    )
    return (tmp_path / f"{name}.gv").read_text(encoding="utf-8")


def test_bom_bubble_renders_number_with_rounded_table():
    tbl = bom_bubble(3)
    assert tbl is not None
    s = str(tbl)
    assert "3" in s
    assert ROUNDED_MARKER in s  # rounded outline on the table, not the td
    assert "<td" in s and ROUNDED_MARKER not in s.split("<td", 1)[1]


def test_bom_bubble_none_for_missing_id():
    assert bom_bubble(None) is None


def test_references_shown_by_default(tmp_path):
    gv = _gv_text(tmp_path, "")  # no options -> default
    assert ROUNDED_MARKER in gv, "BOM-reference badges should render by default"


def test_references_hidden_when_disabled(tmp_path):
    gv = _gv_text(tmp_path, "options: {show_bom_references: false}\n")
    assert ROUNDED_MARKER not in gv, "no badges when show_bom_references is false"


def test_legacy_mini_bom_mode_still_accepted(tmp_path):
    # The deprecated option must not raise (Options(**...) would otherwise fail).
    gv = _gv_text(tmp_path, "options: {mini_bom_mode: false}\n")
    assert ROUNDED_MARKER in gv, "mini_bom_mode is a no-op; badges still default on"
