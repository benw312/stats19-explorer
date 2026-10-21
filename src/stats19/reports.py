"""Render print pages to PDF with headless Chromium (PLAN-004 phase 4.4).

The web app has /print/... routes that lay out a report with the same components as
the screen. They set ``window.__reportReady = true`` once the data and the map
have rendered, or ``window.__reportError`` if something failed. This module loads
such a page and prints it.
"""

from __future__ import annotations

import logging
import threading

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

log = logging.getLogger(__name__)

# Chromium is memory-hungry; on the home-lab box, two renders at once is plenty.
_RENDER_SLOTS = threading.BoundedSemaphore(2)
_CHROMIUM_ARGS = [
    # software WebGL so MapLibre renders without a GPU (containers, servers)
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
]

# Lay the page out at the A4 portrait *content* width (210 mm - 2 x 12 mm margins, at
# 96 px/in). Chromium draws WebGL maps at screen layout size and doesn't redraw them
# when printing reflows, so the screen width must equal the printed width.
MARGIN_MM = 12
A4_CONTENT_WIDTH_PX = round((210 - 2 * MARGIN_MM) / 25.4 * 96)

FOOTER = """
<div style="width:100%;font:7.5pt -apple-system,'Helvetica Neue',Arial,sans-serif;color:#7a8089;
            padding:0 12mm;display:flex;justify-content:space-between">
  <span>STATS19 explorer · DfT road safety data (OGL v3.0) · © OpenStreetMap contributors</span>
  <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
</div>"""


class ReportError(RuntimeError):
    """The print page failed or never signalled it was ready."""


def render_pdf(url: str, *, timeout_s: float = 90) -> bytes:
    with _RENDER_SLOTS, sync_playwright() as p:
        browser = p.chromium.launch(args=_CHROMIUM_ARGS)
        try:
            # bypass_csp: our pages forbid eval (Caddyfile CSP), which Playwright's
            # readiness polling needs. Applies to this renderer session only.
            page = browser.new_context(
                viewport={"width": A4_CONTENT_WIDTH_PX, "height": 1000}, bypass_csp=True
            ).new_page()
            problems: list[str] = []  # page console errors, for a useful message if it fails
            page.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: problems.append(str(e)))
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)
            try:
                page.wait_for_function("window.__reportReady === true", timeout=timeout_s * 1000)
            except PlaywrightTimeout as exc:
                hint = f" (last page error: {problems[-1]})" if problems else ""
                raise ReportError(
                    f"report page did not finish within {timeout_s:.0f} s{hint}"
                ) from exc
            except PlaywrightError as exc:
                hint = f"; page errors: {problems[-3:]}" if problems else ""
                raise ReportError(f"report page crashed: {exc}{hint}") from exc
            failure = page.evaluate("window.__reportError || null")
            if failure:
                raise ReportError(f"report page failed: {failure}")
            return page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                display_header_footer=True,
                header_template="<span></span>",
                footer_template=FOOTER,
                margin={
                    "top": f"{MARGIN_MM}mm",
                    "bottom": f"{MARGIN_MM + 2}mm",
                    "left": f"{MARGIN_MM}mm",
                    "right": f"{MARGIN_MM}mm",
                },
            )
        finally:
            browser.close()
