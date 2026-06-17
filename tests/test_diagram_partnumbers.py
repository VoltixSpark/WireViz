# -*- coding: utf-8 -*-
"""Regression tests for the `show_part_numbers` diagram option.

The diagram boxes should declutter for production: by default, part-number text
(P/N, MPN, manufacturer, SPN) is suppressed inside connector / cable / wire /
sleeve / crimp boxes, while the production-relevant fields (color, gauge,
length, pinout) stay. Setting `show_part_numbers: true` restores the in-box
part numbers. Full part-number detail always remains in the BOM.

We render the GraphViz source (`gv`) and inspect its text: the HTML node labels
carry the box contents, so PN strings appear there iff they are rendered.
"""

import wireviz.wireviz as wv

# A harness whose connector, cable, individual wire, sleeve, and crimp sub-item
# all carry part-number info, plus lengths/gauges/colors that must survive.
HARNESS = """
{options}
connectors:
  X1:
    pincount: 2
    manufacturer: ConnCo
    mpn: CONN-2P
    pn: PN-X1
    additional_components:
      - type: Crimp pin
        qty_multiplier: populated
        manufacturer: CrimpCo
        mpn: CRIMP-22
  X2:
    pincount: 2
cables:
  W:
    category: bundle
    gauge: 22 AWG
    length: 10 in
    colors: [RD, BK]
    manufacturer: WireCo
    mpn: WIRE-22
    pn: PN-W
    sleeve:
      color: BK
      length: 10 in
      pn: SLV-PN
      mpn: SLV-MPN
      manufacturer: Techflex
connections:
  - - X1: [1, 2]
    - W: [1, 2]
    - X2: [1, 2]
"""

PN_TOKENS = ["PN-X1", "CONN-2P", "ConnCo", "PN-W", "WIRE-22", "WireCo",
             "SLV-PN", "SLV-MPN", "Techflex", "CRIMP-22", "CrimpCo"]
KEEP_TOKENS = ["10 in", "22 AWG", "Braid", "Crimp pin"]


def _gv_text(tmp_path, options_block, name="t"):
    import yaml

    data = yaml.safe_load(HARNESS.format(options=options_block))
    wv.parse(
        data,
        output_formats=["gv"],
        output_dir=str(tmp_path),
        output_name=name,
    )
    with open(tmp_path / f"{name}.gv", encoding="utf-8") as f:
        return f.read()


def test_part_numbers_hidden_by_default(tmp_path):
    gv = _gv_text(tmp_path, "")  # no options block -> default
    for token in PN_TOKENS:
        assert token not in gv, f"part-number token {token!r} should be hidden by default"
    # production-relevant fields must still be present
    for token in KEEP_TOKENS:
        assert token in gv, f"expected {token!r} to remain in the diagram"


def test_part_numbers_shown_when_opted_in(tmp_path):
    gv = _gv_text(tmp_path, "options: {show_part_numbers: true}\n")
    for token in PN_TOKENS:
        assert token in gv, f"part-number token {token!r} should appear when opted in"
    for token in KEEP_TOKENS:
        assert token in gv, f"expected {token!r} to remain in the diagram"
