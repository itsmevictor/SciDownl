# -*- encoding: utf-8 -*-
"""Task implementations."""
import os.path

from .base import BaseTask, ScihubUrlChooser
from .source import DoiSource, source_classes
from .crawler import ScihubCrawler
from .extractor import HtmlPdfExtractor
from .downloader import UrlDownloader
from .chooser import AvailabilityFirstScihubUrlChooser, scihub_url_choosers
from .updater import CrawlingScihubDomainUpdater
from ..log import get_logger
from ..config import get_config
from ..db.service import ScihubUrlService
from ..exception import DownloadException

logger = get_logger()
configs = get_config()

scihub_url_chooser_type = configs['scihub.task']['scihub_url_chooser_type']
default_chooser_cls = scihub_url_choosers.get(scihub_url_chooser_type, AvailabilityFirstScihubUrlChooser)


class ScihubTask(BaseTask):

    def __init__(self,
                 source_keyword: str,
                 source_type: str = 'doi',
                 scihub_url: str = None,
                 scihub_url_chooser_cls=default_chooser_cls,
                 out: str = None,
                 proxies: dict = None,
                 browser: bool = False):
        super().__init__()
        self.source_keyword = source_keyword
        self.scihub_url_chooser_cls = scihub_url_chooser_cls
        self.scihub_url_chooser = self.scihub_url_chooser_cls()
        self.scihub_url = scihub_url
        self.source_class = source_classes.get(source_type, DoiSource)
        self.out = out
        self.proxies = proxies or {}
        self.context['status'] = 'initialized'
        self.context['proxies'] = self.proxies
        self.context['browser'] = browser
        self.service = ScihubUrlService()
        self.updater = CrawlingScihubDomainUpdater()

    def run(self):
        if self.scihub_url is not None:
            logger.info(f"Choose the scihub url: {self.scihub_url}")
            return self._run(self.scihub_url)

        preferred_urls = configs['scihub.task'].get('preferred_urls', '').split()
        # Keep a usable configured mirror even if domain discovery is unavailable.
        if len(self.scihub_url_chooser) == 0 and not preferred_urls:
            self.updater.update_domains()
            self.scihub_url_chooser = self.scihub_url_chooser_cls()

        urls = dict.fromkeys(preferred_urls + [item.url for item in self.scihub_url_chooser])
        errors = []
        for i, scihub_url in enumerate(urls):
            try:
                logger.info(f"Choose scihub url [{i}]: {scihub_url}")
                return self._run(scihub_url)
            except Exception as e:
                self.context['error'] = e
                errors.append(f"{scihub_url}: {e}")
                logger.warning(f"Mirror failed: {scihub_url}: {e}")
        self.context['status'] = 'failed'
        error = DownloadException(
            f"Failed to download {self.source_keyword}. " + ('; '.join(errors) or 'No mirrors available.'))
        self.context['error'] = error
        raise error

    def _run(self, scihub_url):
        source = self.source_class(self.source_keyword)
        crawler = ScihubCrawler(source, scihub_url, self)
        try:
            return self._download(crawler)
        finally:
            crawler.sess.close()
            self.context.pop('session', None)

    def _download(self, crawler):
        content = crawler.crawl()

        extractor = HtmlPdfExtractor(content, self)
        pdf_url_title_info = extractor.extract()
        title = pdf_url_title_info['title'] or HtmlPdfExtractor._clean_title(self.source_keyword) or 'paper'

        if self.out is None:
            # Using title as the filename and save to current directory.
            out = title + '.pdf'
        else:
            dirpath, filename = os.path.split(self.out)
            if dirpath != '' and not os.path.exists(dirpath):
                os.makedirs(dirpath)
            if len(filename) == 0 or os.path.isdir(self.out):
                dirpath = self.out
                filename = title + '.pdf'
            if not filename.lower().endswith('.pdf'):
                filename += '.pdf'
            out = os.path.join(dirpath, filename)

        downloader = UrlDownloader(pdf_url_title_info, self)
        downloader.download(out)
        scihub_url = self.context.get('referer', None)
        self.service.increment_success_times(scihub_url)
        self.context['status'] = 'succeeded'
        self.context.pop('error', None)
        return out
