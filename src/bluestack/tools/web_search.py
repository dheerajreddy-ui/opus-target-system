"""Mock web search tool with SSRF protection at higher defense levels."""

import json
import re


_CANNED_RESULTS = [
    {"title": "AcmeCorp Product Catalog", "url": "https://acmecorp.com/products", "snippet": "Browse our complete range of enterprise solutions."},
    {"title": "AcmeCorp Support Center", "url": "https://acmecorp.com/support", "snippet": "Get help with orders, returns, and technical issues."},
    {"title": "AcmeCorp Return Policy", "url": "https://acmecorp.com/returns", "snippet": "30-day hassle-free returns on all products."},
    {"title": "AcmeCorp Enterprise Plans", "url": "https://acmecorp.com/enterprise", "snippet": "Custom solutions for teams of 50+."},
    {"title": "AcmeCorp Blog", "url": "https://acmecorp.com/blog", "snippet": "Latest news and product updates from AcmeCorp."},
]


class WebSearchTool:
    def __init__(self, defense_manager=None):
        self.defense_manager = defense_manager

    def search(self, query: str, num_results: int = 3) -> str:
        """Search with canned results. Level 2+: reject queries containing URLs/IPs."""
        if self.defense_manager and self.defense_manager.is_enabled("input_sanitizer"):
            if re.search(r"https?://|(\d{1,3}\.){3}\d{1,3}|localhost|127\.0\.0\.1|0\.0\.0\.0", query, re.IGNORECASE):
                return json.dumps({"error": "Query rejected: URLs and IP addresses are not permitted in search queries."})

        results = _CANNED_RESULTS[:max(1, min(num_results, len(_CANNED_RESULTS)))]
        return json.dumps({"query": query, "results": results, "total": len(results)})
