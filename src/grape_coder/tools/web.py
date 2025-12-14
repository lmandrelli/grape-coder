from strands.tools import tool
from bs4 import BeautifulSoup


@tool
def fetch_url(url: str) -> str:
    """Fetch content from a URL

    Args:
        url: URL to fetch content from
    """

    import urllib.error
    import urllib.request

    try:
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read().decode("utf-8", errors="ignore")
            return f"Content from {url}:\n{content[:5000]}{'...' if len(content) > 5000 else ''}"
    except urllib.error.HTTPError as e:
        return f"Error: HTTP {e.code} - {e.reason}"
    except Exception as e:
        return f"Error fetching URL: {str(e)}"


@tool
def search(query: str, max_results: int = 10) -> str:
    """Search DuckDuckGo and return formatted results

    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 10)
    """
    import urllib.parse
    import urllib.request
    import urllib.error
    from dataclasses import dataclass
    from typing import List

    @dataclass
    class SearchResult:
        title: str
        link: str
        snippet: str
        position: int

    def parse_duckduckgo_html(
        html_content: str, max_results: int
    ) -> List[SearchResult]:
        """Parse DuckDuckGo HTML response to extract search results"""
        soup = BeautifulSoup(html_content, "html.parser")
        results = []

        for result in soup.select(".result"):
            title_elem = result.select_one(".result__title")
            if not title_elem:
                continue

            link_elem = title_elem.find("a")
            if not link_elem:
                continue

            title = link_elem.get_text(strip=True)
            link = str(link_elem.get("href", "")) if link_elem.get("href") else ""

            # Skip ad results
            if not link or "y.js" in link:
                continue

            # Clean up DuckDuckGo redirect URLs
            if link.startswith("//duckduckgo.com/l/?uddg="):
                try:
                    link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
                except (IndexError, ValueError):
                    continue

            snippet_elem = result.select_one(".result__snippet")
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

            results.append(  # type: ignore
                SearchResult(
                    title=title,
                    link=link,
                    snippet=snippet,
                    position=len(results) + 1,  # type: ignore
                )
            )

            if len(results) >= max_results:  # type: ignore
                break

        return results  # type: ignore

    def format_results(results: List[SearchResult]) -> str:
        """Format results for display"""
        if not results:
            return "No results found. This could be due to DuckDuckGo's bot detection or the query returned no matches."

        output = [f"Found {len(results)} search results:\n"]

        for result in results:
            output.append(f"{result.position}. {result.title}")
            output.append(f"   URL: {result.link}")
            if result.snippet:
                output.append(f"   Summary: {result.snippet}")
            output.append("")

        return "\n".join(output)

    try:
        # Prepare search data
        data = urllib.parse.urlencode(
            {
                "q": query,
                "b": "",
                "kl": "",
            }
        ).encode("utf-8")

        # Create request
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        request = urllib.request.Request(
            "https://html.duckduckgo.com/html", data=data, headers=headers
        )

        # Make request
        with urllib.request.urlopen(request, timeout=30) as response:
            html_content = response.read().decode("utf-8", errors="ignore")

        # Parse results
        results = parse_duckduckgo_html(html_content, max_results)
        return format_results(results)

    except urllib.error.HTTPError as e:
        return f"Error: HTTP {e.code} - {e.reason}"
    except Exception as e:
        return f"Error searching DuckDuckGo: {str(e)}"
