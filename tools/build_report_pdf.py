"""Build docs/Design_Report.pdf from docs/Design_Report.md.

    python tools/build_report_pdf.py

The Markdown is converted to HTML (each ``##`` section starts on a new A4
page) and headless Chromium prints it to PDF.  Needs the ``markdown``
package (pip install markdown) and Chromium; set CHROME=/path/to/chrome if it
is not found automatically.
"""
import subprocess
import sys
from pathlib import Path

import markdown

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_diagrams import find_chrome  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "Design_Report.md"
TARGET = ROOT / "docs" / "Design_Report.pdf"

CSS = """@page{size:A4;margin:18mm 16mm}
body{font-family:Calibri,Carlito,Arial,sans-serif;font-size:10pt;line-height:1.38;color:#1d2b3a}
h1{font-size:21pt;color:#1d3b5a;margin:0 0 6pt}
h2{font-size:15pt;color:#1d3b5a;margin-top:0;border-bottom:1.5px solid #1d3b5a;padding-bottom:3pt}
h2.sec{page-break-before:always}h3{font-size:12pt;color:#2e5475}
table{border-collapse:collapse;width:100%;margin:6pt 0;page-break-inside:auto}tr{page-break-inside:avoid}
th,td{border:1px solid #9aa9b8;padding:3pt 5pt;vertical-align:top;font-size:8.6pt;text-align:left}
th{background:#dde7f0}code{font-family:Consolas,'DejaVu Sans Mono',monospace;font-size:8.6pt}
pre{background:#f3f5f7;padding:6pt;font-size:8.6pt;white-space:pre-wrap}
img{max-width:100%;max-height:235mm;display:block;margin:4pt auto;page-break-inside:avoid}
p{margin:4pt 0}hr{display:none}"""


def main():
    body = markdown.markdown(SOURCE.read_text(encoding="utf-8"),
                             extensions=["tables", "fenced_code"])
    body = body.replace("<h2>", '<h2 class="sec">')
    page = SOURCE.with_name("_report.html")          # next to the .md so images resolve
    page.write_text('<html><head><meta charset="utf-8"><title>Problem 4 Design Report</title>'
                    f"<style>{CSS}</style></head><body>{body}</body></html>", encoding="utf-8")
    try:
        subprocess.run([find_chrome(), "--headless=new", "--no-sandbox", "--disable-gpu",
                        "--no-pdf-header-footer", f"--print-to-pdf={TARGET}", page.as_uri()],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    finally:
        page.unlink(missing_ok=True)
    print(f"written {TARGET.relative_to(ROOT)} ({TARGET.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
