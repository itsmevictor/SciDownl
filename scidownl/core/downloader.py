# -*- encoding: utf-8 -*-
"""Downloader implementation."""
import os
import tempfile

from .base import BaseDownloader, BaseTask, BaseTaskStep
from .http import create_session, REQUEST_TIMEOUT
from .information import UrlInformation
from ..log import get_logger
from ..exception import DownloadException
from ..db.service import ScihubUrlService

logger = get_logger()


class UrlDownloader(BaseDownloader, BaseTaskStep):
    """Download a PDF, preserving an existing file if the request fails."""

    def __init__(self, information: UrlInformation, task: BaseTask = None):
        BaseDownloader.__init__(self, information)
        BaseTaskStep.__init__(self, task)
        self.service = ScihubUrlService()
        if self.task is not None:
            self.task.context['status'] = 'downloading'

    def download(self, out: str) -> str:
        context = self.task.context if self.task is not None else {}
        session = context.get('session')
        owns_session = session is None
        if owns_session:
            session = create_session()
        temporary_path = None
        try:
            headers = {}
            if context.get('page_url'):
                headers['Referer'] = context['page_url']
            with session.get(self.information.get_url(), stream=True,
                             proxies=context.get('proxies', {}), headers=headers,
                             timeout=REQUEST_TIMEOUT) as response:
                response.raise_for_status()
                chunks = response.iter_content(chunk_size=65536)
                first_chunk = next((chunk for chunk in chunks if chunk), b'')
                if not first_chunk.lstrip().startswith(b'%PDF-'):
                    raise ValueError(
                        'The server returned an empty response or a non-PDF page '
                        '(possibly a robot verification page). Try another mirror '
                        'with --scihub-url.')
                with tempfile.NamedTemporaryFile(dir=os.path.dirname(os.path.abspath(out)),
                                                 prefix='.scidownl-', suffix='.part',
                                                 delete=False) as output:
                    temporary_path = output.name
                    output.write(first_chunk)
                    for chunk in chunks:
                        output.write(chunk)
            os.replace(temporary_path, out)
            temporary_path = None
            filename = os.path.basename(out)
            logger.info(f"↓ Successfully downloaded the PDF to: {out}")
            if self.task is not None:
                context['out'] = out
                context['filename'] = filename
                context['status'] = 'downloaded'
            return filename
        except Exception as error:
            if self.task is not None:
                context['status'] = 'downloading_failed'
                context['error'] = error
                self.service.increment_failed_times(context.get('referer'))
            raise DownloadException(f"Error downloading PDF: {error}") from error
        finally:
            if temporary_path is not None:
                os.unlink(temporary_path)
            if owns_session:
                session.close()
