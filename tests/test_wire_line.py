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
        connectors: {A: {pincount: 2}, B: {pincount: 2}}
        cables: {C1: {gauge: 24 AWG, colors: [RD, BK], length: 5 in}}
        connections: [[{A: [1,2]}, {C1: [1,2]}, {B: [1,2]}]]
        """,
    )
    assert "A:1" in gv and "B:1" in gv


def test_sleeve_band_spans_full_wire_row(tmp_path):
    # the braid band colspan must equal the wire-row cell count (8 for a bundle
    # with BOM badges on, the default), not the old hard-coded 6.
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
