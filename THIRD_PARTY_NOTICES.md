# Third-Party Notices

This project (the VoltixSpark WireViz fork) bundles the following third-party
assets. Each is distributed under its own license, reproduced or referenced
below. These notices supplement, and do not override, the project LICENSE.

## Liberation Sans (bundled font)

- Files: `src/wireviz/fonts/LiberationSans-Regular.woff2`,
  `src/wireviz/fonts/LiberationSans-Bold.woff2`
- Version: liberation-fonts 2.1.5
- Source: https://github.com/liberationfonts/liberation-fonts (release 2.1.5,
  `liberation-fonts-ttf-2.1.5.tar.gz`)
- License: SIL Open Font License, Version 1.1 (OFL-1.1)
- Copyright: Digitized data copyright (c) 2010 Google Corporation with Reserved
  Font Arimo, Tinos and Cousine; Copyright (c) 2012 Red Hat, Inc. with Reserved
  Font Name Liberation.
- Full license text and authors: `src/wireviz/fonts/LICENSE` and
  `src/wireviz/fonts/AUTHORS` (copied verbatim from the upstream release).

The bundled woff2 files are Latin-subset, woff2-compressed conversions of the
upstream TrueType fonts; no glyph outlines were modified. They are embedded
into generated SVG output (via an `@font-face` data URI) so that diagram cell
text renders at Arial advance widths on viewers that lack Arial, preventing
text from overflowing the cell borders that GraphViz lays out using Arial
metrics.

The SIL Open Font License 1.1 permits bundling, embedding, and redistribution.
OFL-1.1 is a permissive font license and is compatible with this project's
GPLv3 distribution (the font is an aggregated data asset, not linked code).
