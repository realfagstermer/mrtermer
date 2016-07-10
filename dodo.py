# encoding=utf8
from doit import get_var
from roald import Roald

import logging
import logging.config
logging.config.fileConfig('logging.cfg')
logger = logging.getLogger(__name__)

import data_ub_tasks

config = {
    'dumps_dir': get_var('dumps_dir', '/opt/data.ub/www/default/dumps'),
    'dumps_dir_url': get_var('dumps_dir_url', 'http://data.ub.uio.no/dumps'),
    'graph': 'http://data.ub.uio.no/mrtermer',
    'fuseki': 'http://localhost:3031/ds',
    'basename': 'mrtermer',
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
            'git config --unset user.name',
            'git config --unset user.email',
        ]
    }
    remote_path = 'https://app.uio.no/ub/emnesok/data/mr/'
    for basename in ['idtermer.txt', 'idsteder.txt', 'idformer.txt']:
        remote = remote_path + basename
        local = 'src/' + basename
        etag_cache = local + '.etag'
        yield {
            'name': local,
            'actions': [(data_ub_tasks.fetch_remote, [], {
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
            'src/idsteder.txt',
            'src/idformer.txt',
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
    return data_ub_tasks.git_push_task_gen(config)


def task_publish_dumps():
    return data_ub_tasks.publish_dumps_task_gen(config['dumps_dir'], [
        '%s.marc21.xml' % config['basename'],
        '%s.ttl' % config['basename']
    ])

def task_fuseki():
    return data_ub_tasks.fuseki_task_gen(config)
