# Project: WEEX API Documentation Extraction and Knowledge Base Integration

## Architecture
- **WEEX API Crawler/Extractor**: A Python crawler script (e.g. `weex_crawler.py`) that uses `requests` and parses dynamic or static documentation content from WEEX (`https://www.weex.com/api-doc`).
- **Local Knowledge Base**: Mapped markdown files under `lobes/knowledge/weex/` and synchronized to `C:/Users/pesil/EAIS/.agents/lobes/knowledge/weex/`.
- **Knowledge Graph Ingestion**: Ingests markdown files into L1 Hybrid Memory (sqlite-vec) and Graph Memory (Entities/Relations) using the `angati/memory_store` and `memory` node/edge creation MCP tools.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1_Explore | Investigate WEEX doc structure, categories, schema and outline crawl layout | none | DONE |
| 2 | M2_Scrape_Update | Implement crawler/downloader, generate `.md` files, sync paths | M1 | DONE |
| 3 | M3_Ingest | Ingest compiled KIs into L1 Hybrid Memory and Graph Memory | M2 | DONE |
| 4 | M4_Audit | Validate links, schema structure, signatures (V2 vs V3), run checks | M3 | DONE |

## Interface Contracts
- **Markdown File Formats**: Standardized header schemas, tables for query parameters, code blocks for python/curl examples.
- **Signing logic**: Detail query param differences for V2 and V3 (V2: signature can treat query string inside path; V3: explicitly decouples path and query string).
- **Ingestion tools**: Call `memory_store` and graph node/relation tools properly.
