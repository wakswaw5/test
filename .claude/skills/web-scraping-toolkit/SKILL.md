---
name: web-scraping-toolkit
description: |
  Pick and use an open-source web crawling/scraping tool: Crawl4AI (web pages to LLM-ready markdown, Python), Crawlee (Node.js/Python crawlers with proxy rotation, retries and request queues), Scrapy (large-scale Python spider framework), AutoScraper (learns a scraping rule from one example value, no selectors) and curl-impersonate / curl_cffi (HTTP requests with a real Chrome/Firefox TLS fingerprint). Use when the user wants to write crawler/scraper code, crawl many pages, export scraped data, or asks which scraping tool to use. For Firecrawl use the `firecrawl*` skills; for AI-driven browser control use `browser-use` / `browser-use-library`; for stealth/adaptive scraping use `scrapling-official`; for files to markdown use `markitdown`; for Android apps use `scrcpy`.
---

# Web scraping toolkit

## Choosing a tool

| Need | Tool | Skill |
|---|---|---|
| Hosted API: search, scrape, crawl with JS rendering, markdown/JSON output | Firecrawl | `firecrawl`, `firecrawl-scrape`, `firecrawl-crawl`, … |
| Free local page → clean markdown for an LLM, no API key | Crawl4AI | this skill |
| An agent that clicks, scrolls, logs in, fills forms | Browser-use | `browser-use`, `browser-use-library` |
| Production crawler in Node.js/TypeScript (or Python) with proxy rotation, auto-retry, queues | Crawlee | this skill |
| Millions of pages, pipelines, clean JSON/CSV exports, pure Python | Scrapy | this skill |
| Stealth fetching, anti-bot pages, selectors that survive site redesigns | Scrapling | `scrapling-official` |
| Give one example value, get all similar items — no selectors to write | AutoScraper | this skill |
| Plain HTTP requests that look like a real Chrome/Firefox (TLS/HTTP2 fingerprint) | curl-impersonate / curl_cffi | this skill |
| PDF, Office, images → markdown | MarkItDown | `markitdown` |
| Data from an Android app with no website | scrcpy + adb | `scrcpy` |

