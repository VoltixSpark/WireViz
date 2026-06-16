# -*- coding: utf-8 -*-
"""Regression tests for first-class sleeve BOM support.

A nested `sleeve:` object on a cable/bundle must:
  * emit one BOM row carrying its part number / manufacturer,
  * aggregate by part number across cables (summed length),
while the legacy flat `sleeve_color` / `sleeve_length` keys must keep working and
must NOT add a BOM row (no part identity), exactly as before.
"""

import csv

import wireviz.wireviz as wv


def _bom_rows(tmp_path, yaml_str, name="t"):
    import yaml

    data = yaml.safe_load(yaml_str)
    wv.parse(
        data,
        output_formats=["tsv"],
        output_dir=str(tmp_path),
        output_name=name,
    )
    with open(tmp_path / f"{name}.bom.tsv", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def test_nested_sleeve_emits_bom_row_with_pn(tmp_path):
    rows = _bom_rows(
        tmp_path,
        """
        connectors:
          A: {pincount: 2}
          B: {pincount: 2}
        cables:
          W:
            category: bundle
            gauge: 22 AWG
            colors: [RD, BK]
            length: 10 in
            sleeve:
              color: BK
              length: 8 in
              pn: CCPO.125BK
              mpn: CCPO.125BK
              manufacturer: Techflex
        connections:
          - - A: [1, 2]
            - W: [1, 2]
            - B: [1, 2]
        """,
    )
    sleeve = [r for r in rows if r["P/N"] == "CCPO.125BK"]
    assert len(sleeve) == 1, "expected exactly one sleeve BOM row"
    assert sleeve[0]["Manufacturer"] == "Techflex"
    assert float(sleeve[0]["Qty"]) == 8.0
    assert sleeve[0]["Unit"] == "in"


def test_sleeve_length_aggregates_by_pn(tmp_path):
    rows = _bom_rows(
        tmp_path,
        """
        connectors:
          A: {pincount: 4}
          B: {pincount: 4}
        cables:
          W1:
            category: bundle
            gauge: 22 AWG
            colors: [RD, BK]
            length: 10 in
            sleeve: {color: BK, length: 8 in, pn: CCPO.125BK, manufacturer: Techflex}
          W2:
            category: bundle
            gauge: 22 AWG
            colors: [GN, BU]
            length: 6 in
            sleeve: {color: BK, length: 5 in, pn: CCPO.125BK, manufacturer: Techflex}
        connections:
          - - A: [1, 2]
            - W1: [1, 2]
            - B: [1, 2]
          - - A: [3, 4]
            - W2: [1, 2]
            - B: [3, 4]
        """,
    )
    sleeve = [r for r in rows if r["P/N"] == "CCPO.125BK"]
    assert len(sleeve) == 1, "same-PN sleeves must collapse to one row"
    assert float(sleeve[0]["Qty"]) == 13.0  # 8 + 5


def test_flat_sleeve_fields_add_no_bom_row(tmp_path):
    rows = _bom_rows(
        tmp_path,
        """
        connectors:
          A: {pincount: 2}
          B: {pincount: 2}
        cables:
          W:
            category: bundle
            gauge: 22 AWG
            colors: [WH, YE]
            length: 4 in
            sleeve_color: BK
            sleeve_length: 3 in
        connections:
          - - A: [1, 2]
            - W: [1, 2]
            - B: [1, 2]
        """,
    )
    assert not [
        r for r in rows if "sleev" in r["Description"].lower()
    ], "flat sleeve fields (no PN) must not create a BOM row"
