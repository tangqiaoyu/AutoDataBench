# Web Search & Fetch API

Base URL: `$WEB_API_BASE`
Auth: all requests must include the `Authorization: Bearer $WEB_API_KEY` header.

> **Note (current project setup)**: `WEB_API_BASE` and `WEB_API_KEY` are already provided via environment variables — use them directly, no need to fill in host / key by hand. The `curl` examples below reference `$WEB_API_BASE` / `$WEB_API_KEY` directly.

---

## POST /search

Web search powered by Google.

### Request

```bash
curl -X POST "$WEB_API_BASE/search" \
  -H "Authorization: Bearer $WEB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "what is python programming language",
    "num": 3,
    "extendParams": {
      "country": "us",
      "locale": "en",
      "location": "United States",
      "page": 1,
      "type": "search"
    },
    "platformInput": {
      "model": "google-search"
    }
  }'
```

### Parameters

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | string | Yes | Search query |
| `num` | int | No | Number of results per page (default 10) |
| `extendParams.country` | string | No | Country code: `"us"` (default), `"cn"` for Chinese search |
| `extendParams.locale` | string | No | Locale: `"en"` (default), `"zh-cn"` for Chinese |
| `extendParams.location` | string | No | `"United States"` (default), `"China"` for Chinese |
| `extendParams.page` | int | No | Page number (default 1) |
| `extendParams.type` | string | No | `"search"` (default) or `"news"` |
| `platformInput.model` | string | No | Fixed: `"google-search"` |

**Chinese search shortcut** — just change three fields in `extendParams`:

```json
{
  "country": "cn",
  "locale": "zh-cn",
  "location": "China"
}
```

### Response

```json
{
  "success": true,
  "message": "请求成功",
  "data": {
    "id": 784579996353095363,
    "usage": {
      "cacheReadInputTokensCompatible": 0,
      "completion_tokens": 0,
      "prompt_tokens": 1,
      "total_tokens": 1
    },
    "originalOutput": {
      "searchParameters": {
        "q": "what is python programming language",
        "gl": "us",
        "hl": "en",
        "type": "search",
        "num": 3,
        "page": 1,
        "location": "United States",
        "engine": "google"
      },
      "organic": [
        {
          "title": "What is Python? Executive Summary",
          "link": "https://www.python.org/doc/essays/blurb/",
          "snippet": "Python is an interpreted, object-oriented, high-level programming language with dynamic semantics.",
          "position": 1
        },
        {
          "title": "What Is Python Used For? A Beginner's Guide - Coursera",
          "link": "https://www.coursera.org/articles/what-is-python-used-for-a-beginners-guide-to-using-python",
          "snippet": "Python is a computer programming language often used to build websites and software, automate tasks, and conduct data analysis.",
          "date": "May 20, 2025",
          "position": 2
        }
      ],
      "peopleAlsoAsk": [
        {
          "question": "What is Python programming in easy words?",
          "snippet": "Python is an interpreted, object-oriented, high-level programming language...",
          "title": "What is Python? - Teradata",
          "link": "https://www.teradata.com/glossary/what-is-python"
        }
      ],
      "relatedSearches": [
        { "query": "What is python programming language used for" },
        { "query": "Features of Python" }
      ],
      "credits": 1
    }
  },
  "code": "200",
  "detailMessage": null
}
```

---

## POST /fetch

