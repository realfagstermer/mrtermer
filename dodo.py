# encoding=utf8
import logging
import logging.config
from doit import get_var
from roald import Roald
from doit_ubo import publish_dumps_task_gen, fuseki_task_gen, git_push_task_gen, fetch_remote

logging.config.fileConfig('logging.cfg')
logger = logging.getLogger(__name__)

config = {
    'dumps_dir': get_var('dumps_dir', './dumps'),
    'graph': 'http://data.ub.uio.no/mrtermer',
    'fuseki': 'http://localhost:3030/ds',
    'basename': 'mrtermer'
}


def task_fetch():

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
        roald.set_uri_format(
            'http://data.ub.uio.no/%s/c{id}' % config['basename'])
        roald.save('%s.json' % config['basename'])
        logger.info('Wrote %s.json', config['basename'])

        marc21options = {
            'vocabulary_code': 'noubomr',
            'created_by': 'NoOU'
        }
        roald.export('dist/%s.marc21.xml' %
                     config['basename'], format='marc21', **marc21options)
        logger.info('Wrote dist/%s.marc21.xml', config['basename'])

        roald.export('dist/%s.ttl' % config['basename'], format='rdfskos',
                     include=['%s.scheme.ttl' % config['basename'], 'ubo-onto.ttl'])
        logger.info('Wrote dist/%s.ttl', config['basename'])

    return {
        'doc': 'Build distribution files (RDF/SKOS + MARC21XML) from source files',
        'actions': [build_dist],
        'file_dep': [
            'src/idtermer.txt',
            'ubo-onto.ttl',
            '%s.scheme.ttl' % config['basename']
        ],
        'targets': [
            '%s.json' % config['basename'],
            'dist/%s.marc21.xml' % config['basename'],
            'dist/%s.ttl' % config['basename'],
        ]
    }


def task_git_push():
    return git_push_task_gen(config)


def task_publish_dumps():
    return publish_dumps_task_gen(config)


def task_fuseki():
    return fuseki_task_gen(config)
