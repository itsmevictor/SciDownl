# -*- coding: utf-8 -*-
"""Crawler implementations."""
from .content import HtmlContent, is_verification_page
from .browser import fetch_verified_page
from .http import create_session, REQUEST_TIMEOUT
from .base import BaseCrawler, BaseSource, BaseTaskStep, BaseTask, BaseContent
from ..log import get_logger
from ..exception import CrawlException
from ..db.service import ScihubUrlService

logger = get_logger()


class ScihubCrawler(BaseCrawler, BaseTaskStep):
    """Crawler of a scihub source."""

    OK_STATUS_CODES = [200]

    def __init__(self, source: BaseSource, scihub_url: str, task: BaseTask = None):
        BaseCrawler.__init__(self, source)
        BaseTaskStep.__init__(self, task)
        self.scihub_url = scihub_url
        self.sess = create_session()
        self.service = ScihubUrlService()

        if self.task is not None:
            self.task.context['source'] = source
            self.task.context['referer'] = scihub_url
            self.task.context['status'] = 'crawling'

    def crawl(self) -> HtmlContent:
        try:
            # Build direct URL: https://sci-hub.xx/{identifier}
            identifier = self.source[self.source.type]
            url = f"{self.scihub_url.rstrip('/')}/{identifier}"
            proxies = self.task.context.get('proxies', {}) if self.task is not None else {}
            logger.info(f"<- Request: url={url}, source={self.source}, proxies={proxies}")

            res = self.sess.get(url, proxies=proxies, timeout=REQUEST_TIMEOUT)
            logger.info(f"-> Response: status_code={res.status_code}, content_length={len(res.content)}")

            html, page_url = res.text, res.url
            if is_verification_page(html):
                if self.task is None or not self.task.context.get('browser'):
                    raise RuntimeError('Robot verification required. Use --browser to complete '
                                       'the check in Chrome, or try another mirror with --scihub-url.')
                html, page_url = fetch_verified_page(res.url, self.sess, proxies)
            elif res.status_code not in ScihubCrawler.OK_STATUS_CODES:
                raise RuntimeError(f"HTTP {res.status_code} from {res.url}")

            content = HtmlContent(html)

            if self.task is not None:
                self.task.context['content'] = content
                self.task.context['page_url'] = page_url
                self.task.context['session'] = self.sess
                self.task.context['status'] = 'crawled'
            return content
        except Exception as e:
            if self.task is not None:
                self.task.context['status'] = 'crawling_failed'
                self.task.context['error'] = e
                self.service.increment_failed_times(self.scihub_url)
            raise CrawlException(f"Error occurs when crawling: {e}")
        finally:
            if self.task is None:
                self.sess.close()
