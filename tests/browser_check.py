"""Exercise real uploads, responsive Plotly charts and PNG downloads in Chromium."""

import struct
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect, sync_playwright
from test_out_of_plane import write_mixed_field_dataset, write_perpendicular_dataset

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
        const legend = chart.querySelector('.legend')?.getBoundingClientRect();
        if (legend && annotation.bottom > legend.top - 2) {
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
            exercise_exclusions(page, 49)
            check_chart_layout(page)
            page.screenshot(path=str(ARTIFACTS / "in-plane-desktop.png"), full_page=True)
            # Round 1: the demo linewidth fit (R² ≈ 0.1) must not be shown as an established α.
            expect(page.locator("#damping-status")).to_be_visible()
            expect(page.locator("#damping-card")).not_to_have_class("metric-card metric-accent")
            expect(page.locator("#kittel-equation math msqrt")).to_have_count(1)
            expect(page.locator("#linewidth-equation math mfrac")).to_have_count(1)
            expect(page.locator("#model-note li")).to_have_count(4)
            page.get_by_role("button", name="New to FMR? Start here").click()
            expect(page.locator("#about-dialog")).to_be_visible()
            page.screenshot(path=str(ARTIFACTS / "about-dialog.png"))
            page.locator("#about-close").click()
            expect(page.locator("#about-dialog")).to_be_hidden()
            with page.expect_download() as download_event:
                page.locator('[data-chart="linewidth-chart"]').click()
            download_event.value.save_as(ARTIFACTS / "fmr-linewidth-in_plane.png")
            # Round 4: light by default, result first, a plain summary, and a dark theme.
            expect(page.locator("html")).to_have_attribute("data-theme", "light")
            expect(page.locator("#result-summary p")).to_have_count(3)
            expect(page.locator("#result-summary")).to_contain_text("is not established")
            assert page.evaluate("""() => {
              const summary = document.querySelector('#results-summary').getBoundingClientRect();
              const controls = document.querySelector('.controls').getBoundingClientRect();
              return summary.top < controls.top;
            }"""), "the fit summary must come before the controls"
            page.get_by_role("button", name="Dark", exact=True).click()
            expect(page.locator("html")).to_have_attribute("data-theme", "dark")
            page.wait_for_function(
                "document.querySelector('#kittel-chart').layout.paper_bgcolor === '#101923'"
            )
            expect(page.locator("#error-message")).to_be_hidden()
            assert page.evaluate(
                "document.querySelector('#kittel-chart').layout.xaxis.gridcolor"
            ).startswith("rgba(")
            page.screenshot(path=str(ARTIFACTS / "in-plane-dark.png"), full_page=True)
            page.reload()
            wait_for_results(page)
            expect(page.locator("html")).to_have_attribute("data-theme", "dark")
            page.get_by_role("button", name="Light", exact=True).click()
            page.wait_for_function(
                "document.querySelector('#kittel-chart').layout.paper_bgcolor === '#ffffff'"
            )
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
            exercise_exclusions(page, 8)
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
                assert struct.unpack(">II", payload[16:24]) == (2400, 1700)

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
            exercise_unavailable_fits(page, Path(temporary))
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


def exercise_exclusions(page: Page, total: int) -> None:
    """Select real chart markers from either plot and verify linked refits and recovery."""
    original = page.locator("#g-factor").inner_text()
    for chart_id in ("kittel-chart", "linewidth-chart"):
        marker = page.locator(f"#{chart_id} .scatterlayer .trace").nth(1).locator(".point").first
        marker.scroll_into_view_if_needed()
        bounds = marker.bounding_box()
        assert bounds is not None
        # Plotly receives real pointer events on its transparent drag layer above the SVG markers.
        page.mouse.click(bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2)
        expect(page.locator("#selection-status")).to_contain_text("1 selected")
        page.locator("#exclude-selected").click()
        wait_for_results(page)
        expect(page.locator("#sweep-count")).to_have_text(str(total - 1).zfill(2))
        expect(page.locator("#selection-status")).to_contain_text("1 excluded")
        for linked_chart in ("kittel-chart", "linewidth-chart"):
            assert (
                page.locator(f"#{linked_chart}").evaluate("chart => chart.data[1].marker.symbol[0]")
                == "x"
            )
        expect(page.locator("#trace-select option").first).to_contain_text("excluded")
        check_chart_layout(page)
        page.locator("#analyze-button").click()
        wait_for_results(page)
        expect(page.locator("#sweep-count")).to_have_text(str(total - 1).zfill(2))
        page.locator("#restore-all").click()
        wait_for_results(page)
        expect(page.locator("#g-factor")).to_have_text(original)
        expect(page.locator("#sweep-count")).to_have_text(str(total).zfill(2))

    # Keyboard-accessible dataset selection also supports bulk exclusions.
    options = page.locator("#dataset-selection option").evaluate_all(
        "options => options.map(option => option.value)"
    )
    page.locator("#dataset-selection").select_option(options[:-3])
    page.locator("#exclude-selected").click()
    wait_for_results(page)
    expect(page.locator("#fit-status")).to_contain_text("at least four")
    expect(page.locator("#results")).to_be_visible()
    expect(page.locator("#g-factor")).to_have_text("—")
    expect(page.locator("#sweep-count")).to_have_text("03")
    page.locator("#restore-all").click()
    wait_for_results(page)
    expect(page.locator("#sweep-count")).to_have_text(str(total).zfill(2))
    page.locator("#dataset-selection").select_option(options[:1])
    page.locator("#exclude-selected").click()
    wait_for_results(page)
    page.locator("#dataset-selection").select_option(options[:1])
    page.locator("#restore-selected").click()
    wait_for_results(page)
    expect(page.locator("#g-factor")).to_have_text(original)
    expect(page.locator("#sweep-count")).to_have_text(str(total).zfill(2))


def exercise_unavailable_fits(page: Page, temporary: Path) -> None:
    """Inspect signed resonances, recover property fits, and retain failed raw traces."""
    mixed_root = temporary / "mixed"
    mixed_root.mkdir()
    folder = write_mixed_field_dataset(mixed_root)
    page.locator("#dataset-folder").set_input_files(str(folder))
    wait_for_results(page)
    expect(page.locator("#fit-status")).to_contain_text("nonnegative")
    expect(page.locator("#g-factor")).to_have_text("—")
    expect(page.locator("#damping")).to_have_text("—")
    expect(page.locator("#trace-summary")).to_contain_text("-700.00 Oe")
    for chart in ("kittel-chart", "linewidth-chart"):
        assert page.locator(f"#{chart}").evaluate("chart => chart.data[0].x.length") == 0
        assert page.locator(f"#{chart}").evaluate("chart => chart.data[1].x.length") == 9
    for width in (1440, 320):
        page.set_viewport_size({"width": width, "height": 1000})
        check_chart_layout(page)
    page.set_viewport_size({"width": 1440, "height": 1100})
    check_chart_layout(page)
    page.screenshot(path=str(ARTIFACTS / "mixed-fields-before-exclusion.png"), full_page=True)
    negative_id = page.locator("#dataset-selection option").first.get_attribute("value")
    assert negative_id is not None
    page.locator("#dataset-selection").select_option(negative_id)
    page.locator("#exclude-selected").click()
    wait_for_results(page)
    expect(page.locator("#fit-status")).to_be_hidden()
    expect(page.locator("#g-factor")).to_have_text("2.1200")
    expect(page.locator("#damping")).to_have_text("0.0002000")
    page.locator("#restore-all").click()
    wait_for_results(page)
    expect(page.locator("#fit-status")).to_contain_text("nonnegative")
    expect(page.locator("#g-factor")).to_have_text("—")
    page.reload()
    wait_for_results(page)
    expect(page.locator("#fit-status")).to_contain_text("nonnegative")
    flat_folder = temporary / "flat"
    flat_folder.mkdir()
    (flat_folder / "sample-OOP-14000MHz-flat.csv").write_text("100,1\n" * 8, encoding="utf-8")
    page.locator("#dataset-folder").set_input_files(str(flat_folder))
    wait_for_results(page)
    expect(page.locator("#trace-summary")).to_contain_text("distinct")
    expect(page.locator("#dataset-selection option")).to_contain_text("fit unavailable")
    assert page.locator("#trace-chart").evaluate("chart => chart.data[0].y.length") == 8
    assert page.locator("#trace-chart").evaluate("chart => chart.data[1].y.length") == 0
    check_chart_layout(page)


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
