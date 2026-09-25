"""Turn every SVG diagram in docs/ into a PNG of exactly the same size.

    python tools/render_diagrams.py                 # all docs/*.svg
    python tools/render_diagrams.py docs/flowchart_3_transfer.svg

The SVGs come from ``banking_system.py --diagram docs`` and
``tools/make_flowcharts.py``.  Headless Chromium draws each one; its window is
made a little taller than the drawing (headless mode keeps a strip of the
window for browser chrome), and Pillow then crops the screenshot back to the
SVG's own width and height.

Needs: Chromium (or Chrome) and Pillow.  Set CHROME=/path/to/chrome if the
browser is not found automatically.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
EXTRA_HEIGHT = 88          # the strip headless Chromium keeps for itself


def find_chrome():
    """Return a Chromium/Chrome executable, or exit with a clear message."""
    candidates = [os.environ.get("CHROME", ""), "chromium", "chromium-browser",
                  "google-chrome", "chrome"]
    for name in candidates:
        if name and shutil.which(name):
            return shutil.which(name)
    for found in sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome")):
        return str(found)
    sys.exit("Chromium not found: install it or set CHROME=/path/to/chrome")


def svg_size(svg):
    """Width and height in pixels, read from the root <svg> element."""
    head = svg.read_text(encoding="utf-8")[:2000]
    width = re.search(r'width="(\d+)"', head)
    height = re.search(r'height="(\d+)"', head)
    if not (width and height):
        raise ValueError(f"{svg.name}: no pixel width/height on the <svg> element")
    return int(width.group(1)), int(height.group(1))


def render(svg, chrome, workdir):
    """Screenshot one SVG with Chromium and crop it to the drawing's size."""
    from PIL import Image

    width, height = svg_size(svg)
    page = Path(workdir) / (svg.stem + ".html")
    page.write_text("<html><body style='margin:0;background:#fff'>"
                    f"<img src='{svg.resolve().as_uri()}'></body></html>", encoding="utf-8")
    png = svg.with_suffix(".png")
    subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
                    "--hide-scrollbars", f"--window-size={width},{height + EXTRA_HEIGHT}",
                    f"--screenshot={png}", page.as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    with Image.open(png) as shot:
        shot.crop((0, 0, width, height)).save(png)
    print(f"{png.relative_to(ROOT)}  {width} x {height}")


def main(argv):
    svgs = [Path(a) for a in argv] or sorted(DOCS.glob("*.svg"))
    chrome = find_chrome()
    with tempfile.TemporaryDirectory() as workdir:
        for svg in svgs:
            render(svg.resolve(), chrome, workdir)


if __name__ == "__main__":
    main(sys.argv[1:])
