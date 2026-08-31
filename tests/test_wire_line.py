# -*- coding: utf-8 -*-
"""Regression tests for the bundle wire-info line.

Covers three things introduced/fixed when the wire line was reworked into
aligned columns:
  * the wire number and label are not duplicated when the label is just the
    number (e.g. numeric wirelabels -> "1", not "1 1"),
  * the per-wire connection-endpoint labels (e.g. "A:1") are gated by
    show_connection_labels (hidden by default),
  * the sleeve/jacket band spans the full wire-row width (its colspan tracks
    the wire-row cell count, not a hard-coded constant).
"""

import re

import wireviz.wireviz as wv


def _gv(tmp_path, yaml_str, name="t"):
    import yaml

    wv.parse(
        yaml.safe_load(yaml_str),
        output_formats=["gv"],
        output_dir=str(tmp_path),
        output_name=name,
    )
    return (tmp_path / f"{name}.gv").read_text(encoding="utf-8")


def test_numeric_label_not_duplicated(tmp_path):
    # non-bundle cable shows the wire number; numeric wirelabels must not double
    gv = _gv(
        tmp_path,
        """
        connectors: {A: {pincount: 3}, B: {pincount: 3}}
        cables:
          C1: {gauge: 24 AWG, colors: [RD, GN, BU], wirelabels: [1, 2, 3], length: 9 in}
        connections: [[{A: [1,2,3]}, {C1: [1,2,3]}, {B: [1,2,3]}]]
        """,
    )
    assert ">1 1<" not in gv and ">2 2<" not in gv, "wire number/label must not double"


def test_connection_labels_hidden_by_default(tmp_path):
    gv = _gv(
        tmp_path,
        """
        connectors: {A: {pincount: 2}, B: {pincount: 2}}
        cables: {C1: {gauge: 24 AWG, colors: [RD, BK], length: 5 in}}
        connections: [[{A: [1,2]}, {C1: [1,2]}, {B: [1,2]}]]
        """,
    )
    # endpoint labels render as "A:1" / "B:1" (designator:pin); hidden by default
    assert "A:1" not in gv and "B:1" not in gv


def test_connection_labels_shown_when_enabled(tmp_path):
    gv = _gv(
        tmp_path,
        """
        options: {show_connection_labels: true}
        connectors:
          A: {pincount: 2, pinlabels: [GND, VCC]}
          B: {pincount: 2}
        cables: {C1: {gauge: 24 AWG, colors: [RD, BK], length: 5 in}}
        connections: [[{A: [1,2]}, {C1: [1,2]}, {B: [1,2]}]]
        """,
    )
    # full mode includes the pin label
    assert "A:1:GND" in gv


def test_connection_labels_pin_mode_drops_label(tmp_path):
    gv = _gv(
        tmp_path,
        """
        options: {show_connection_labels: pin}
        connectors:
          A: {pincount: 2, pinlabels: [GND, VCC]}
          B: {pincount: 2}
        cables: {C1: {gauge: 24 AWG, colors: [RD, BK], length: 5 in}}
        connections: [[{A: [1,2]}, {C1: [1,2]}, {B: [1,2]}]]
        """,
    )
    # pin mode shows connector:pin but not the labeled endpoint ("A:1:GND").
    # (The bare label "GND" still appears in connector A's pinout table, which
    # is correct - that is the connector box, not the wire-row endpoint.)
    assert "A:1" in gv and "A:1:GND" not in gv


def test_sleeve_band_spans_full_wire_row(tmp_path):
    # the sleeve band colspan must equal the wire-row cell count (8 for a bundle
    # with BOM badges on, the default), not the old hard-coded 6. Was 9 until
    # the per-segment length column was dropped in favor of showing only each
    # wire's total cut length.
    gv = _gv(
        tmp_path,
        """
        connectors: {A: {pincount: 2}, B: {pincount: 2}}
        cables:
          B1:
            category: bundle
            gauge: 22 AWG
            colors: [RD, BK]
            length: 5 in
            sleeve: {color: BK, length: 5 in, pn: SLV1}
        connections: [[{A: [1,2]}, {B1: [1,2]}, {B: [1,2]}]]
        """,
    )
    colspans = set(re.findall(r'colspan="(\d+)"', gv))
    assert "8" in colspans, "band/wire-bar should span all 8 columns"
    assert "6" not in colspans, "stale hard-coded colspan=6 must be gone"


def test_uniform_gauge_header_only(tmp_path):
    # scalar gauge: shown in the bundle header, not repeated per wire
    gv = _gv(
        tmp_path,
        """
        connectors: {A: {pincount: 2}, B: {pincount: 2}}
        cables:
          B1: {category: bundle, colors: [RD, BK], wirelabels: [W1, W2], gauge: 22 AWG, length: 5 in}
        connections: [[{A: [1,2]}, {B1: [1,2]}, {B: [1,2]}]]
        """,
    )
    assert gv.count("22 AWG") == 1, "uniform gauge should appear once (header only)"


def test_per_wire_gauge_shown_when_differs(tmp_path):
    # list gauge: header shows the range, each wire shows its own gauge
    gv = _gv(
        tmp_path,
        """
        connectors: {A: {pincount: 2}, B: {pincount: 2}}
        cables:
          B1:
            category: bundle
            colors: [RD, BK]
            wirelabels: [W1, W2]
            gauge: [22 AWG, 24 AWG]
            length: 5 in
        connections: [[{A: [1,2]}, {B1: [1,2]}, {B: [1,2]}]]
        """,
    )
    assert "22 .. 24 AWG" in gv, "header should show the gauge range"
    assert ">22 AWG<" in gv and ">24 AWG<" in gv, "each wire should show its own gauge"
