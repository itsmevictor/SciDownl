# -*- coding: utf-8 -*-
"""Content implementations."""

from .base import BaseContent
from bs4 import BeautifulSoup


def is_verification_page(html):
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select_one('meta[name="citation_pdf_url"], div.pdf object, embed#pdf, iframe#pdf, '
                       'object[type="application/pdf"], embed[type="application/pdf"]'):
        return False
    title = soup.title.get_text(' ', strip=True).lower() if soup.title else ''
    return ('are you a robot' in title or 'êtes-vous un robot' in title or 'just a moment' in title or
            'checking your browser' in title or 'verify you are human' in title or
            soup.select_one('#challenge-form, altcha-widget[challengeurl*="/captcha/challenge/"]') is not None)


class HtmlContent(BaseContent):
    """Content stores html string."""
    def __init__(self, html: str = None):
        super().__init__(html)
        self.type = 'html'

    def __repr__(self):
        return f"HtmlContent[html = {self.content}]"

    def __len__(self):
        return len(self.content)


class JsonContent(BaseContent):
    """Content stores JSON object."""
    def __init__(self, json: dict = None):
        super().__init__(json)
        self.type = 'json'

    def __repr__(self):
        return f"JsonContent[json = {self.content}]"

    def __len__(self):
        return len(self.content)
