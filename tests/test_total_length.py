# -*- coding: utf-8 -*-
"""Tests for per-wire total cut length (`total_length:`) and its display.

Production reads one number per wire: the total cut length of the whole
physical conductor, shown on every segment box it passes through. Two
authoring styles produce it:
  * legacy, no `total_length:` anywhere -> sum each segment's own `length:`,
  * `total_length:` declared once in a chain -> that value IS the total, and
    every cable in the chain omits `length:`.
Mixing the two, or declaring a total twice in one chain, is a hard error.
"""

import re

import pytest
import yaml

import wireviz.wireviz as wv

CHAIN = """
connectors:
  X1: {{pincount: 2}}
  X2: {{pincount: 2}}
cables:
  A:
    category: bundle
    gauge: 22 AWG
    colors: [YE, BK]
    wirelabels: [W1, W2]
    mpn: ["M1", "M2"]
{a}
  B:
    category: bundle
    colors: [YE, BK]
    wirelabels: [W1, W2]
{b}
continuations:
- [A.W1, B.W1]
- [A.W2, B.W2]
connections:
- - X1: [1, 2]
  - A: [1, 2]
- - B: [1, 2]
  - X2: [1, 2]
"""


def _harness(a="", b=""):
    return wv.parse(
        yaml.safe_load(CHAIN.format(a=a, b=b)),
        return_types=("harness",),
        output_dir=".",
        output_name="t",
    )


def _totals(h):
    return {
        f"{cn}.{w.label}": w.chain_total_length
        for cn, c in h.cables.items()
        for w in c.wire_objects.values()
    }


def _wire_bom_qty(h):
    return sorted(
        v["qty"] for bh, v in h.bom.items() if bh.partnumbers and bh.partnumbers.mpn
    )


def test_legacy_sum_unchanged():
    # no total_length anywhere: the chain total stays the sum of segments
    h = _harness("    length: 10 in", "    length: 5 in")
    assert all(t.number == 15 for t in _totals(h).values())
    assert _wire_bom_qty(h) == [15, 15]


def test_declared_total_on_head():
    h = _harness("    total_length: 23.5 in", "")
    assert all(t.number == 23.5 for t in _totals(h).values())
    assert _wire_bom_qty(h) == [23.5, 23.5]


def test_declared_total_on_tail_still_reaches_bom():
    # the BOM entry is created on the HEAD wire, but the total may be declared
    # on any segment; the head must still pick it up via the chain.
    h = _harness("", "    total_length: 23.5 in")
    assert all(t.number == 23.5 for t in _totals(h).values())
    assert _wire_bom_qty(h) == [23.5, 23.5]


def test_declared_total_per_wire_list():
    h = _harness("    total_length: [23.5 in, 24 in]", "")
    totals = _totals(h)
    assert totals["A.W1"].number == 23.5
    assert totals["B.W1"].number == 23.5
    assert totals["A.W2"].number == 24
    assert _wire_bom_qty(h) == [23.5, 24]


def test_length_free_segment_reports_chain_total_not_none():
    # regression: chain_total_length used to return None for any segment that
    # carried no length of its own, which crashed the renderer.
    h = _harness("    length: 10 in", "")
    assert _totals(h)["B.W1"].number == 10


def test_mixing_total_length_and_length_is_an_error():
    with pytest.raises(Exception) as e:
        _harness("    total_length: 23.5 in", "    length: 5 in")
    msg = str(e.value)
    assert "total_length" in msg and "length" in msg
    # the message must name both offending cables so the fix is obvious
    assert "'A'" in msg and "'B'" in msg


def test_declaring_total_twice_in_one_chain_is_an_error():
    with pytest.raises(Exception) as e:
        _harness("    total_length: 23.5 in", "    total_length: 9 in")
    assert "more than once" in str(e.value)


def test_total_shown_on_every_segment_and_segment_length_is_not(tmp_path):
    # the total appears in each box the wire passes through; the per-segment
    # length column is gone entirely.
    wv.parse(
        yaml.safe_load(CHAIN.format(a="    total_length: 23.5 in", b="")),
        output_formats=["gv"],
        output_dir=str(tmp_path),
        output_name="t",
    )
    gv = (tmp_path / "t.gv").read_text(encoding="utf-8")
    assert len(re.findall(r"23\.5 in total", gv)) >= 4  # 2 wires x 2 segments


def test_single_segment_bundle_shows_its_total(tmp_path):
    # a plain bundle with no continuations now also states its cut length,
    # which it previously only did when per-wire lengths differed.
    wv.parse(
        yaml.safe_load(
            """
            connectors: {A: {pincount: 2}, B: {pincount: 2}}
            cables:
              B1:
                category: bundle
                gauge: 22 AWG
                colors: [RD, BK]
                length: 23 in
            connections: [[{A: [1,2]}, {B1: [1,2]}, {B: [1,2]}]]
            """
        ),
        output_formats=["gv"],
        output_dir=str(tmp_path),
        output_name="s",
    )
    gv = (tmp_path / "s.gv").read_text(encoding="utf-8")
    assert "23 in total" in gv


