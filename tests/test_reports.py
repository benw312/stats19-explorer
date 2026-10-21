"""PDF reports: renderer (headless Chromium) and the report endpoints."""

import json
import urllib.parse

import pytest

from stats19.reports import ReportError, render_pdf

READY_PAGE = (
    "data:text/html,<html><body><h1>Report</h1>"
    "<script>setTimeout(()=>{window.__reportReady=true},50)</script></body></html>"
)
FAILING_PAGE = (
    "data:text/html,<html><body><script>"
    "window.__reportError='summary failed';window.__reportReady=true</script></body></html>"
)


def test_render_pdf_waits_for_ready_and_returns_pdf():
    pdf = render_pdf(READY_PAGE, timeout_s=20)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_render_pdf_surfaces_page_errors():
    with pytest.raises(ReportError, match="summary failed"):
        render_pdf(FAILING_PAGE, timeout_s=20)


def test_render_pdf_times_out_when_never_ready():
    with pytest.raises(ReportError, match="did not finish"):
        render_pdf("data:text/html,<html><body>never ready</body></html>", timeout_s=2)


# ------------------------------------------------------------------ endpoints


@pytest.fixture
def captured(monkeypatch):
    import stats19.api.report_routes as routes

    calls: list[str] = []

    def fake_render(url: str, **_: object) -> bytes:
        calls.append(url)
        return b"%PDF-1.7 fake"

    monkeypatch.setattr(routes, "render_pdf", fake_render)
    return calls


@pytest.mark.integration
def test_area_report_renders_print_page(api, captured):
    f = {"year_from": 1979}
    r = api.get(
        "/api/reports/area.pdf",
        params={"f": json.dumps(f), "title": "A30 study", "notes": "Wet & dark"},
    )

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert 'filename="stats19-area-report-' in r.headers["content-disposition"]
    url = urllib.parse.urlparse(captured[0])
    q = urllib.parse.parse_qs(url.query)
    assert url.path == "/print/area"
    assert json.loads(q["f"][0]) == f
    assert q["title"] == ["A30 study"] and q["notes"] == ["Wet & dark"]


@pytest.mark.integration
def test_area_report_too_large(api, captured, monkeypatch):
    import stats19.api.report_routes as routes

    monkeypatch.setattr(routes, "MAX_REPORT_COLLISIONS", 1)
    r = api.get("/api/reports/area.pdf")

    assert r.status_code == 413
    assert captured == []


@pytest.mark.integration
def test_report_text_lengths_validated(api, captured):
    assert api.get("/api/reports/area.pdf", params={"title": "x" * 500}).status_code == 422


@pytest.mark.integration
def test_collision_report(api, captured):
    r = api.get("/api/reports/collision/1980A.pdf")

    assert r.status_code == 200
    assert urllib.parse.urlparse(captured[0]).path == "/print/collision/1980A"


@pytest.mark.integration
def test_collision_report_unknown_id(api, captured):
    assert api.get("/api/reports/collision/2099ZZZZ.pdf").status_code == 404
    assert captured == []


@pytest.fixture
def csp_server():
    """Serve a page with the production CSP *header* (as Caddy does), which forbids eval."""
    import http.server
    import socketserver
    import threading

    files = {
        "/page": (
            "text/html",
            b"<html><body><h1>CSP</h1><script src='/ready.js'></script></body></html>",
        ),
        # ready *after* polling has started, so the in-page (eval) polling path runs
        "/ready.js": ("text/javascript", b"setTimeout(() => { window.__reportReady = true }, 400)"),
    }

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path not in files:
                self.send_error(404)
                return
            ctype, body = files[self.path]
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    class Server(http.server.ThreadingHTTPServer):
        def server_bind(self):
            # skip HTTPServer's reverse-DNS lookup (socket.getfqdn), which can stall ~35 s
            socketserver.TCPServer.server_bind(self)
            self.server_name, self.server_port = "127.0.0.1", self.server_address[1]

    server = Server(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/page"
    server.shutdown()


def test_render_pdf_works_under_production_csp_header(csp_server):
    # Regression: Playwright's readiness polling uses eval, which the CSP blocks.
    assert render_pdf(csp_server, timeout_s=20).startswith(b"%PDF")


@pytest.mark.integration
def test_area_report_can_leave_out_sticks_and_list(api, captured):
    r = api.get("/api/reports/area.pdf", params={"sticks": "false", "list": "false"})
    full = api.get("/api/reports/area.pdf")

    assert r.status_code == 200 and full.status_code == 200
    q = urllib.parse.parse_qs(urllib.parse.urlparse(captured[0]).query)
    assert q["sticks"] == ["0"] and q["list"] == ["0"]
    assert "sticks" not in urllib.parse.parse_qs(urllib.parse.urlparse(captured[1]).query)
