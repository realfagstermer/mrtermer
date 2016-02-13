# encoding=utf8
from __future__ import print_function
import sys
import os
import re
import requests
import datetime
from dateutil.parser import parse
from tzlocal import get_localzone
import pytz   # timezone in Python 3
from functools import reduce
import logging
import logging.config
from roald import Roald
from doit import get_var

logging.config.fileConfig('logging.cfg')
logger = logging.getLogger(__name__)

config = {
    'dumps_dir': get_var('dumps_dir', './dumps')
}


def task_fetch():

    def download(remote, local):
        with open(local, 'wb') as out_file:
            response = requests.get(remote, stream=True)
            if not response.ok:
                raise Exception('Download failed')
            for block in response.iter_content(1024):
                if not block:
                    break
                out_file.write(block)
        logger.info('Fetched new version of %s', remote)

    def fetch_remote(task, remote, etag_cache):
        logger.info('Checking %s', remote)
        head = requests.head(remote)
        if head.status_code != 200:
            logger.warn('Got status code: %s', head.status_code)
            raise Exception('Got status code: %s', head.status_code)

        if 'etag' in head.headers:
            remote_etag = head.headers['etag']
            if os.path.isfile(etag_cache):
                with open(etag_cache, 'rb') as f:
                    local_etag = f.read().decode('utf-8').strip()
            else:
                local_etag = '0'

            logger.info('   Remote file etag: %s', remote_etag)
            logger.info('    Local file etag: %s', local_etag)

            if remote_etag == local_etag:
                logger.info(' -> Local data are up-to-date.')
                task.uptodate = True
                return

            download(remote, task.targets[0])

            with open(etag_cache, 'wb') as f:
                f.write(remote_etag.encode('utf-8'))

            task.uptodate = False

    yield {
        'doc': 'Fetch remote files that have changed',
        'basename': 'fetch',
        'name': None
    }
    yield {
        'name': 'git pull',
        'actions': [
            'git config user.name "ubo-bot"',
            'git config user.email "danmichaelo+ubobot@gmail.com"',
            'git pull',
        ]
    }
    for remote in ['https://app.uio.no/ub/emnesok/data/mr/idtermer.txt']:
        local = 'src/{}'.format(remote.split('/')[-1])
        etag_cache = 'src/{}.etag'.format(remote.split('/')[-1])
        yield {
            'name': local,
            'actions': [(fetch_remote, [], {
                'remote': remote,
                'etag_cache': etag_cache
            })],
            'targets': [local]
        }


def task_build():

    def build_dist(task):
        logger.info('Building new dist')
        roald = Roald()
        roald.load('src/', format='roald2', language='en')
        roald.set_uri_format('http://data.ub.uio.no/mrtermer/c{id}')
        roald.save('mrtermer.json')
        logger.info('Wrote mrtermer.json')

        marc21options = {
            'vocabulary_code': 'noubomr',
            'created_by': 'NoOU'
        }
        roald.export('dist/mrtermer.marc21.xml', format='marc21', **marc21options)
        logger.info('Wrote mrtermer.marc21.xml')

        roald.export('dist/mrtermer.ttl', format='rdfskos',
                     include=['mrtermer.scheme.ttl', 'ubo-onto.ttl'])
        logger.info('Wrote mrtermer.ttl')

    return {
        'doc': 'Build distribution files (RDF/SKOS + MARC21XML) from source files',
        'actions': [build_dist],
        'file_dep': [
            'src/idtermer.txt',
            'ubo-onto.ttl',
            'mrtermer.scheme.ttl'
        ],
        'targets': [
            'mrtermer.json',
            'dist/mrtermer.marc21.xml',
            'dist/mrtermer.ttl'
        ]
    }


def task_git_push():
    return {
        'doc': 'Commit and push updated files to GitHub',
        'basename': 'git-push',
        'file_dep': [
            'mrtermer.json',
            'dist/mrtermer.marc21.xml',
            'dist/mrtermer.ttl'
        ],
        'actions': [
            'git config user.name "ubo-bot"',
            'git config user.email "danmichaelo+ubobot@gmail.com"',
            'git add -u',
            'git commit -m "Data update"',
            'git push --mirror origin'  # locally updated refs will be force updated on the remote end !
        ]
    }


def task_publish_dumps():

    basename = './dist/mrtermer'
    dumps_dir = config['dumps_dir']

    return {
        'doc': 'Publish uncompressed and compressed dumps',
        'basename': 'publish-dumps',
        'file_dep': [
            'dist/mrtermer.marc21.xml',
            'dist/mrtermer.ttl'
        ],
        'actions': [
            'mkdir -p {0}'.format(dumps_dir),
            'bzip2 -f -k {0}.ttl'.format(basename),
            'zip {0}.ttl.zip {0}.ttl'.format(basename),
            'cp {0}.ttl {0}.ttl.bz2 {0}.ttl.zip {1}/'.format(basename, dumps_dir)
        ],
        'targets': [
            '{0}.ttl.zip'.format(basename),
            '{0}.ttl.bz2'.format(basename)
        ]
    }


def task_fuseki():
    return {
        'doc': 'Push updated RDF to Fuseki',
        'file_dep': [
            'dist/mrtermer.ttl'
        ],
        'actions': [

            # Inferring and adding skos:narrower
            'skosify --no-enrich-mappings --transitive --narrower --no-mark-top-concepts --infer ./dist/mrtermer.ttl -o ./dist/mrtermer-skosify.ttl',

            # Pushing data to Fuseki
            's-put http://localhost:3030/ds/data http://data.ub.uio.no/mrtermer ./dist/mrtermer-skosify.ttl',

            # Cleaning up
            'rm ./dist/mrtermer-skosify.ttl'
        ]
    }