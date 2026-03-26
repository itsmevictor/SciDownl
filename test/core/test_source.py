import unittest

from scidownl.core.source import DoiSource, PmidSource, TitleSource
from scidownl.exception import EmptyDoiException, EmptyPmidException, EmptyTitleException


class TestSource(unittest.TestCase):

    def test_create_doi_source(self):
        # Empty case: doi is None.
        with self.assertRaises(EmptyDoiException):
            DoiSource(None)

        # Empty case: doi is an empty string.
        with self.assertRaises(EmptyDoiException):
            DoiSource("")

        # Invalid type case: doi is not a string.
        with self.assertRaises(TypeError):
            DoiSource(2345783)

        # Correct case.
        cases = {
            'http_doi': 'http://doi.org/10.1145/1327452.1327492',
            'https_doi': 'https://doi.org/10.1145/1327452.1327492',
            'raw_doi': 'doi.org/10.1145/1327452.1327492',
            'bare_doi': '10.1145/1327452.1327492',
        }
        expected_doi = "10.1145/1327452.1327492"

        doi_source = DoiSource(cases.get('http_doi'))
        self.assertEqual(expected_doi, doi_source.get_doi())
        self.assertEqual("http", doi_source.get_protocol())

        doi_source = DoiSource(cases.get('https_doi'))
        self.assertEqual(expected_doi, doi_source.get_doi())
        self.assertEqual("https", doi_source.get_protocol())

        doi_source = DoiSource(cases.get('raw_doi'))
        self.assertEqual(expected_doi, doi_source.get_doi())
        self.assertEqual("https", doi_source.get_protocol())

        doi_source = DoiSource(cases.get('bare_doi'))
        self.assertEqual(expected_doi, doi_source.get_doi())
        self.assertEqual("https", doi_source.get_protocol())

    def test_doi_extraction_from_publisher_urls(self):
        """DOIs should be extracted from arbitrary publisher URLs."""
        cases = {
            'https://onlinelibrary.wiley.com/doi/abs/10.1111/ajps.12185':
                '10.1111/ajps.12185',
            'https://www.sciencedirect.com/science/article/pii/S0003347209005806/10.1016/j.anbehav.2009.12.007':
                '10.1016/j.anbehav.2009.12.007',
            'https://link.springer.com/article/10.1007/s11269-006-9105-4':
                '10.1007/s11269-006-9105-4',
            'https://journals.sagepub.com/doi/10.1177/0956797611421206':
                '10.1177/0956797611421206',
        }
        for url, expected_doi in cases.items():
            with self.subTest(url=url):
                doi_source = DoiSource(url)
                self.assertEqual(expected_doi, doi_source.get_doi())

    def test_create_pmid_source(self):
        # Empty case: PMID is None.
        with self.assertRaises(EmptyPmidException):
            PmidSource(None)

        # Empty case: doi is an empty string.
        with self.assertRaises(EmptyPmidException):
            PmidSource("")

        # Invalid type case: doi is not a string.
        with self.assertRaises(TypeError):
            PmidSource(True)
            PmidSource([])
            PmidSource({})

        # Correct case.
        cases = {
            'PMID_str': '31928726',
            'PMID_number': 31928726,
        }
        pmid_source = PmidSource(cases.get('PMID_str'))
        self.assertEqual(cases.get('PMID_str'), pmid_source.get_pmid())

        pmid_source = PmidSource(cases.get('PMID_number'))
        self.assertEqual(str(cases.get('PMID_number')), pmid_source.get_pmid())

    def test_create_title_source(self):
        # Empty case: TITLE is None.
        with self.assertRaises(EmptyTitleException):
            TitleSource(None)

        # Empty case: doi is an empty string.
        with self.assertRaises(EmptyTitleException):
            TitleSource("")

        # Invalid type case: doi is not a string.
        with self.assertRaises(TypeError):
            TitleSource(True)
            TitleSource([])
            TitleSource({})

        # Correct case.
        cases = {
            'title1': 'Visualizing Distributed System Executions',
            'title2': '    Measuring and improving customer retention at authorised automobile workshops after free services   ',
        }
        title_source = TitleSource(cases.get('title1'))
        self.assertEqual(cases.get('title1'), title_source.get_title())

        title_source = TitleSource(cases.get('title2'))
        self.assertEqual(str(cases.get('title2')).strip(), title_source.get_title())


if __name__ == '__main__':
    unittest.main()