# --- regressions from the code review of the total_length/covering commit ---

MIXED = """
connectors:
  X1: {{pincount: 1}}
  X2: {{pincount: 1}}
cables:
  A:
    category: bundle
    gauge: 22 AWG
    colors: [YE]
    wirelabels: [W1]
    mpn: ["M1"]
{a}
  B:
    category: bundle
    colors: [YE]
    wirelabels: [W1]
{b}
continuations:
- [A.W1, B.W1]
connections:
- - X1: [1]
  - A: [1]
- - B: [1]
  - X2: [1]
"""


def test_distinct_part_in_chain_rejects_declared_total():
    # B has its own gauge + PN, so it does not merge into A and would get its
    # own BOM line; without this guard both lines billed the full total.
    with pytest.raises(Exception) as e:
        wv.parse(
            yaml.safe_load(
                MIXED.format(
                    a="    total_length: 23.5 in",
                    b='    gauge: 24 AWG\n    mpn: ["M2"]',
                )
            ),
            return_types=("harness",),
            output_dir=".",
            output_name="t",
        )
    assert "distinct part" in str(e.value)


def test_single_cable_cannot_set_both_length_and_total_length():
    # no continuations at all: the chain guard never runs, so Cable must reject it
    with pytest.raises(Exception) as e:
        wv.parse(
            yaml.safe_load(
                """
                connectors: {A: {pincount: 1}, B: {pincount: 1}}
                cables:
                  W1:
                    category: bundle
                    colors: [RD]
                    length: 10 in
                    total_length: 23.5 in
                connections: [[{A: [1]}, {W1: [1]}, {B: [1]}]]
                """
            ),
            return_types=("harness",),
            output_dir=".",
            output_name="t",
        )
    assert "both 'length' and 'total_length'" in str(e.value)


def test_non_bundle_cable_with_total_length_keeps_its_bom_amount():
    h = wv.parse(
        yaml.safe_load(
            """
            connectors: {A: {pincount: 1}, B: {pincount: 1}}
            cables:
              C1:
                wirecount: 1
                colors: [RD]
                mpn: CAB1
                total_length: 30 in
            connections: [[{A: [1]}, {C1: [1]}, {B: [1]}]]
            """
        ),
        return_types=("harness",),
        output_dir=".",
        output_name="t",
    )
    rows = [
        (v["qty"], bh.qty_unit)
        for bh, v in h.bom.items()
        if bh.partnumbers and bh.partnumbers.mpn == "CAB1"
    ]
    assert rows == [(30, "in")]


def test_qty_multiplier_length_works_without_a_segment_length():
    h = wv.parse(
        yaml.safe_load(
            """
            connectors: {A: {pincount: 1}, B: {pincount: 1}}
            cables:
              W1:
                category: bundle
                colors: [RD]
                total_length: 23.5 in
                additional_components:
                  - type: Sleeve
                    qty_multiplier: LENGTH
            connections: [[{A: [1]}, {W1: [1]}, {B: [1]}]]
            """
        ),
        return_types=("harness",),
        output_dir=".",
        output_name="t",
    )
    sub = h.cables["W1"].additional_components[0]
    assert sub.amount_computed.number == 23.5
    assert sub.amount_computed.unit == "in"


@pytest.mark.parametrize("bad", [1, True, "woven"])
def test_bad_sleeve_covering_gives_a_readable_error(bad):
    with pytest.raises(Exception) as e:
        wv.parse(
            yaml.safe_load(
                f"""
                connectors: {{A: {{pincount: 1}}, B: {{pincount: 1}}}}
                cables:
                  W1:
                    category: bundle
                    colors: [RD]
                    length: 5 in
                    sleeve: {{color: BK, length: 5 in, covering: {bad}}}
                connections: [[{{A: [1]}}, {{W1: [1]}}, {{B: [1]}}]]
                """
            ),
            return_types=("harness",),
            output_dir=".",
            output_name="t",
        )
    assert "braid" in str(e.value) and "heatshrink" in str(e.value)


def test_cyclic_continuation_raises_instead_of_hanging():
    with pytest.raises(Exception) as e:
        wv.parse(
            yaml.safe_load(
                """
                connectors: {X1: {pincount: 1}, X2: {pincount: 1}}
                cables:
                  A: {category: bundle, colors: [YE], wirelabels: [W1], length: 5 in}
                  B: {category: bundle, colors: [YE], wirelabels: [W1], length: 5 in}
                continuations:
                - [A.W1, B.W1]
                - [B.W1, A.W1]
                connections:
                - - X1: [1]
                  - A: [1]
                - - B: [1]
                  - X2: [1]
                """
            ),
            return_types=("harness",),
            output_dir=".",
            output_name="t",
        )
    assert "cyclic" in str(e.value)
