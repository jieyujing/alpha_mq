---
name: xiaoya-search
description: Specialized media discovery for Xiaoya Alist. Use when searching for movies, anime, or TV shows in Xiaoya Alist, especially when standard discovery methods are limited.
---

# Xiaoya Search

## Overview
Efficiently discovers media resources in the Xiaoya Alist ecosystem by parsing HTML search results from the built-in search page.

## Quick Start
Search for resources by keyword:
```bash
python3 scripts/search.py <keyword>
```

## Implementation Details
- **Hybrid Network Path**: Automatically detects and prioritizes Intranet (`192.168.100.99:5678`) before falling back to Extranet (`xiaoya.luoyujun.eu.org`).
- **HTML Parsing**: Uses `requests` and `re` to extract resource paths directly from the web search interface (`/search?box=...`).
- **Dynamic Correction**: Intercepts 302 redirects to internal Docker IPs (`172.17.0.2`) and maps them back to accessible host addresses.

## Output Format
Returns results as a numbered list of Markdown hyperlinks:
`1. [Resource Name](https://xiaoya.luoyujun.eu.org/path/to/resource)`
