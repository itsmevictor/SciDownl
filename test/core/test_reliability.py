"""Offline regression tests for mirror failures and PDF downloads."""
import tempfile
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests
from click.testing import CliRunner

from scidownl.api.cli import cli
from scidownl.core.content import HtmlContent, is_verification_page
from scidownl.core.browser import fetch_verified_page
from scidownl.core.crawler import ScihubCrawler
from scidownl.core.downloader import UrlDownloader
from scidownl.core.extractor import HtmlPdfExtractor
from scidownl.core.information import PdfUrlTitleInformation
from scidownl.core.source import DoiSource
from scidownl.core.task import ScihubTask
from scidownl.exception import CrawlException, DownloadException, ExtractException


class TestReliability(unittest.TestCase):
    def setUp(self):
        for module in ('crawler', 'downloader', 'extractor', 'task'):
            patcher = patch(f'scidownl.core.{module}.ScihubUrlService')
            patcher.start()
            self.addCleanup(patcher.stop)
        updater = patch('scidownl.core.task.CrawlingScihubDomainUpdater')
        updater.start()
        self.addCleanup(updater.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / 'paper.pdf'
        self.session = MagicMock()
        self.context = {'session': self.session, 'page_url': 'https://mirror.test/article'}
        self.info = PdfUrlTitleInformation('https://mirror.test/paper.pdf', 'Paper')

    def download_response(self, chunks):
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_content.return_value = iter(chunks)
        self.session.get.return_value = response
        return response

    def test_pdf_without_content_length_and_shared_session(self):
        self.download_response([b'', b'%PDF-1.6\n', b'paper'])
        task = SimpleNamespace(context=self.context)
        UrlDownloader(self.info, task).download(str(self.output))
        self.assertEqual(self.output.read_bytes(), b'%PDF-1.6\npaper')
        self.assertEqual(self.session.get.call_args.kwargs['headers'],
                         {'Referer': self.context['page_url']})
        self.assertIn('timeout', self.session.get.call_args.kwargs)
        self.session.close.assert_not_called()
        self.assertEqual(list(self.output.parent.glob('*.part')), [])

    def test_error_page_and_empty_response_preserve_existing_file(self):
        for chunks in ([b'<html>Are you a robot?</html>'], []):
            with self.subTest(chunks=chunks):
                self.output.write_bytes(b'existing PDF')
                self.download_response(chunks)
                with self.assertRaises(DownloadException):
                    UrlDownloader(self.info, SimpleNamespace(context=self.context)).download(str(self.output))
                self.assertEqual(self.output.read_bytes(), b'existing PDF')

    def test_http_error_does_not_create_output(self):
        response = self.download_response([b'%PDF-1.6'])
        response.raise_for_status.side_effect = requests.HTTPError('404')
        with self.assertRaises(DownloadException):
            UrlDownloader(self.info, SimpleNamespace(context=self.context)).download(str(self.output))
        self.assertFalse(self.output.exists())

    def test_interrupted_download_cleans_up_and_preserves_file(self):
        self.output.write_bytes(b'existing PDF')
        def interrupted_chunks():
            yield b'%PDF-1.6\n'
            raise requests.ConnectionError('Disconnected')
        self.download_response(interrupted_chunks())
        with self.assertRaises(DownloadException):
            UrlDownloader(self.info, SimpleNamespace(context=self.context)).download(str(self.output))
        self.assertEqual(self.output.read_bytes(), b'existing PDF')
        self.assertEqual(list(self.output.parent.iterdir()), [self.output])

    def test_pdf_layouts_and_relative_urls(self):
        for html, expected in [
            ('<meta name="citation_pdf_url" content="/file.pdf#view=FitH">', 'https://mirror.test/file.pdf'),
            ('<embed id="pdf" src="//cdn.test/file.pdf#view=FitH">', 'https://cdn.test/file.pdf'),
            ('<iframe id="pdf" src="file.pdf">', 'https://mirror.test/papers/file.pdf'),
            ('<object type="application/pdf" data="https://cdn.test/file.pdf#x"></object>', 'https://cdn.test/file.pdf'),
            ('<a href="/file.pdf?download=1">Save</a>', 'https://mirror.test/file.pdf?download=1'),
            ('<div class="pdf"><object></object></div><meta name="citation_pdf_url" content="/file.pdf">', 'https://mirror.test/file.pdf'),
        ]:
            with self.subTest(html=html):
                context = {'page_url': 'https://mirror.test/papers/article'}
                info = HtmlPdfExtractor(HtmlContent(html), SimpleNamespace(context=context)).extract()
                self.assertEqual(info.get_url(), expected)

    def test_metadata_title_and_robot_page(self):
        html = '<meta name="citation_title" content="Title: a question?"><embed id="pdf" src="https://cdn.test/file.pdf">'
        info = HtmlPdfExtractor(HtmlContent(html)).extract()
        self.assertEqual(info.get_title(), 'Title  a question')
        with self.assertRaisesRegex(ExtractException, 'Robot verification'):
            HtmlPdfExtractor(HtmlContent('<title>Are you a robot?</title>')).extract()

    def test_crawler_keeps_redirect_url_and_session(self):
        response = requests.Response()
        response.status_code = 200
        response.url = 'https://new-mirror.test/papers/article'
        response._content = b'<title>Paper</title>'
        self.session.get.return_value = response
        context = {}
        with patch('scidownl.core.crawler.create_session', return_value=self.session):
            crawler = ScihubCrawler(DoiSource('10.1017/example'), 'https://mirror.test', SimpleNamespace(context=context))
            crawler.crawl()
        self.assertIs(context['session'], self.session)
        self.assertEqual(context['page_url'], response.url)
        self.assertEqual(context['referer'], 'https://mirror.test')

    def test_french_verification_and_article_report_widget(self):
        self.assertTrue(is_verification_page('<title>Sci-Hub : êtes-vous un robot ?</title>'))
        self.assertTrue(is_verification_page('<altcha-widget challengeurl="/captcha/challenge/123"></altcha-widget>'))
        self.assertFalse(is_verification_page(
            '<title>A paper about robots</title><meta name="citation_pdf_url" content="/paper.pdf">'
            '<altcha-widget challengeurl="/captcha/challenge"></altcha-widget>'))
        self.assertFalse(is_verification_page(
            '<title>Are you a robot? A study</title><embed type="application/pdf" src="/paper.pdf">'))

    def test_crawler_browser_handoff_is_optional(self):
        response = requests.Response()
        response.status_code = 403
        response.url = 'https://mirror.test/article'
        response._content = b'<title>Are you a robot?</title>'
        self.session.get.return_value = response
        with patch('scidownl.core.crawler.create_session', return_value=self.session):
            with patch('scidownl.core.crawler.fetch_verified_page') as browser:
                crawler = ScihubCrawler(DoiSource('10.1017/example'), 'https://mirror.test',
                                        SimpleNamespace(context={}))
                with self.assertRaisesRegex(CrawlException, '--browser'):
                    crawler.crawl()
                browser.assert_not_called()
                context = {'browser': True}
                html = '<meta name="citation_pdf_url" content="/paper.pdf">'
                browser.return_value = html, 'https://redirect.test/article'
                crawler = ScihubCrawler(DoiSource('10.1017/example'), 'https://mirror.test',
                                        SimpleNamespace(context=context))
                self.assertEqual(crawler.crawl().content, html)
                browser.assert_called_once_with(response.url, self.session, {})
                self.assertEqual(context['page_url'], 'https://redirect.test/article')

    @unittest.skipUnless(importlib.util.find_spec('selenium'), 'Optional Selenium is not installed')
    def test_browser_exports_cookies_and_closes(self):
        with patch('selenium.webdriver.Chrome') as chrome, patch('selenium.webdriver.support.ui.WebDriverWait'):
            browser = chrome.return_value.__enter__.return_value
            browser.execute_script.return_value = 'Browser user agent'
            browser.get_cookies.return_value = [{'name': 'session', 'value': 'verified',
                                                 'domain': '.mirror.test', 'path': '/', 'secure': True}]
            browser.page_source = '<title>Paper</title>'
            browser.current_url = 'https://mirror.test/article'
            html, url = fetch_verified_page(browser.current_url, self.session, {})
            self.assertEqual(html, '<title>Paper</title>')
            self.assertEqual(url, browser.current_url)
            self.session.cookies.set.assert_called_once_with(
                'session', 'verified', domain='.mirror.test', path='/', secure=True, expires=None)
            self.session.headers.__setitem__.assert_called_once_with('User-Agent', 'Browser user agent')
            chrome.return_value.__exit__.assert_called_once()

    def test_missing_browser_dependency_has_instructions(self):
        with patch.dict('sys.modules', {'selenium': None}):
            with self.assertRaisesRegex(RuntimeError, 'requires Selenium'):
                fetch_verified_page('https://mirror.test', self.session, {})

    def test_failed_mirror_falls_back(self):
        task = ScihubTask('10.1017/example', scihub_url_chooser_cls=lambda: [])
        with patch('scidownl.core.task.configs', {'scihub.task': {'preferred_urls': 'https://first.test https://second.test'}}):
            with patch.object(task, '_run', side_effect=[DownloadException('Robot check'), 'paper.pdf']) as run:
                self.assertEqual(task.run(), 'paper.pdf')
        self.assertEqual([call.args[0] for call in run.call_args_list],
                         ['https://first.test', 'https://second.test'])

    def test_all_mirrors_failed_raises(self):
        task = ScihubTask('10.1017/example', scihub_url_chooser_cls=lambda: [])
        with patch.object(task, '_run', side_effect=DownloadException('No PDF')):
            with self.assertRaisesRegex(DownloadException, 'No PDF'):
                task.run()
        self.assertEqual(task.context['status'], 'failed')

    def test_missing_title_uses_doi_and_closes_session(self):
        task = ScihubTask('10.1017/example', out=self.directory.name,
                          scihub_url='https://mirror.test', scihub_url_chooser_cls=lambda: [])
        with patch('scidownl.core.task.ScihubCrawler') as crawler_class:
            crawler = crawler_class.return_value
            crawler.crawl.return_value = HtmlContent('<embed id="pdf" src="https://cdn.test/paper.pdf">')
            with patch('scidownl.core.task.UrlDownloader') as downloader:
                out = task.run()
        self.assertEqual(Path(out).name, '10.1017 example.pdf')
        downloader.return_value.download.assert_called_once_with(out)
        crawler.sess.close.assert_called_once()
        self.assertEqual(task.context['status'], 'succeeded')

    def test_cli_failure_status_and_batch_continuation(self):
        with patch('scidownl.core.task.ScihubTask') as task:
            task.return_value.run.side_effect = [DownloadException('No PDF'), None]
            result = CliRunner().invoke(cli, ['download', '-d', '10.1/a', '-d', '10.1/b'])
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(task.return_value.run.call_count, 2)
        self.assertIn('Failed to download: 10.1/a', result.output)

    def test_cli_requires_identifier(self):
        result = CliRunner().invoke(cli, ['download'])
        self.assertEqual(result.exit_code, 2)
