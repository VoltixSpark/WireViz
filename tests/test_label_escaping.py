# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
"""Regression tests: XML special characters in user-supplied label text.

A literal `&`, `<`, or `>` in a connector/cable type, subtype, notes, an
additional-component description, or a pin label used to make GraphViz fail the
ENTIRE render with "not well-formed (invalid token)", because the text was
dropped raw into a GraphViz HTML-like label. The text must now be escaped
(`&` -> `&amp;`, `<` -> `&lt;`, `>` -> `&gt;`) so the render succeeds and the
characters survive as literals.
"""

import wireviz.wireviz as wv
from wireviz.wv_utils import escape_xml, html_line_breaks

HARNESS = """
connectors:
  C1:
    type: D-Sub
    subtype: "gold cup & flat spade <x>"
    pincount: 2
    notes: "a & b < c > d"
    additional_components:
      - type: "Backshell <A&B>"
        qty: 1
  J1:
    pincount: 2
cables:
  W1:
    gauge: 22 AWG
    length: 10 in
    colors: [RD, BK]
connections:
  - - C1: [1, 2]
    - W1: [1, 2]
    - J1: [1, 2]
"""


def _render(tmp_path, fmts, name="t"):
    import yaml

    data = yaml.safe_load(HARNESS)
    wv.parse(
        data,
        output_formats=fmts,
        output_dir=str(tmp_path),
        output_name=name,
    )
    return tmp_path / name


def test_escape_xml_amp_first_no_double_escape():
    # & must be escaped first so the & we introduce for < / > is not re-escaped.
    assert escape_xml("a & b < c > d") == "a &amp; b &lt; c &gt; d"


def test_escape_xml_is_idempotent_for_existing_entities():
    # Text pre-escaped to dodge the old crash must not be double-escaped.
    assert escape_xml("gold cup &amp; flat spade") == "gold cup &amp; flat spade"
    assert escape_xml("&lt;") == "&lt;"  # already a valid entity, left alone
    assert escape_xml("&gt;") == "&gt;"
    assert escape_xml("deg &#176; C") == "deg &#176; C"  # numeric entity preserved
    # running escape twice yields the same result as running it once
    once = escape_xml("a & b &amp; c < d")
    assert escape_xml(once) == once
    # a bare & that is not part of an entity is still escaped
    assert escape_xml("Q&A") == "Q&amp;A"


def test_escape_xml_passes_non_strings_through():
    assert escape_xml(7) == 7
    assert escape_xml(None) is None


def test_html_line_breaks_escapes_then_inserts_br():
    # The structural <br /> tag we add survives; the literal specials are escaped.
    out = html_line_breaks("a & b\n< c >")
    assert "<br />" in out
    assert "&amp;" in out
    assert "&lt; c &gt;" in out
    # the inserted <br /> must NOT have been escaped into &lt;br /&gt;
    assert "&lt;br" not in out


def test_render_to_gv_does_not_crash_and_escapes(tmp_path):
    out = _render(tmp_path, ["gv"])
    gv = (out.parent / f"{out.name}.gv").read_text(encoding="utf-8")
    # escaped forms present, raw specials in the user text are gone
    assert "&amp;" in gv
    assert "&lt;" in gv
    assert "&gt;" in gv


def test_render_to_svg_does_not_crash(tmp_path):
    # The whole point: rendering to SVG used to raise from GraphViz with
    # "not well-formed (invalid token)". It must now succeed.
    _render(tmp_path, ["svg"])
    assert (tmp_path / "t.svg").exists()
