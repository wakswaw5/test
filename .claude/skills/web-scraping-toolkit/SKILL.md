---
name: web-scraping-toolkit
description: |
  Pick and use an open-source web crawling/scraping tool: Crawl4AI (web pages to LLM-ready markdown, Python), Crawlee (Node.js/Python crawlers with proxy rotation, retries and request queues) and Scrapy (large-scale Python spider framework). Use when the user wants to write crawler/scraper code, crawl many pages, export scraped data, or asks which scraping tool to use. For Firecrawl use the `firecrawl*` skills; for AI-driven browser control use the `browser-use` / `browser-use-library` skills.
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
