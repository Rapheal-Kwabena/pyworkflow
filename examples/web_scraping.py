"""Example: Web Scraping workflow illustrating explicit task setup and fallback execution."""

import re
import urllib.request
from pyworkflow import workflow, task


@task(retries=2, retry_delay=1.0)
def fetch_page(url: str) -> str:
    """Fetch HTML page from URL with a local mock fallback if offline."""
    print(f"Fetching URL: {url}")
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (PyWorkflow Scraper)"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        print(f"Network failed ({e}). Returning mock HTML fallback...")
        return '<html><body><a href="/prod/1">Product 1</a><a href="/prod/2">Product 2</a></body></html>'


@task
def extract_links(html: str) -> list[str]:
    """Parse links from the HTML page."""
    print("Extracting href links...")
    links = re.findall(r'href=[\'"]([^\'"]+)[\'"]', html)
    return links


@task
def process_links(links: list[str]) -> dict:
    """Count product links and compile results."""
    print("Filtering and processing links...")
    prod_links = [l for l in links if "prod" in l]
    return {
        "total_links": len(links),
        "product_links": prod_links,
        "product_count": len(prod_links),
    }


# Assemble workflow using manual tasks and explicit dependencies
flow = workflow("Web Scraping Workflow")

task_fetch = fetch_page.get_task()
task_fetch.args = ("https://news.ycombinator.com",)

task_extract = extract_links.get_task()
task_extract.depends_on = [task_fetch.name]

task_process = process_links.get_task()
task_process.depends_on = [task_extract.name]

flow.add_task(task_fetch)
flow.add_task(task_extract)
flow.add_task(task_process)

if __name__ == "__main__":
    report = flow.run()
    print(f"Scraping run completed: {report.success}")
    if report.success:
        print(f"Scraped details: {report.results['process_links']}")
