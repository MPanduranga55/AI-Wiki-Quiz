from typing import Tuple

import requests
from bs4 import BeautifulSoup  # type: ignore


def fetch_and_extract(url: str) -> Tuple[str, str]:
    """
    Fetch a Wikipedia article over HTTP and extract its readable text.

    Returns:
        raw_html: the original HTML we downloaded
        extracted_text: plain text content for the LLM
    """
    # Add User-Agent header to avoid 403 Forbidden errors
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # Wikipedia main content is usually inside '#mw-content-text' or 'div.mw-parser-output'
    content_div = soup.select_one("div.mw-parser-output") or soup.select_one(
        "#mw-content-text"
    )
    
    text = ""
    
    if content_div:
        # Remove noisy elements: tables, infoboxes, navboxes, references, etc.
        for selector in [
            "table",
            "div.navbox",
            "div.infobox",
            "div.reflist",
            "span.mw-editsection",
            "sup.reference",
            "div.thumb",
            "div.gallery",
            "div.mw-jump-link",
            "div.hatnote",
            "div.mw-indicators",
            "div.ambox",
            "div.dablink",
        ]:
            for el in content_div.select(selector):
                el.decompose()

        # Collect paragraph text - be less aggressive with filtering
        paragraphs = []
        for p in content_div.find_all("p"):
            p_text = p.get_text(" ", strip=True)
            # Only filter out very short paragraphs (less than 10 chars) or empty ones
            if p_text and len(p_text.strip()) >= 10:
                paragraphs.append(p_text)
        
        text = "\n\n".join(paragraphs)
        
        # If we still don't have enough text, try getting text from headings and list items
        if len(text.strip()) < 200:
            # Get headings
            headings = []
            for h in content_div.find_all(["h1", "h2", "h3", "h4", "h5"]):
                h_text = h.get_text(" ", strip=True)
                if h_text and len(h_text.strip()) >= 5:
                    headings.append(h_text)
            
            # Get list items
            list_items = []
            for li in content_div.find_all("li"):
                li_text = li.get_text(" ", strip=True)
                if li_text and len(li_text.strip()) >= 10:
                    list_items.append(li_text)
            
            # Combine all text parts
            all_text_parts = paragraphs + headings + list_items
            text = "\n\n".join([t for t in all_text_parts if t and len(t.strip()) >= 10])
    
    # Final fallback: if we still have no text, try getting text from the whole body
    if not text or len(text.strip()) < 50:
        # Try getting text from main content area without filtering
        body_text = soup.get_text(separator="\n", strip=True)
        # Remove very short lines and common noise
        lines = [line.strip() for line in body_text.split("\n") if line.strip() and len(line.strip()) > 20]
        text = "\n".join(lines[:100])  # Take first 100 meaningful lines
    
    # Last resort: return raw text from body
    if not text or len(text.strip()) < 50:
        text = soup.get_text(separator="\n", strip=True)

    return html, text


