import os
import re
import socket
import threading
import time
import shutil
from collections.abc import Generator
import pandas as pd
import playwright.sync_api
from playwright.sync_api import Page, expect
import pytest
import uvicorn
from app.main import app

def _check_playwright_launch() -> bool:
    try:
        with playwright.sync_api.sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        return True
    except Exception:
        return False

pytestmark = pytest.mark.skipif(
    not _check_playwright_launch(),
    reason="Playwright chromium browser cannot be launched",
)

def get_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return int(port)

@pytest.fixture(scope="module")
def nycflights_server(tmp_path_factory: pytest.TempPathFactory) -> Generator[str, None, None]:
    tmp_dir = tmp_path_factory.mktemp("nycflights_data")
    
    # Copy nycflights.csv to the temp data directory
    shutil.copy("data/nycflights.csv", tmp_dir / "nycflights.csv")
    
    original_env = os.environ.get("EXPYRI_DATA_DIR")
    os.environ["EXPYRI_DATA_DIR"] = str(tmp_dir)
    
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    
    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()
    
    base_url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError("Server failed to start")
        
    yield base_url
    
    server.should_exit = True
    thread.join(timeout=5)
    if original_env is not None:
        os.environ["EXPYRI_DATA_DIR"] = original_env
    else:
        os.environ.pop("EXPYRI_DATA_DIR", None)

def test_nycflights_origin_methods_offered(nycflights_server: str, page: Page) -> None:
    page.goto(f"{nycflights_server}/")
    
    # Step 1: Select nycflights
    page.locator("select[name='dataset_id']").select_option("nycflights")
    page.wait_for_selector("select[name='group_column']")
    
    # Select group column
    page.locator("select[name='group_column']").select_option("origin")
    
    # Wait for checkboxes to be rendered and check default selections
    page.wait_for_selector("input[name='selected_groups']")
    
    # Go to step 3 (Choose Method)
    page.click("text=Choose Method")
    page.wait_for_selector("input[name='selected_method']")
    
    # Expect Kruskal-Wallis H to be enabled
    kruskal = page.locator("input[name='selected_method'][value='kruskal_wallis']")
    expect(kruskal).to_be_enabled()
    
    # Verify that the panel is scrollable so the user can see the non-parametric options
    panel = page.locator("#panel-step-3")
    overflow_y = panel.evaluate("el => window.getComputedStyle(el).overflowY")
    assert overflow_y in ("auto", "scroll")

def test_nycflights_origin_continue_flow(nycflights_server: str, page: Page) -> None:
    page.goto(f"{nycflights_server}/")
    
    # Step 1: Select nycflights
    page.locator("select[name='dataset_id']").select_option("nycflights")
    page.wait_for_selector("select[name='group_column']")
    
    # Select group column
    page.locator("select[name='group_column']").select_option("origin")
    page.wait_for_selector("input[name='selected_groups']")
    
    # Click sidebar Continue button to go to Step 2
    page.click("#btn-sidebar-next")
    page.wait_for_selector("text=Step 2: Preprocessing Filters")
    
    # Click sidebar Continue button to go to Step 3
    page.click("#btn-sidebar-next")
    page.wait_for_selector("input[name='selected_method']")
    
    # Expect Kruskal-Wallis H to be enabled
    kruskal = page.locator("input[name='selected_method'][value='kruskal_wallis']")
    expect(kruskal).to_be_enabled()

