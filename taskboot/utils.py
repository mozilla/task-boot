import requests
import logging
import time


logger = logging.getLogger(__name__)


def retry(operation,
          retries=5,
          wait_between_retries=30,
          exception_to_break=None,
          ):
    '''
    Retry an operation several times
    '''
    for i in range(retries):
        try:
            logger.debug('Trying {}/{}'.format(i+1, retries))
            return operation()
        except Exception as e:
            logger.warn('Try failed: {}'.format(e))
            if exception_to_break and isinstance(e, exception_to_break):
                raise
            if i == retries - 1:
                raise
            time.sleep(wait_between_retries)


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
