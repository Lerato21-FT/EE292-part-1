"""Exercise real uploads, responsive Plotly charts and PNG downloads in Chromium."""

import struct
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect, sync_playwright
from test_out_of_plane import write_perpendicular_dataset

ARTIFACTS = Path("/artifacts")
CHART_IDS = ("kittel-chart", "linewidth-chart", "trace-chart")


def wait_for_results(page: Page) -> None:
    """Wait for analysis and all three plots, including the selected raw trace."""
    expect(page.locator("#results")).to_be_visible(timeout=60000)
    expect(page.locator("#analyze-button")).to_be_enabled(timeout=60000)
    expect(page.locator("#loading-message")).to_be_hidden()
    expect(page.locator("#error-message")).to_be_hidden()
    page.wait_for_function("document.querySelector('#trace-chart').data?.length === 2")


def check_chart_layout(page: Page) -> None:
    """Assert plots resize and labels remain within their cards and SVG canvases."""
    page.wait_for_function("""() => [...document.querySelectorAll('.chart')].every(
      c => c._fullLayout && Math.abs(c._fullLayout.width - c.clientWidth) < 2)""")
    failures = page.evaluate("""() => {
      const errors = [];
      if (document.documentElement.scrollWidth > innerWidth + 1) errors.push('page overflows');
      for (const chart of document.querySelectorAll('.chart')) {
        const canvas = chart.querySelector('.main-svg').getBoundingClientRect();
        const card = chart.closest('.chart-card').getBoundingClientRect();
        if (canvas.left < card.left || canvas.right > card.right + 1) {
          errors.push(chart.id + ': canvas overflows');
        }
        const labels = '.xtick text, .ytick text, .xtitle, .ytitle, '
          + '.annotation-text, .legend, .legendtext';
        for (const label of chart.querySelectorAll(labels)) {
          const r = label.getBoundingClientRect();
          if (r.width && (r.left < canvas.left - 2 || r.right > canvas.right + 2
              || r.top < canvas.top - 2 || r.bottom > canvas.bottom + 2)) {
            errors.push(chart.id + ': clipped label ' + label.textContent);
          }
        }
        const annotation = chart.querySelector('.annotation-text').getBoundingClientRect();
        const legend = chart.querySelector('.legend').getBoundingClientRect();
        if (annotation.bottom > legend.top - 2) {
          errors.push(chart.id + ': equation overlaps legend at ' + innerWidth);
        }
        if (chart._fullLayout._size.h < 100) errors.push(chart.id + ': plot area too short');
      }
      return errors;
    }""")
    assert not failures, failures


def exercise_browser() -> None:
    """Run both geometries, narrow screens, failure recovery and image exports."""
    with tempfile.TemporaryDirectory() as temporary:
        folder = write_perpendicular_dataset(Path(temporary))
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto("http://127.0.0.1:8000")
            wait_for_results(page)
            expect(page.locator("#sweep-count")).to_have_text("49")
            check_chart_layout(page)
            page.screenshot(path=str(ARTIFACTS / "in-plane-desktop.png"), full_page=True)
            page.get_by_role("button", name="Out-of-plane", exact=True).click()
            expect(page.locator("#results")).to_be_hidden()
            expect(page.locator("#analyze-button")).to_be_disabled()
            expect(page.locator("#initial-field")).to_have_value("-0.4")
            expect(page.locator("#initial-linewidth")).to_have_value("10")
            page.locator("#dataset-folder").set_input_files(str(folder))
            wait_for_results(page)
            expect(page.locator("#sweep-count")).to_have_text("08")
            expect(page.locator("#g-factor")).to_have_text("2.1200")
            expect(page.locator("#perpendicular-field")).to_have_text("-0.4000")
            expect(page.locator("#fourfold-field")).to_have_text("N/A")
            check_chart_layout(page)
            page.screenshot(path=str(ARTIFACTS / "out-of-plane-desktop.png"), full_page=True)

            for width in (1024, 768, 390, 320):
                page.set_viewport_size({"width": width, "height": 1000})
                check_chart_layout(page)
                if width == 390:
                    page.screenshot(path=str(ARTIFACTS / "out-of-plane-mobile.png"), full_page=True)
            page.set_viewport_size({"width": 1440, "height": 1100})
            page.locator("#initial-field").fill("-0.3")
            page.locator("#analyze-button").click()
            wait_for_results(page)
            expect(page.locator("#perpendicular-field")).to_have_text("-0.4000")
            page.locator("#trace-select").select_option(index=7)
            expect(page.locator("#trace-summary")).to_contain_text("28.000 GHz")
            for chart in CHART_IDS:
                with page.expect_download() as download_event:
                    page.locator(f'[data-chart="{chart}"]').click()
                download = download_event.value
                assert "out_of_plane" in download.suggested_filename
                destination = ARTIFACTS / download.suggested_filename
                download.save_as(destination)
                payload = destination.read_bytes()
                assert payload[:8] == b"\x89PNG\r\n\x1a\n"
                assert struct.unpack(">II", payload[16:24]) == (2000, 1400)

            page.reload()
            wait_for_results(page)
            expect(page.locator('[data-geometry="out_of_plane"]')).to_have_attribute(
                "aria-pressed", "true"
            )
            expect(page.locator("#perpendicular-field")).to_have_text("-0.4000")
            bad_folder = Path(temporary) / "invalid"
            bad_folder.mkdir()
            (bad_folder / "bad.csv").write_text("1,2\n" * 8, encoding="utf-8")
            page.locator("#dataset-folder").set_input_files(str(bad_folder))
            expect(page.locator("#error-message")).to_be_visible()
            expect(page.locator("#upload-button")).to_be_enabled()
            page.locator("#analyze-button").click()
            wait_for_results(page)
            expect(page.locator("#perpendicular-field")).to_have_text("-0.4000")
            page.get_by_role("button", name="In-plane", exact=True).click()
            page.locator("#dataset-folder").set_input_files("/data")
            wait_for_results(page)
            expect(page.locator("#sweep-count")).to_have_text("49")
            for width in (1440, 390, 320):
                page.set_viewport_size({"width": width, "height": 1000})
                check_chart_layout(page)
            assert not errors, errors
            browser.close()
    print(
        "Browser checks passed: both geometries, responsive charts, "
        "uploads, refit, reload, PNG export."
    )


def main() -> None:
    """Start an isolated API server for the browser and always stop it afterwards."""
    ARTIFACTS.mkdir(exist_ok=True)
    with tempfile.TemporaryFile(mode="w+") as server_log:
        server = subprocess.Popen(
            ["uvicorn", "app.api:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=server_log,
            stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(150):
                try:
                    if httpx.get("http://127.0.0.1:8000/api/measurements").status_code == 200:
                        break
                except httpx.TransportError:
                    if server.poll() is not None:
                        raise RuntimeError("Browser test API exited before startup.") from None
                time.sleep(0.2)
            else:
                raise RuntimeError("Browser test API did not start.")
            exercise_browser()
        except Exception:
            server_log.seek(0)
            print(server_log.read())
            raise
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
