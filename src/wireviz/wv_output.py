# -*- coding: utf-8 -*-

import base64
import re
from importlib import resources
from pathlib import Path
from typing import Callable, Dict, List, Union

import wireviz  # for doing wireviz.__file__
from wireviz import APP_NAME, APP_URL, __version__
from wireviz.wv_dataclasses import Metadata, Options
from wireviz.wv_utils import (
    file_read_text,
    file_write_text,
    html_line_breaks,
    smart_file_resolve,
)

mime_subtype_replacements = {"jpg": "jpeg", "tif": "tiff"}

# GraphViz reserves each HTML-table cell's width using Arial metrics and bakes a
# fixed geometry into the SVG, but embeds no font (the SVG just declares
# font-family="arial"). Where Arial is absent (common in PDF export and on
# non-Windows viewers) the viewer substitutes a wider font, so rendered text is
# wider than the reserved cell and trailing glyphs spill past the cell border.
# Embedding Liberation Sans (a libre metric-clone of Arial, advance widths equal)
# and forcing the diagram text to resolve to it makes the rendered width match
# the width GraphViz already reserved, on every viewer.
_FONT_FACES = (
    # (font-family weight value, package-data filename)
    ("normal", "LiberationSans-Regular.woff2"),
    ("bold", "LiberationSans-Bold.woff2"),
)


def _font_b64(filename: str) -> Union[str, None]:
    """Return the base64 of a bundled font file, or None if it is missing.

    Missing font data must never crash a render, so callers degrade gracefully
    (skip the embed) when this returns None."""
    try:
        data = (resources.files("wireviz") / "fonts" / filename).read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return None
    return base64.b64encode(data).decode("ascii")


def build_font_style_block() -> str:
    """Build an SVG <style> block that embeds Liberation Sans via @font-face and
    forces the diagram text to use it.

    Returns "" if no font data could be loaded, so the SVG is still emitted
    (just without the embedded font) rather than failing."""
    faces = []
    for weight, filename in _FONT_FACES:
        b64 = _font_b64(filename)
        if b64 is None:
            continue
        faces.append(
            "@font-face{font-family:'Liberation Sans';"
            f"font-style:normal;font-weight:{'700' if weight == 'bold' else '400'};"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}"
        )
    if not faces:
        return ""
    # The !important rule wins over GraphViz's per-<text> font-family="arial"
    # presentation attribute. Arial stays as a fallback for the (rare) case the
    # embedded face fails to load.
    rule = "text{font-family:'Liberation Sans',Arial,sans-serif !important;}"
    return "<style>" + "".join(faces) + rule + "</style>"


def inject_svg_font_style(svg_in: str) -> str:
    """Insert the embedded-font <style> block right after the opening <svg> tag.

    No-op (returns the input unchanged) if the SVG has no opening tag or no font
    data is available."""
    style = build_font_style_block()
    if not style:
        return svg_in
    # already injected (e.g. SVG re-processed): do not double-insert
    if "'Liberation Sans'" in svg_in:
        return svg_in
    return re.sub(r"(<svg\b[^>]*>)", r"\1" + style, svg_in, count=1)


# TODO: Share cache and code between data_URI_base64() and embed_svg_images()
def data_URI_base64(file: Union[str, Path], media: str = "image") -> str:
    """Return Base64-encoded data URI of input file."""
    file = Path(file)
    b64 = base64.b64encode(file.read_bytes()).decode("utf-8")
    uri = f"data:{media}/{get_mime_subtype(file)};base64, {b64}"
    # print(f"data_URI_base64('{file}', '{media}') -> {len(uri)}-character URI")
    if len(uri) > 65535:
        print(
            "data_URI_base64(): Warning: Browsers might have different URI length limitations"
        )
    return uri


def embed_svg_images(svg_in: str, base_path: Union[str, Path] = Path.cwd()) -> str:
    images_b64 = {}  # cache of base64-encoded images

    def image_tag(pre: str, url: str, post: str) -> str:
        return f'<image{pre} xlink:href="{url}"{post}>'

    def replace(match: re.Match) -> str:
        imgurl = match["URL"]
        if not imgurl in images_b64:  # only encode/cache every unique URL once
            imgurl_abs = (Path(base_path) / imgurl).resolve()
            image = imgurl_abs.read_bytes()
            images_b64[imgurl] = base64.b64encode(image).decode("utf-8")
        return image_tag(
            match["PRE"] or "",
            f"data:image/{get_mime_subtype(imgurl)};base64, {images_b64[imgurl]}",
            match["POST"] or "",
        )

    pattern = re.compile(
        image_tag(r"(?P<PRE> [^>]*?)?", r'(?P<URL>[^"]*?)', r"(?P<POST> [^>]*?)?"),
        re.IGNORECASE,
    )
    svg_out = pattern.sub(replace, svg_in)
    # embed Liberation Sans so cell text stops overflowing borders on viewers
    # without Arial; degrades to a no-op if the bundled font is unavailable.
    return inject_svg_font_style(svg_out)


def get_mime_subtype(filename: Union[str, Path]) -> str:
    mime_subtype = Path(filename).suffix.lstrip(".").lower()
    if mime_subtype in mime_subtype_replacements:
        mime_subtype = mime_subtype_replacements[mime_subtype]
    return mime_subtype


