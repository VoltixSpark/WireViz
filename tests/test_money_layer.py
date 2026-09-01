# -*- coding: utf-8 -*-
"""The money layer: what the drawing says a wire is, the BOM must bill.

WHY THIS FILE EXISTS

Production staff cut wire and order parts from this output. The dangerous
failure here is not a crash, it is a number that is quietly wrong on a document
somebody then works from. A 23.5 in conductor that bills as 47 in orders twice
the copper; a wire whose BOM amount vanishes orders none.

Every case below is a defect that actually shipped, listed in the review of
2026-08/09. They are written as INVARIANTS rather than as snapshots of known
output, deliberately:

A snapshot's failure mode is that somebody regenerates it. In this project an
assistant writes most of the code, and an assistant told to make the tests pass
will regenerate a golden file with a plausible commit message. That edit looks
like ordinary data churn in a diff. An invariant's failure mode is that somebody
deletes it, and a deleted test is one of the few things a reviewer never misses.

So the expected numbers live HERE, in the fixture, hand-verified and small
enough to read. There is no generated artifact to refresh, and changing an
expected value means editing a line that says what it means.
"""

import csv

import pytest
import yaml

import wireviz.wireviz as wv

# --------------------------------------------------------------------------- #
# One small harness, with the answer written next to the question.             #
# --------------------------------------------------------------------------- #

# A two-segment chain: 23.5 in of conductor running from X1 through a splice to
# X2. Production specifies the TOTAL and the covering length; the split between
# segments is decided on the bench, which is why total_length exists.
#
# Hand-verified expectations. Each wire is ONE physical conductor 23.5 in long,
# so each bills 23.5 in, once. Two wires, so 47 in of wire is purchased in
# total, but no single wire may ever bill 47.
MONEY_HARNESS = """
connectors:
  X1: {pincount: 2}
  X2: {pincount: 2}
cables:
  A:
    category: bundle
    gauge: 22 AWG
    colors: [YE, BK]
    wirelabels: [W1, W2]
    mpn: ["WIRE-YE", "WIRE-BK"]
    total_length: 23.5 in
  # Same gauge and same part numbers as A, so the splice joins ONE physical
  # conductor rather than two distinct parts. That is what licenses a single
  # total_length for the chain; when the parts differ the engine refuses,
  # because each part would take its own BOM line and bill the total again.
  B:
    category: bundle
    gauge: 22 AWG
    colors: [YE, BK]
    wirelabels: [W1, W2]
    mpn: ["WIRE-YE", "WIRE-BK"]
continuations:
- [A.W1, B.W1]
- [A.W2, B.W2]
connections:
- - X1: [1, 2]
  - A: [1, 2]
- - B: [1, 2]
  - X2: [1, 2]
"""

# label -> the one cut length that wire has, in inches. Read this table against
# the YAML above; it is the whole contract.
EXPECTED_CUT_LENGTH_IN = {
    "W1": 23.5,
    "W2": 23.5,
}


