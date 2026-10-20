# -*- coding: utf-8 -*-
"""High level APIs for human"""

from ..core.task import ScihubTask


def scihub_download(
        keyword: str,
        paper_type: str = 'doi',
        scihub_url: str = None,
        out: str = None,
        proxies: dict = None,
        browser: bool = False
    ) -> str:
    """Download a paper from SciHub.

    :param keyword: a DOI or a PMID.
    :param paper_type: (optional) one of ['doi', 'pmid', 'title']
    :param scihub_url: (optional) a specific SciHub url used to download the paper.
        If None, automatically choose one from local saved domains.
        It's recommended to leave it None.
    :param out: Output directory or file path, which could be an
        absolute path or a relative path.
        Output directory examples:
         /absolute/path/to/download/, ./relative/path/to/download/
        Output file examples:
         /absolute/dir/paper.pdf, ../relative/dir/paper.pdf
        If None, paper will be downloaded to the current directory with the file
        name of the paper's title.
    :param browser: Open Chrome for interactive robot verification when necessary.
    :returns: The saved PDF path. Raises an exception if all mirrors fail.
    """
    proxies = proxies or {}
    return ScihubTask(
        source_keyword=keyword,
        source_type=paper_type,
        scihub_url=scihub_url,
        out=out,
        proxies=proxies,
        browser=browser
    ).run()

