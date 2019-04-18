import requests
import logging


logger = logging.getLogger(__name__)


def download_progress(url, path):
    '''
    Download a file using a streamed response
    and display progress
    '''
    written = 0
    percent = 0
    with requests.get(url, stream=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get('Content-Length', 0))
        assert total > 0, 'No content-length'
        with open(path, 'wb') as f:
            logger.info('Writing artifact in {}'.format(path))
            for chunk in resp.iter_content(chunk_size=1024*1024):
                if chunk:
                    x = f.write(chunk)
                    written += x
                    p = int(100.0 * written / total)
                    if p % 10 == 0 and p > percent:
                        percent = p
                        logger.info('Written {} %'.format(p))

    logger.info('Written {} with {} bytes'.format(path, written))
    return written
