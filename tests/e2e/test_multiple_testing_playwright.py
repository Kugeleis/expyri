"""Browser regression for adjusted significance through results and plots."""

from pathlib import Path

from playwright.sync_api import Page, expect
from tests.e2e.test_playwright_e2e import playwright_server, pytestmark

__all__ = ["playwright_server", "pytestmark"]


def test_holm_results_and_plot_filter(playwright_server: str, page: Page, tmp_path: Path) -> None:
    csv = "group,strong,marginal,other\n"
    csv += "".join(f"A,{i},{i},{i}\n" for i in range(1, 6))
    csv += "".join(f"B,{i + 9},{i + 2.5},{i + 2.4}\n" for i in range(1, 6))
    upload = page.request.post(
        f"{playwright_server}/wizard/upload",
        multipart={"file": {"name": "holm_data.csv", "mimeType": "text/csv", "buffer": csv.encode()}},
    )
    assert upload.ok
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))

    page.goto(playwright_server)
    with page.expect_response(lambda response: response.url.endswith("/select-dataset-id")) as selection:
        page.locator("select[name='dataset_id']").select_option("holm_data")
    assert selection.value.ok
    page.wait_for_selector("select[name='group_column']")
    with page.expect_response(lambda response: response.url.endswith("/update-group-col")) as grouping:
        page.locator("select[name='group_column']").select_option("group")
    assert grouping.value.ok
    page.wait_for_selector("input[name='selected_groups']")
    page.get_by_text("Choose Method", exact=True).click()
    page.locator("input[name='selected_method'][value='ttest_ind']").check()
    page.get_by_text("Results", exact=True).click()

    table = page.locator(".results-table")
    expect(table.get_by_role("columnheader", name="Raw p-value", exact=True)).to_be_visible()
    expect(table.get_by_role("columnheader", name="Adjusted p-value", exact=True)).to_be_visible()
    expect(page.locator("#multiple-testing-legend")).to_contain_text("Holm")
    marginal = table.locator("tbody tr").filter(has=page.get_by_role("cell", name="marginal", exact=True))
    assert float(marginal.locator("td").nth(3).inner_text()) < 0.05
    assert float(marginal.locator("td").nth(4).inner_text()) > 0.05
    expect(marginal).not_to_have_class("result-row-significant")
    expect(marginal).not_to_have_class("result-row-strict")
    expect(page.locator("#filtered-plots-counter")).to_contain_text("Matches 1 variables")
    expect(page.get_by_label("Plot top variables with adjusted p-value ≤")).to_be_visible()
    page.locator("#statResultsContainer").screenshot(path=str(tmp_path / "holm-results.png"))

    page.get_by_role("columnheader", name="Adjusted p-value", exact=True).click()
    expect(table.locator("tbody tr").first.locator("td").first).to_have_text("strong")
    page.get_by_label("Plot top variables with adjusted p-value ≤").fill("0.1")
    page.get_by_label("Plot top variables with adjusted p-value ≤").press("Tab")
    expect(page.locator("#filtered-plots-counter")).to_contain_text("Matches 3 variables")
    page.get_by_label("Plot top variables with adjusted p-value ≤").fill("0.05")
    page.get_by_label("Plot top variables with adjusted p-value ≤").press("Tab")
    expect(page.locator("#filtered-plots-counter")).to_contain_text("Matches 1 variables")

    page.get_by_text("Select Plots", exact=True).click()
    expect(page.locator("#plots-generation-counter")).to_contain_text("adjusted p-value")
    page.locator("input[name='selected_plots'][value='boxplot']").check()
    page.get_by_role("button", name="Generate Plots", exact=True).click()
    expect(page.locator(".plot-group-card")).to_have_count(1)
    expect(page.locator(".plot-group-header code")).to_have_text("strong")
    expect(page.locator(".plot-result-meta")).to_contain_text("Adjusted p:")
    assert not page_errors