def embed_svg_images_file(
    filename_in: Union[str, Path], overwrite: bool = True
) -> None:
    filename_in = Path(filename_in).resolve()
    filename_out = filename_in.with_suffix(".b64.svg")
    filename_out.write_text(  # TODO?: Verify xml encoding="utf-8" in SVG?
        embed_svg_images(filename_in.read_text(), filename_in.parent)
    )  # TODO: Use encoding="utf-8" in both read_text() and write_text()
    if overwrite:
        filename_out.replace(filename_in)


def generate_html_output(
    filename: Union[str, Path],
    bom: List[List[str]],
    metadata: Metadata,
    options: Options,
):
    # load HTML template
    templatename = metadata.get("template", {}).get("name")
    if templatename:
        # if relative path to template was provided,
        # check directory of YAML file first, fall back to built-in template directory
        templatefile = smart_file_resolve(
            f"{templatename}.html",
            [Path(filename).parent, Path(__file__).parent / "templates"],
        )
    else:
        # fall back to built-in simple template if no template was provided
        templatefile = Path(wireviz.__file__).parent / "templates/simple.html"

    html = file_read_text(templatefile)  # TODO?: Warn if unexpected meta charset?

    # embed SVG diagram (only if used)
    def svgdata() -> str:
        return re.sub(  # TODO?: Verify xml encoding="utf-8" in SVG?
            "^<[?]xml [^?>]*[?]>[^<]*<!DOCTYPE [^>]*>",
            "<!-- XML and DOCTYPE declarations from SVG file removed -->",
            file_read_text(f"{filename}.tmp.svg"),
            1,
        )

    # generate BOM table
    # generate BOM header (may be at the top or bottom of the table)
    bom_header_html = "  <tr>\n"
    for item in bom[0]:
        th_class = f"bom_col_{item.lower()}"
        bom_header_html = f'{bom_header_html}    <th class="{th_class}">{item}</th>\n'
    bom_header_html = f"{bom_header_html}  </tr>\n"

    # generate BOM contents
    bom_contents = []
    for row in bom[1:]:
        row_html = "  <tr>\n"
        for i, item in enumerate(row):
            td_class = f"bom_col_{bom[0][i].lower()}"
            row_html = f'{row_html}    <td class="{td_class}">{item if item is not None else ""}</td>\n'
        row_html = f"{row_html}  </tr>\n"
        bom_contents.append(row_html)

    bom_html = (
        '<table class="bom">\n' + bom_header_html + "".join(bom_contents) + "</table>\n"
    )
    bom_html_reversed = (
        '<table class="bom">\n'
        + "".join(list(reversed(bom_contents)))
        + bom_header_html
        + "</table>\n"
    )

    # prepare simple replacements
    replacements = {
        "<!-- %generator% -->": f"{APP_NAME} {__version__} - {APP_URL}",
        "<!-- %fontname% -->": options.fontname,
        "<!-- %bgcolor% -->": options.bgcolor.html,
        "<!-- %filename% -->": str(filename),
        "<!-- %filename_stem% -->": Path(filename).stem,
        "<!-- %bom% -->": bom_html,
        "<!-- %bom_reversed% -->": bom_html_reversed,
        "<!-- %sheet_current% -->": "1",  # TODO: handle multi-page documents
        "<!-- %sheet_total% -->": "1",  # TODO: handle multi-page documents
        "<!-- %template_sheetsize% -->": metadata.get("template", {}).get(
            "sheetsize", ""
        ),
    }

    def replacement_if_used(key: str, func: Callable[[], str]) -> None:
        """Append replacement only if used in html."""
        if key in html:
            replacements[key] = func()

    replacement_if_used("<!-- %diagram% -->", svgdata)
    replacement_if_used(
        "<!-- %diagram_png_b64% -->", lambda: data_URI_base64(f"{filename}.png")
    )

    # prepare metadata replacements
    if metadata:
        for item, contents in metadata.items():
            if isinstance(contents, (str, int, float)):
                replacements[f"<!-- %{item}% -->"] = html_line_breaks(str(contents))
            elif isinstance(contents, Dict):  # useful for authors, revisions
                for index, (category, entry) in enumerate(contents.items()):
                    if isinstance(entry, Dict):
                        replacements[f"<!-- %{item}_{index+1}% -->"] = str(category)
                        for entry_key, entry_value in entry.items():
                            replacements[
                                f"<!-- %{item}_{index+1}_{entry_key}% -->"
                            ] = html_line_breaks(str(entry_value))
                    elif isinstance(entry, (str, int, float)):
                        pass  # TODO?: replacements[f"<!-- %{item}_{category}% -->"] = html_line_breaks(str(entry))

    # perform replacements
    # regex replacement adapted from:
    # https://gist.github.com/bgusach/a967e0587d6e01e889fd1d776c5f3729

    # longer replacements first, just in case
    replacements_sorted = sorted(replacements, key=len, reverse=True)
    replacements_escaped = map(re.escape, replacements_sorted)
    pattern = re.compile("|".join(replacements_escaped))
    html = pattern.sub(lambda match: replacements[match.group(0)], html)

    file_write_text(f"{filename}.html", html)