Rules of thumb:
- Try a plain HTTP fetch first. Use a browser (Crawl4AI, Crawlee's `PlaywrightCrawler`, Browser-use) only when the page needs JavaScript or interaction.
- Respect robots.txt, site terms and rate limits. Keep concurrency low and add delays unless the user owns the site.
- Don't scrape behind a login or collect personal data unless the user is authorized to.

## Crawl4AI (Python, Apache-2.0)

Install:

```bash
pip install -U crawl4ai
crawl4ai-setup        # installs the Playwright browser; run crawl4ai-doctor if it fails
```

CLI:

```bash
crwl https://example.com -o markdown
```

Python:

```python
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

async def main():
    browser_cfg = BrowserConfig(headless=True)
    run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url="https://example.com", config=run_cfg)
        if result.success:
            print(result.markdown)
        else:
            print(result.error_message)

asyncio.run(main())
```

- Use `crawler.arun_many(urls, config=run_cfg)` to crawl several pages at once.
- For structured output, pass an extraction strategy such as `JsonCssExtractionStrategy(schema)` through `CrawlerRunConfig(extraction_strategy=...)`.
- Docs: https://docs.crawl4ai.com

## Crawlee (Node.js/TypeScript, Apache-2.0; Python version also available)

Start a project from a template, or add it to an existing one:

```bash
npx crawlee create my-crawler
# or
npm install crawlee playwright
```

Browser crawler (JavaScript-rendered pages):

```js
import { PlaywrightCrawler, Dataset } from 'crawlee';

const crawler = new PlaywrightCrawler({
    maxRequestsPerCrawl: 50,
    async requestHandler({ request, page, enqueueLinks, log }) {
        const title = await page.title();
        log.info(`${title} — ${request.loadedUrl}`);
        await Dataset.pushData({ url: request.loadedUrl, title });
        await enqueueLinks();            // follows same-domain links by default
    },
});

await crawler.run(['https://crawlee.dev']);
```

- Use `CheerioCrawler` for static HTML. It is much faster and doesn't start a browser.
- Proxy rotation: `new ProxyConfiguration({ proxyUrls: [...] })`, passed as `proxyConfiguration` to the crawler.
- Retries, the request queue and session/fingerprint handling are built in. Tune them with `maxRequestRetries`, `maxConcurrency` and `useSessionPool`.
- Results are saved to `./storage/datasets/default`. To export, call `await Dataset.exportToCSV('results')` or `exportToJSON`.
- Python: `pip install 'crawlee[all]'`, then use `crawlee.crawlers.PlaywrightCrawler` / `BeautifulSoupCrawler`.
- Docs: https://crawlee.dev

## Scrapy (Python, BSD-3-Clause)

```bash
pip install scrapy
scrapy startproject myproject      # full project, or use runspider for one file
scrapy shell "https://quotes.toscrape.com"   # try out selectors interactively
```

Spider in a single file:

```python
import scrapy

class QuotesSpider(scrapy.Spider):
    name = "quotes"
    start_urls = ["https://quotes.toscrape.com/"]
    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOAD_DELAY": 0.5,
    }

    def parse(self, response):
        for q in response.css("div.quote"):
            yield {
                "text": q.css("span.text::text").get(),
                "author": q.css("small.author::text").get(),
                "tags": q.css("a.tag::text").getall(),
            }
        yield from response.follow_all(css="li.next a", callback=self.parse)
```

```bash
scrapy runspider quotes_spider.py -O quotes.json   # -O overwrites; -o appends; .csv/.jsonl also work
```

- Clean and store data in item pipelines (`ITEM_PIPELINES`). Add proxy or header logic in downloader middlewares.
- Scrapy doesn't run JavaScript. For JS pages, find the site's underlying JSON API in the network tab, or add `scrapy-playwright`.
- Docs: https://docs.scrapy.org

## AutoScraper (Python, MIT)

Give it a page and one or more values you see on it; it learns the rule and finds similar items.

```bash
pip install autoscraper
```

```python
from autoscraper import AutoScraper

url = "https://stackoverflow.com/questions/2081586/web-scraping-with-python"
wanted_list = ["What are metaclasses in Python?"]   # a value copied from the page

scraper = AutoScraper()
print(scraper.build(url, wanted_list))            # every similar item on the page

# Reuse the learned rule on other pages with the same layout
scraper.get_result_similar("https://stackoverflow.com/questions/606191/convert-bytes-to-a-string")
scraper.get_result_exact("https://...")           # same fields, same order as wanted_list

scraper.save("so-scraper")                        # later: AutoScraper().load("so-scraper")
```

- `wanted_list` must match text that is in the fetched HTML right now. It fetches with `requests`, so JS-rendered content isn't visible. For those pages, fetch the HTML with a browser and pass it as `html=`.
- Proxies/headers: `scraper.build(url, wanted_list, request_args=dict(proxies=..., headers=...))`.
- Rules break if the site changes its layout. Rebuild when results come back empty.

## curl-impersonate / curl_cffi (MIT)

A build of curl whose TLS and HTTP/2 handshake matches a real Chrome or Firefox, so servers that block curl by its fingerprint treat it like a browser. It doesn't run JavaScript or solve CAPTCHAs.

`lwthiker/curl-impersonate` hasn't been updated since 2024. The maintained fork is `lexiforest/curl-impersonate`. In Python, use its binding **curl_cffi**:

```bash
pip install curl_cffi
```

```python
from curl_cffi import requests

r = requests.get("https://example.com", impersonate="chrome")   # latest Chrome profile
print(r.status_code, r.text[:200])

s = requests.Session(impersonate="chrome")      # keeps cookies across requests
```

The command-line binaries have one wrapper script per browser, and each wrapper sets that browser's headers:

```bash
docker run --rm lwthiker/curl-impersonate:0.6-chrome curl_chrome116 https://www.wikipedia.org
# or download a release binary: https://github.com/lexiforest/curl-impersonate/releases
```

Use it as a drop-in `requests` replacement when a site returns 403 to plain HTTP clients but works in a browser.
