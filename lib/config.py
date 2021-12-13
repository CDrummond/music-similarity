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

    for key in ['musly', 'essentia', 'paths']:
        if not key in config:
            _LOGGER.error("'%s' not in config file" % key)
            exit(-1)

    if analyse:
        for key in ['local', 'lms', 'db']:
            if not key in config['paths']:
                _LOGGER.error("'paths.%s' not in config file" % key)
                exit(-1)
            if (key=='db' and not os.path.exists(config['paths'][key])) or (analyse and key=='local' and not os.path.exists(config['paths'][key])):
                _LOGGER.error("'%s' does not exist" % config['paths'][key])
                exit(-1)
    else:
        if not 'db' in config['paths']:
            _LOGGER.error("'paths.db' not in config file")
            exit(-1)
        if not os.path.exists(config['paths']['db']):
            _LOGGER.error("'%s' does not exist" % config['paths']['db'])
            exit(-1)

    for key in config['paths']:
        if not config['paths'][key].endswith('/'):
            config['paths'][key]=config['paths'][key]+'/'

    if 'tmp' in config['paths'] and not os.path.exists(config['paths']['tmp']):
        _LOGGER.error("'%s' does not exist" % config['paths']['tmp'])
        exit(-1)

    if not 'port' in config:
        config['port']=11000

    if not 'host' in config:
        config['host']='0.0.0.0'

    if not 'threads' in config:
        config['threads']=os.cpu_count()

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
        if analyse and not 'extractor' in config['essentia']:
            _LOGGER.error("'essentia.extractor' not in config file")
            exit(-1)

    if not 'lib' in config['musly']:
        _LOGGER.error("'musly.lib' not in config file" % key)
        exit(-1)
    if not 'extractlen' in config['musly']:
        config['musly']['extractlen']=120
    if not 'extractstart' in config['musly']:
        config['musly']['extractstart']=-210
    if not 'styletracks' in config['musly']:
        config['musly']['styletracks']=1000
    if not 'styletracksmethod' in config['musly']:
        config['musly']['styletracksmethod']='genres'

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
