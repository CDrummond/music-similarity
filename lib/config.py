#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import json
import logging
import os
from . import tracks_db

_LOGGER = logging.getLogger(__name__)


def fix_path(path):
    for e  in ['HOME', 'USERPROFILE', 'TMP']:
        if e in os.environ:
            if '$%s' % e in path:
                path = path.replace('$%s' % e, os.environ[e])
            elif '%%%s%%' % e in path:
                path = path.replace('%%%s%%' % e, os.environ[e])
    return path


def read_config(path, analyse):
    config={}

    if not os.path.exists(path):
        _LOGGER.error('%s does not exist' % path)
        exit(-1)
    try:
        with open(path, 'r') as configFile:
            config = json.load(configFile)
    except ValueError:
        _LOGGER.error('Failed to parse config file')
        exit(-1)
    except IOError:
        _LOGGER.error('Failed to read config file')
        exit(-1)

    # Check required keys are present
    for key in ['musly', 'essentia', 'paths']:
        if not key in config:
            _LOGGER.error("'%s' not in config file" % key)
            exit(-1)

    if analyse:
        for key in ['local', 'lms', 'db']:
            if not key in config['paths']:
                _LOGGER.error("'paths.%s' not in config file" % key)
                exit(-1)
    else:
        if not 'db' in config['paths']:
            _LOGGER.error("'paths.db' not in config file")
            exit(-1)

    # Ensure paths end with /
    # and replace HOME, etc, env vars in paths
    for key in config['paths']:
        config['paths'][key] = fix_path(config['paths'][key])
        if not config['paths'][key].endswith('/'):
            config['paths'][key]=config['paths'][key]+'/'

    if 'lmsdb' in config:
        config['lmsdb'] = fix_path(config['lmsdb'])

    # Check oaths exist
    if analyse:
        for key in ['local', 'lms', 'db']:
            if (key=='db' and not os.path.exists(config['paths'][key])) or (analyse and key=='local' and not os.path.exists(config['paths'][key])):
                _LOGGER.error("'%s' does not exist" % config['paths'][key])
                exit(-1)
    else:
        if not os.path.exists(config['paths']['db']):
            _LOGGER.error("'%s' does not exist" % config['paths']['db'])
            exit(-1)

    if 'lmsdb' in config and not os.path.exists(config['lmsdb']):
        _LOGGER.error("'%s' does not exist" % config['lmsdb'])
        exit(-1)

    if 'tmp' in config['paths'] and not os.path.exists(config['paths']['tmp']):
        _LOGGER.error("'%s' does not exist" % config['paths']['tmp'])
        exit(-1)

    # Cjeck general settings
    if not 'port' in config:
        config['port']=11000

    if not 'host' in config:
        config['host']='0.0.0.0'

    if not 'threads' in config:
        config['threads']=os.cpu_count()

    # Check/default musly settings
    if not 'lib' in config['musly']:
        _LOGGER.error("'musly.lib' not in config file" % key)
        exit(-1)
    else:
        config['musly']['lib'] = fix_path(config['musly']['lib'])
    if not 'extractlen' in config['musly']:
        config['musly']['extractlen']=120
    if not 'extractstart' in config['musly']:
        config['musly']['extractstart']=-210
    if not 'styletracks' in config['musly']:
        config['musly']['styletracks']=1000
    if not 'styletracksmethod' in config['musly']:
        config['musly']['styletracksmethod']='genres'

    # Check/default essentia settings
    if not 'enabled' in config['essentia']:
        config['essentia']['enabled']=True

    if config['essentia']['enabled']:
        if not 'bpm' in config['essentia']:
            config['essentia']['bpm']=20
        if not 'loudness' in config['essentia']:
            config['essentia']['loudness']=10
        if not 'filterkey' in config['essentia']:
            config['essentia']['filterkey']=True
        if not 'highlevel' in config['essentia']:
            config['essentia']['highlevel']=False
        if not 'filterattrib' in config['essentia']:
            config['essentia']['filterattrib']=True
        if not 'weight' in config['essentia'] or float(config['essentia']['weight'])<0 or float(config['essentia']['weight'])>1:
            config['essentia']['weight'] = 0.0
        if not config['essentia']['highlevel']:
            config['essentia']['weight'] = 0.0
        if analyse:
            if not 'extractor' in config['essentia']:
                _LOGGER.error("'essentia.extractor' not in config file")
                exit(-1)
            else:
                config['essentia']['extractor'] = fix_path(config['essentia']['extractor'])

    # Check genres, etc.
    if 'genres' in config:
        config['all_genres']=set()
        for i in range(len(config['genres'])):
            config['genres'][i]=set(config['genres'][i])
            config['all_genres'].update(config['genres'][i])

    if 'ignoregenre' in config:
        if isinstance(config['ignoregenre'], list):
            ignore=[]
            for item in config['ignoregenre']:
                ignore.append(tracks_db.normalize_artist(item))
            config['ignoregenre']=set(ignore)
        else:
            config['ignoregenre']=set([config['ignoregenre']])

    if 'normalize' in config:
        tracks_db.set_normalize_options(config['normalize'])

    return config