def _build(tmp_path, yaml_str, name="money"):
    """Render to TSV in tmp_path and hand back (harness, bom rows)."""
    harness = wv.parse(
        yaml.safe_load(yaml_str),
        output_formats=["tsv"],
        output_dir=str(tmp_path),
        output_name=name,
        return_types=("harness",),
    )
    with open(tmp_path / f"{name}.bom.tsv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    return harness, rows


def _drawing_totals(harness):
    """What each wire SHOWS on the diagram, keyed by label."""
    out = {}
    for cable in harness.cables.values():
        for wire in cable.wire_objects.values():
            total = wire.chain_total_length
            if total is not None:
                out.setdefault(str(wire.label), []).append(
                    (total.number, str(total.unit))
                )
    return out


def _explain(label, expected, actual):
    """Name the failure shape, so a red test says what went wrong.

    Double billing is the defect this suite exists for and it has a signature:
    an exact integer multiple of the true length, one multiple per distinct part
    in the continuation chain. Saying "2.00x" out loud turns a number mismatch
    into a diagnosis.
    """
    detail = f"{label}: expected {expected} in, got {actual} in"
    if expected and actual:
        ratio = actual / expected
        if abs(ratio - round(ratio)) < 1e-9 and round(ratio) >= 2:
            return (
                f"{detail}  ({ratio:.2f}x, DOUBLE-BILLING SIGNATURE: the chain "
                f"total is being billed once per part instead of once per wire)"
            )
        if actual < expected:
            return f"{detail}  (UNDER by {expected - actual:g} in; short wire)"
    return detail


# --------------------------------------------------------------------------- #
# Invariant 1: the drawing and the BOM agree, per wire.                        #
# --------------------------------------------------------------------------- #

def test_drawing_and_bom_agree_per_wire(tmp_path):
    """The number a technician cuts to is the number that was purchased.

    These are produced by different code paths (the graphviz table and the BOM
    aggregator), and they have disagreed: a jacketed cable using total_length
    drew 30 in and billed quantity 1.
    """
    harness, rows = _build(tmp_path, MONEY_HARNESS)

    drawing = _drawing_totals(harness)
    for label, expected in EXPECTED_CUT_LENGTH_IN.items():
        assert label in drawing, f"{label} shows no total on the drawing at all"
        for number, unit in drawing[label]:
            assert unit == "in", f"{label} drawn in {unit}, expected in"
            assert number == pytest.approx(expected), _explain(
                f"{label} (drawing)", expected, number
            )

    wire_rows = [r for r in rows if (r.get("MPN") or "").startswith("WIRE-")]
    assert wire_rows, "no wire rows in the BOM; the wires were not billed at all"

    for row in wire_rows:
        qty = float(row["Qty"])
        assert row["Unit"] == "in", f"{row['MPN']} billed in {row['Unit']}"
        assert qty == pytest.approx(23.5), _explain(
            f"{row['MPN']} (BOM)", 23.5, qty
        )


def test_a_wire_is_billed_exactly_once(tmp_path):
    """Total purchased equals the sum of the cut lengths. No more, no less.

    This is the invariant the 23.5-in-billed-as-47-in defect broke. It is stated
    over the WHOLE bom rather than per row, so splitting one row into two does
    not sneak past it.
    """
    _, rows = _build(tmp_path, MONEY_HARNESS)

    billed = sum(
        float(r["Qty"]) for r in rows if (r.get("MPN") or "").startswith("WIRE-")
    )
    expected = sum(EXPECTED_CUT_LENGTH_IN.values())
    assert billed == pytest.approx(expected), _explain(
        "total wire billed", expected, billed
    )


# The configuration that actually produced 47 in from a 23.5 in wire: a chain
# whose two segments are DISTINCT parts (different gauge here, so different BOM
# lines) while a single total is declared for the chain. Each part takes its own
# line, and each line billed the whole total.
#
# The fix is a refusal rather than a division, because there is no correct way
# to split a total the author never split: the engine cannot know how much of
# the 23.5 in is the 22 AWG segment. Guessing produces a confident wrong number
# on a cut sheet, which is the failure this whole file exists to prevent.
DISTINCT_PARTS_ONE_TOTAL = MONEY_HARNESS.replace(
    "  B:\n    category: bundle\n    gauge: 22 AWG",
    "  B:\n    category: bundle\n    gauge: 20 AWG",
)


def test_one_total_across_two_distinct_parts_is_refused(tmp_path):
    """Refuse to bill a chain total once per part. This is the 23.5 -> 47 defect.

    Kept separate from the merged-chain tests above on purpose: when the two
    segments are the same part they collapse to one BOM line, so that fixture
    CANNOT express double billing and cannot detect its return. Verified by
    mutation: neutering the guard in wv_harness leaves the merged tests green
    and turns this one red.
    """
    with pytest.raises(Exception) as excinfo:
        _build(tmp_path, DISTINCT_PARTS_ONE_TOTAL)

    message = str(excinfo.value)
    assert "total_length" in message, (
        f"refused, but without naming total_length, so the author is not told "
        f"which line to change: {message!r}"
    )
    assert "length:" in message, (
        f"refused without naming the fix (give each part its own length): "
        f"{message!r}"
    )


# --------------------------------------------------------------------------- #
# Invariant 2: units are never assumed.                                        #
# --------------------------------------------------------------------------- #

MIXED_UNITS = MONEY_HARNESS.replace(
    "    total_length: 23.5 in", "    length: 10 in"
).replace(
    "    colors: [YE, BK]\n    wirelabels: [W1, W2]\n    mpn: [\"WIRE-YE\", \"WIRE-BK\"]\ncontinuations:",
    "    colors: [YE, BK]\n    wirelabels: [W1, W2]\n    mpn: [\"WIRE-YE\", \"WIRE-BK\"]\n    length: 100 mm\ncontinuations:",
)


def test_mixed_units_never_silently_sum(tmp_path):
    """10 in + 100 mm must not report 110 in.

    Three separate code paths summed across a chain without comparing units.
    Raising is the correct outcome: there is no safe guess, and a wrong guess
    reaches a bench as a mis-cut wire.
    """
    with pytest.raises(Exception) as excinfo:
        _build(tmp_path, MIXED_UNITS)

    message = str(excinfo.value).lower()
    assert "unit" in message, (
        "mixed units raised, but the message does not mention units, so the "
        f"author cannot tell what to fix: {excinfo.value!r}"
    )


def test_every_bom_row_labels_its_own_unit(tmp_path):
    """A row must not carry a quantity in one unit labelled with another."""
    _, rows = _build(tmp_path, MONEY_HARNESS)
    for row in rows:
        qty, unit = row.get("Qty"), (row.get("Unit") or "").strip()
        if not qty:
            continue
        if float(qty) != int(float(qty)) and not unit:
            pytest.fail(
                f"row {row.get('Description')!r} bills {qty} with no unit. A "
                f"fractional quantity is a measurement, and a measurement "
                f"without a unit cannot be ordered."
            )


# --------------------------------------------------------------------------- #
# Invariant 3: bad input fails fast, and says so.                              #
# --------------------------------------------------------------------------- #

CYCLIC = """
connectors:
  X1: {pincount: 1}
  X2: {pincount: 1}
cables:
  A:
    category: bundle
    colors: [YE]
    wirelabels: [W1]
    length: 5 in
  B:
    category: bundle
    colors: [YE]
    wirelabels: [W1]
continuations:
- [A.W1, B.W1]
- [B.W1, A.W1]
connections:
- - X1: [1]
  - A: [1]
- - B: [1]
  - X2: [1]
"""


@pytest.mark.timeout(30)
def test_cyclic_continuations_raise_instead_of_hanging(tmp_path):
    """A cycle used to spin the parser forever.

    A hang is worse than a crash here: it presents as a stuck build or a CI job
    killed by the runner, so it gets read as infrastructure trouble rather than
    as a harness the author needs to fix. The timeout marker means this test
    fails in 30 seconds rather than joining the hang.
    """
    with pytest.raises(Exception) as excinfo:
        _build(tmp_path, CYCLIC)
    assert "cycl" in str(excinfo.value).lower() or "loop" in str(excinfo.value).lower(), (
        f"cycle detected but the error does not name the problem: {excinfo.value!r}"
    )


def test_a_wire_that_carries_a_length_always_reaches_the_bom(tmp_path):
    """No wire with a length may be absent from the BOM.

    A jacketed cable using total_length lost its amount entirely and billed as
    quantity 1. Stated as a presence check because "the row is missing" and "the
    row is wrong" are different bugs and only one of them is caught by comparing
    numbers.
    """
    harness, rows = _build(tmp_path, MONEY_HARNESS)

    billed_mpns = {(r.get("MPN") or "").strip() for r in rows}
    for cable in harness.cables.values():
        for wire in cable.wire_objects.values():
            if wire.chain_total_length is None:
                continue
            mpn = getattr(getattr(wire, "partnumbers", None), "mpn", None)
            if mpn:
                assert mpn in billed_mpns, (
                    f"wire {wire.label} is drawn with a cut length but its part "
                    f"{mpn!r} has no BOM row, so it would never be ordered"
                )
