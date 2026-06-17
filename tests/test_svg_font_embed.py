# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
"""Regression tests: an Arial-metric font is embedded into the generated SVG.

GraphViz reserves each HTML-table cell's width using Arial metrics and bakes a
fixed geometry into the SVG, but embeds no font. On viewers without Arial
(common in PDF export and on non-Windows systems) a wider substitute font makes
cell text spill past the reserved cell border. The engine now embeds Liberation
Sans (a libre metric-clone of Arial) via @font-face and forces the diagram text
to resolve to it, so rendered width matches the reserved width everywhere.
"""

import wireviz.wireviz as wv
from wireviz.wv_output import (
    build_font_style_block,
    embed_svg_images,
    inject_svg_font_style,
)

HARNESS = """
connectors:
  C1:
    type: D-Sub
    subtype: "female, 15 pos, solder cup"
    pincount: 2
cables:
  W1:
    gauge: 22 AWG
    length: 10 in
    colors: [RD, BK]
connections:
  - - C1: [1, 2]
    - W1: [1, 2]
"""


def test_font_style_block_has_face_and_data_uri():
    s = build_font_style_block()
    assert "@font-face" in s
    assert "'Liberation Sans'" in s
    # base64 data URI with the woff2 media type and format hint
    assert "data:font/woff2;base64," in s
    assert "format('woff2')" in s
    # the override rule that wins over GraphViz's per-text font-family="arial"
    assert "text{font-family:'Liberation Sans',Arial,sans-serif !important;}" in s


def test_inject_is_idempotent():
    svg = '<svg width="1" height="1"><text>x</text></svg>'
    once = inject_svg_font_style(svg)
    assert "@font-face" in once
    assert once.index("<style>") > once.index("<svg")  # style follows the svg tag
    assert inject_svg_font_style(once) == once  # no double-insertion


def test_embed_svg_images_injects_font(tmp_path):
    out = embed_svg_images('<svg width="1"><text>x</text></svg>', tmp_path)
    assert "@font-face" in out and "'Liberation Sans'" in out


def test_rendered_svg_embeds_font(tmp_path):
    import yaml

    wv.parse(
        yaml.safe_load(HARNESS),
        output_formats=["svg"],
        output_dir=str(tmp_path),
        output_name="r",
    )
    svg = (tmp_path / "r.svg").read_text(encoding="utf-8")
    assert "@font-face" in svg
    assert "'Liberation Sans'" in svg
    assert "data:font/woff2;base64," in svg
    # the diagram text is forced to the embedded face
    assert "font-family:'Liberation Sans',Arial,sans-serif !important" in svg
