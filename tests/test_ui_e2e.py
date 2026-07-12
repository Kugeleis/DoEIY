import multiprocessing
import os
import time
from collections.abc import Generator

import pytest
import uvicorn
from playwright.sync_api import Page, expect

from app.main import app

# Check if Playwright browser binaries are installed and available
playwright_available = False
if os.environ.get("CI") != "true":
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            _browser = p.chromium.launch()
            _browser.close()
        playwright_available = True
    except Exception:
        pass


def run_server() -> None:
    # Run the uvicorn app on port 8002 for E2E testing
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="warning")


@pytest.fixture(scope="module", autouse=True)
def server() -> Generator[None]:
    # Spin up uvicorn in a separate daemon process
    proc = multiprocessing.Process(target=run_server, daemon=True)
    proc.start()
    time.sleep(1.5)  # Wait for uvicorn to boot up
    yield
    proc.terminate()
    proc.join()


@pytest.mark.skipif(
    not playwright_available,
    reason="Playwright E2E tests are skipped because browser binaries are not installed or we are in CI."
)
def test_ui_workflow(page: Page) -> None:
    # 1. Load the web interface
    page.goto("http://127.0.0.1:8002/")
    expect(page).to_have_title("DoEIY - Design of Experiments Web Platform")

    # 2. Check default navigation and visibility
    expect(page.locator("#make-design")).to_be_visible()
    expect(page.locator("#enter-results")).not_to_be_visible()

    # 3. Generate a default Full Factorial design (2 factors, 4 runs)
    page.click("#generate-design-btn")

    # Should automatically transition to the Enter/Edit Results tab
    expect(page.locator("#enter-results")).to_be_visible()
    expect(page.locator("#make-design")).not_to_be_visible()

    # Wait for Handsontable to load
    page.wait_for_selector("#hot-container .handsontable")

    # 4. Programmatically fill response values via exposed appState for stability
    page.evaluate("""() => {
        window.appState.designData.forEach((row, idx) => {
            row.Response = 50.0 + idx * 5.0; // 50, 55, 60, 65
        });
        window.appState.hotInstance.loadData(window.appState.designData);
    }""")

    # 5. Run Regression Analysis
    # Navigate to the Analyze the Design tab
    page.click('.nav-menu [data-tab="analyze-design"] a')
    expect(page.locator("#analyze-design")).to_be_visible()

    # Run fitting on "Response" with Main Effects preset
    page.click("#run-analysis-btn")

    # Results section should become visible
    page.wait_for_selector("#analysis-results-section", state="visible")

    # Check that R-squared is valid
    r2_text = page.locator("#val-r2").text_content()
    assert r2_text is not None
    assert float(r2_text) > 0.0

    # 6. Model Explorer & Optimizer
    # Navigate to the Model Explorer tab
    page.click('.nav-menu [data-tab="model-explorer"] a')
    expect(page.locator("#model-explorer")).to_be_visible()
    expect(page.locator("#explorer-content")).to_be_visible()

    # Verify sliders for the factors are created
    expect(page.locator("#slider-Temperature")).to_be_visible()
    expect(page.locator("#slider-Pressure")).to_be_visible()

    # Solve Optimization (Maximize Response)
    page.select_option("#opt-type", "Maximize")
    page.click("#run-optimizer-btn")

    # Verify optimizer outputs a badge and a valid prediction
    page.wait_for_selector("#optimizer-results-badge", state="visible")
    opt_pred_text = page.locator("#opt-resolved-pred").text_content()
    assert opt_pred_text is not None
    assert float(opt_pred_text) >= 64.9
