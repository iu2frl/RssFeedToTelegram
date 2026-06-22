"""Data models used to represent a single news item."""

import hashlib
import logging
import re
from datetime import datetime

import dateutil.parser


# Create news class
class NewsFromFeed(list):
    """Custom class to store news content"""
    title: str = ""
    date: datetime
    author: str = ""
    summary: str = ""
    link: str = ""
    checksum: str = ""

    def __init__(self, inputTitle: str, inputDate: str, inputAuthor: str, inputSummary: str, inputLink: str = "") -> None:
        self.title = inputTitle.strip()
        logging.debug(f"Class title: [{self.title}]")
        self.date = dateutil.parser.parse(inputDate).replace(tzinfo=None)
        logging.debug(f"Class date: [{self.date}]")
        self.author = inputAuthor.strip()
        logging.debug(f"Class author: [{self.author}]")
        if len(inputSummary) > 10:
            # Remove "Read more"
            regex_read_more = re.compile(re.escape("read more"), re.IGNORECASE)
            # Parse summary
            no_read_more = re.sub(regex_read_more, "", inputSummary.strip())
        else:
            no_read_more = inputSummary
        # Remove line feeds
        cut_text = no_read_more.strip().replace('\n', ' ')
        # Remove excessive blank spaces
        while '  ' in cut_text:
            cut_text = cut_text.replace('  ', ' ')
        # Cut input text if too long (Telegram API limitation)
        if len(no_read_more) > 300:
            cut_text = cut_text[:300] + " ..."
        self.summary = cut_text
        logging.debug(f"Class summary: [{self.summary}]")
        clean_url = inputLink.strip().lower()
        self.link = "[" + self.title + "](" + clean_url + ")"
        logging.debug(f"Class url: [{self.link}]")
        # Calculate checksum
        self.checksum = hashlib.md5(clean_url.encode('utf-8')).hexdigest()
        logging.debug(f"Class checksum: [{self.checksum}]")

    def __str__(self):
        return f"[[{self.title}], [{self.date}], [{self.author}], [{self.summary}], [{self.link}], [{self.checksum}]]"
