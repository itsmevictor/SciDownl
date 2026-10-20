"""Shared HTTP settings for article pages and PDFs."""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REQUEST_TIMEOUT = (5, 30)


def create_session():
    session = requests.Session()
    retries = Retry(total=2, backoff_factor=0.5,
                    status_forcelist=[429, 500, 502, 503, 504],
                    respect_retry_after_header=False)
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session
