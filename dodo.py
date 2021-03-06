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
    'fuseki': 'http://127.0.0.1:3031/ds',
    'basename': 'mrtermer',
    'git_user': 'ubo-bot',
    'git_email': 'danmichaelo+ubobot@gmail.com',
}


def task_fetch_core():

    yield {
        'doc': 'Fetch remote files that have changed',
        'basename': 'fetch',
        'name': None
    }
    yield data_ub_tasks.git_pull_task_gen(config)
    for file in [
        {
            'remote': 'https://app.uio.no/ub/emnesok/data/mr/idtermer.txt',
             'local': 'src/idtermer.txt'
        },
        {
            'remote': 'https://app.uio.no/ub/emnesok/data/mr/idsteder.txt',
             'local': 'src/idsteder.txt'
        },
        {
            'remote': 'https://app.uio.no/ub/emnesok/data/mr/idformer.txt',
             'local': 'src/idformer.txt'
        },
        {
            'remote': 'https://rawgit.com/scriptotek/data_ub_ontology/master/ub-onto.ttl',
             'local': 'src/ub-onto.ttl'
        }
    ]:
        yield data_ub_tasks.fetch_remote_gen(file['remote'], file['local'], ['fetch_core:git-pull'])


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

        prepared = roald.prepare_export(format='rdfskos', include=[
            '%s.scheme.ttl' % config['basename'],
            'src/ub-onto.ttl',
        ])
        prepared.write('dist/%s.ttl' % config['basename'], format='turtle')
        logger.info('Wrote dist/%s.ttl', config['basename'])
        prepared.write('dist/%s.nt' % config['basename'], format='nt')
        logger.info('Wrote dist/%s.nt', config['basename'])

    return {
        'doc': 'Build distribution files (RDF/SKOS + MARC21XML) from source files',
        'actions': [build_dist],
        'file_dep': [
            'src/idtermer.txt',
            'src/idsteder.txt',
            'src/idformer.txt',
            'src/ub-onto.ttl',
            '%s.scheme.ttl' % config['basename']
        ],
        'targets': [
            '%s.json' % config['basename'],
            'dist/%s.marc21.xml' % config['basename'],
            'dist/%s.ttl' % config['basename'],
            'dist/%s.nt' % config['basename'],
        ]
    }


def task_git_push():
    return data_ub_tasks.git_push_task_gen(config)


def task_publish_dumps():
    return data_ub_tasks.publish_dumps_task_gen(config['dumps_dir'], [
        '%s.marc21.xml' % config['basename'],
        '%s.ttl' % config['basename'],
        '%s.nt' % config['basename'],
    ])

def task_fuseki():
    return data_ub_tasks.fuseki_task_gen(config)
