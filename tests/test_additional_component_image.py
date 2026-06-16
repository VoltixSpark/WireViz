# -*- coding: utf-8 -*-
"""Regression test: additional-component images must resolve and embed.

A relative image src on an additional_component must be resolved against
image_paths (like a connector/cable image), or it silently fails to render when
the process cwd is not the project directory. See wireviz.parse().
"""

import base64
import os

import wireviz.wireviz as wv

# 1x1 PNG
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

_YAML = """
connectors:
  X1:
    pincount: 2
    additional_components:
      - type: Backshell
        pn: BS-1
        image: {src: parts-images/bs.png, width: 60, caption: backshellimg}
cables:
  W: {wirecount: 2, colors: [RD, BK]}
connections:
  - - X1: [1, 2]
    - W: [1, 2]
"""


def test_additional_component_image_embeds_from_foreign_cwd(tmp_path, monkeypatch):
    import yaml

    (tmp_path / "parts-images").mkdir()
    (tmp_path / "parts-images" / "bs.png").write_bytes(_PNG)
    out = tmp_path / "out"
    out.mkdir()

    # render from a cwd that is NOT the project, as the GUI/docgen does
    monkeypatch.chdir(tmp_path / "parts-images")

    wv.parse(
        yaml.safe_load(_YAML),
        output_formats=("svg",),
        output_dir=str(out),
        output_name="h",
        image_paths=[str(tmp_path), str(tmp_path / "parts-images")],
    )
    svg = (out / "h.svg").read_text(encoding="utf-8")
    assert "data:image/png" in svg, "additional-component image was not embedded"
    assert "backshellimg" in svg, "additional-component image caption missing"