Fetch and scrape a webpage. Powered by [Firecrawl](https://docs.firecrawl.dev/features/scrape).

Firecrawl handles proxies, caching, rate limits, JS-rendered pages, and PDFs automatically.

### Basic Request

```bash
curl -X POST "$WEB_API_BASE/fetch" \
  -H "Authorization: Bearer $WEB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "onlyMainContent": true,
    "formats": ["html"]
  }'
```

### Parameters

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `url` | string | Yes | — | URL to scrape |
| `formats` | list | No | `["html"]` | Output formats (see below) |
| `onlyMainContent` | bool | No | `true` | Strip headers, footers, navs — keep main content only |
| `maxAge` | int | No | `172800000` | Cache freshness window in ms. Set `0` to force fresh scrape |
| `storeInCache` | bool | No | `true` | Set `false` to skip caching the result |
| `location` | object | No | `{"country":"US"}` | Geo location for the scrape (see Location section) |
| `actions` | list | No | — | Page interactions before scraping (see Actions section) |
| `timeout` | int | No | `30000` | Timeout in ms for the scrape operation |

### Output Formats

Specify one or more in the `formats` array. The response `data` object will contain matching keys.

| Format | Description | Credits |
|---|---|---|
| `"markdown"` | Clean markdown of page content | 1 |
| `"html"` | Cleaned HTML | 1 |
| `"rawHtml"` | Unmodified HTML as received from the page | 1 |
| `"links"` | All links extracted from the page | 1 |
| `"screenshot"` | Screenshot of the page (URL, expires in 24h) | 1 |
| `"json"` | Structured extraction with schema or prompt | +4 |

Multiple formats can be combined: `["markdown", "html", "links"]`

### Structured Extraction (JSON format)

Pass an object in `formats` to extract structured data:

```bash
curl -X POST "$WEB_API_BASE/fetch" \
  -H "Authorization: Bearer $WEB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://firecrawl.dev",
    "formats": [{
      "type": "json",
      "schema": {
        "type": "object",
        "properties": {
          "company_mission": { "type": "string" },
          "is_open_source": { "type": "boolean" }
        },
        "required": ["company_mission", "is_open_source"]
      }
    }]
  }'
```

Or extract without a schema using just a prompt:

```json
{
  "url": "https://firecrawl.dev",
  "formats": [{
    "type": "json",
    "prompt": "Extract the company mission from the page."
  }]
}
```

### Location

Control geo-location and language of the scrape:

```json
{
  "url": "https://example.com",
  "formats": ["markdown"],
  "location": {
    "country": "US",
    "languages": ["en"]
  }
}
```

- `country`: ISO 3166-1 alpha-2 code (e.g. `"US"`, `"CN"`, `"DE"`, `"JP"`). Default `"US"`.
- `languages`: Preferred languages in order of priority. Default: language of specified country.

### Actions

Interact with the page before scraping (click, type, scroll, wait, etc.):

```json
{
  "url": "https://example.com/login",
  "formats": ["markdown"],
  "actions": [
    { "type": "write", "text": "john@example.com" },
    { "type": "press", "key": "Tab" },
    { "type": "write", "text": "secret" },
    { "type": "click", "selector": "button[type=\"submit\"]" },
    { "type": "wait", "milliseconds": 1500 },
    { "type": "screenshot", "fullPage": true }
  ]
}
```

Always use `{"type": "wait", "milliseconds": ...}` before/after other actions to allow the page to load.

### Response

```json
{
  "success": true,
  "data": {
    "metadata": {
      "language": "en",
      "viewport": "width=device-width, initial-scale=1",
      "title": "Example Domain",
      "scrapeId": "019ceb6c-3ce6-7168-82b2-24c50d8cbd8c",
      "sourceURL": "https://example.com",
      "url": "https://example.com/",
      "statusCode": 200,
      "contentType": "text/html",
      "proxyUsed": "basic",
      "cacheState": "hit",
      "cachedAt": "2026-03-14T06:54:28.912Z",
      "creditsUsed": 1,
      "concurrencyLimited": false
    },
    "html": "<!DOCTYPE html><html lang=\"en\"><body><div><h1>Example Domain</h1><p>This domain is for use in documentation examples without needing permission.</p></div></body></html>"
  }
}
```

Response `data` keys depend on requested formats:
- `data.markdown` — when `"markdown"` requested
- `data.html` — when `"html"` requested
- `data.rawHtml` — when `"rawHtml"` requested
- `data.links` — when `"links"` requested
- `data.screenshot` — when `"screenshot"` requested (URL string, expires in 24h)
- `data.json` — when JSON extraction requested
- `data.metadata` — always present

### Caching Notes

- Default cache window is 2 days (`maxAge: 172800000`). Cached responses are much faster (~5x).
- Set `maxAge: 0` to always fetch fresh content (slower, more likely to fail).
- Check `data.metadata.cacheState` (`"hit"` or `"miss"`) to see if the response was cached.

### Credits

Each scrape costs 1 credit. Additional costs:
- JSON extraction: +4 credits per page
- Enhanced proxy: +4 credits per page
- PDF parsing: +1 credit per PDF page

---

## Error Responses

| Status | Meaning | Example |
|---|---|---|
| 401 | Missing or invalid API key | `{"detail": "Invalid API key"}` |
| 429 | Call quota exhausted | `{"detail": "Call quota exhausted for this key. Used: 10,000, Quota: 10,000"}` |
| 502 | Backend unreachable | `{"detail": "Backend request failed: ..."}` |

---

## Retry Recommendations

The backend services may occasionally be unstable (timeouts, 5xx errors, rate limits). We recommend implementing retry logic in your client code.

Key points:
- Use **exponential backoff** (1s, 2s, 4s) between retries
- Retry on **timeout**, **connection error**, and **5xx** status codes
- Do **not** retry on **401** (auth error) — it require fixing the key first
