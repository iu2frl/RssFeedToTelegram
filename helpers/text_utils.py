"""Helpers to clean and normalize text coming from the RSS feeds."""

import re


# Remove HTML code
def remove_html(inputText: str) -> str:
    """Remove html code from the news content"""
    regex_html = re.compile('<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});')
    return re.sub(regex_html, "", inputText.strip())


# Remove links from text
def remove_links(inputText: str) -> str:
    """Remove links from the news content"""
    # This regex matches URLs with or without http/https, including all subdomains
    regex_link = re.compile(r'(?:https?:\/\/)?(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)')
    return re.sub(regex_link, "", inputText.strip())


# Extract domain from URL
def extract_domain(url):
    """Extract the domain name from an URL"""
    pattern = r'https?://(?:www\.)?([^/]+)'
    result = re.match(pattern, url)
    if result:
        return result.group(1)
    return "anonymous"
