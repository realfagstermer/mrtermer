# encoding=utf8
import sys
import os
import re
import logging
import logging.handlers
import requests
import datetime
from dateutil.parser import parse
from tzlocal import get_localzone
import pytz   # timezone in Python 3
from roald import Roald

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(asctime)s %(levelname)s:%(module)s:] %(message)s')

console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

warn_handler = logging.FileHandler('warnings.log')
warn_handler.setLevel(logging.WARNING)
warn_handler.setFormatter(formatter)
logger.addHandler(warn_handler)


def fetch(url, filename):
    """
    Download a file from an URL
    """
    with open(filename, 'wb') as handle:
        response = requests.get(url, stream=True)

        if not response.ok:
            logger.error('Download failed')
            return False

        for block in response.iter_content(1024):
            if not block:
                break

            handle.write(block)

    return True


def check_modification_dates(record):
    """
    Check modification date for remote and local file
    """
    tz = get_localzone()

    head = requests.head(record['remote_url'])
    if head.status_code != 200:
        logger.warn('Got status code: %s' % (head.status_code))
        record['modified'] = False
        return record
    record['remote_datemod'] = parse(head.headers['last-modified'])
    if os.path.isfile(record['local_file']):
        record['local_datemod'] = datetime.datetime.fromtimestamp(os.path.getmtime(record['local_file']))
    else:
        # use some date in the past
        record['local_datemod'] = datetime.datetime(year=2014, month=1, day=1)
    record['local_datemod'] = tz.normalize(tz.localize(record['local_datemod'])).astimezone(pytz.utc)

    logger.info('   Remote file modified: %s' % (record['remote_datemod'].isoformat()))
    logger.info('    Local file modified: %s' % (record['local_datemod'].isoformat()))

    # Subtract 5 minutes to account for the possibility of the clock being slightly off
    if record['remote_datemod'] < record['local_datemod'] + datetime.timedelta(minutes=5):
        logger.info(' -> Local data are up-to-date.')
        record['modified'] = False
        return record

    logger.info(' -> Fetching updated data...')
    fetch(record['remote_url'], record['local_file'])
    record['modified'] = True
    return record


def run():

    files = [
        {
            'remote_url': 'http://app.uio.no/ub/emnesok/data/mr/idtermer.txt',
            'local_file': 'src/idtermer.txt'
        }
    ]

    for f in files:

        logger.info('Checking {}...'.format(f['local_file']))
        f['record'] = check_modification_dates(f)

    if not reduce(lambda x, y: x or y['record']['modified'], files, False):

        logger.info('No changes. Exiting.')
        sys.exit(1)  # tells prepare.sh that there's no need to continue
        # return

    make()


def make():
    roald = Roald()
    roald.load('src/', format='roald2', language='en')
    roald.set_uri_format('http://data.ub.uio.no/mrtermer/c{id}')
    roald.save('mrtermer.json')

    marc21options = {
      'vocabulary': 'noubomr',
      'created_by': 'NoOU'
    }
    roald.export('dist/mrtermer.marc21.xml', format='marc21', **marc21options)
    roald.export('dist/mrtermer.ttl', format='rdfskos',
             include=['mrtermer.scheme.ttl'])


if __name__ == '__main__':
    run()

