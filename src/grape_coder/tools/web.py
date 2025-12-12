from strands.tools import tool


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
