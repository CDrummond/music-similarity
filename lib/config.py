#
# Analyse files with Musly, Essentia, and Bliss, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021-2022 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import json, logging, os, pathlib, platform
from . import tracks_db

_LOGGER = logging.getLogger(__name__)
# Only Linux and mac, for now, support highlevel analysis
SUPPORT_ESSENTIA_HIGHLEVEL = ['linux', 'mac']
# Only Linux, for now, supports bliss
SUPPORT_BLISS = ['linux']

def exit_with_error(s):
    _LOGGER.error(s)
    exit(-1)


def fix_path(path):
    '''
    Replace env vars in paths
    '''
    for e  in ['HOME', 'USERPROFILE', 'TMP']:
        if e in os.environ:
            if '$%s' % e in path:
                path = path.replace('$%s' % e, os.environ[e])
            elif '%%%s%%' % e in path:
                path = path.replace('%%%s%%' % e, os.environ[e])

    if platform.system() == 'Linux':
        path = path.replace('~/', '%s/' % os.environ['HOME']) # ~/x => /home/<user>/x
        path = path.replace('~', '/home/') # ~user/xx => /home/user/xx

    return path


def update_paths(config, analyse, sys, musly, essentia_extractor, bliss_analyser):
    '''
    Update paths settings for detected OS
    '''

    # Set libmusy path, if not already in config
    if musly is not None and not 'lib' in config['musly']:
        _LOGGER.debug('(Defaults) musly.lib set to %s' % musly)
        config['musly']['lib']=musly

    # Update PATH - mainly for windows so that libmusly can find ffmpeg, etc.
    if analyse:
        if sys is not None:
            exe_folder = os.path.join(pathlib.Path(__file__).parent.parent, sys)
            if sys=='windows':
                os.environ['PATH']='%s;%s' % (exe_folder, os.environ['PATH'])
                _LOGGER.debug('Added %s to PATH' % exe_folder)

        # Set essentia extractor path, if not already in config
        if essentia_extractor is not None and not 'extractor' in config['essentia']:
            config['essentia']['extractor']=essentia_extractor
            _LOGGER.debug('(Defaults) essentia.extractor set to %s' % essentia_extractor)
            if not 'highlevel' in config['essentia']:
                config['essentia']['highlevel'] = sys in SUPPORT_ESSENTIA_HIGHLEVEL
                _LOGGER.debug('(Defaults) essentia.highlevel set to %s' % str(config['essentia']['highlevel']))

        # Set bliss analyser path, if not already in config
        if bliss_analyser is not None and not 'analyser' in config['bliss']:
            config['bliss']['analyser']=bliss_analyser
            _LOGGER.debug('(Defaults) bliss.analyser set to %s' % bliss_analyser)

    elif not 'highlevel' in config['essentia']:
        config['essentia']['highlevel'] = sys in SUPPORT_ESSENTIA_HIGHLEVEL
        _LOGGER.debug('(Defaults) essentia.highlevel set to %s' % str(config['essentia']['highlevel']))


def system_name():
    system = platform.system()
    if system == 'Linux':
        return 'linux'
    if system == 'Windows':
        return 'windows'
    if system == 'Darwin':
        return 'mac'
    return 'other'


def setup_paths(config, analyse):
    '''
    Try to configure Musly and Essentia lib/binary paths based upon OS
    '''
    system = system_name()
    arch = platform.architecture()[0]
    proc = platform.processor()
    root_folder = pathlib.Path(__file__).parent.parent

    if system == 'linux':
        if proc == 'x86_64':
            update_paths(config, analyse, 'linux', 'linux/x86-64/libmusly.so', '%s/linux/x86-64/essentia_streaming_extractor_music' % root_folder, '%s/linux/x86-64/bliss-analyse' % root_folder)
            return
        else: # TODO: Check on Pi
            update_paths(config, analyse, 'linux', 'linux/armv7l/libmusly.so', None)
            return
    elif system == 'windows':
        if arch.startswith('64'): # 64-bit Python
            update_paths(config, analyse, 'windows', 'windows\\mingw64\\libmusly.dll', '%s\\windows\\streaming_extractor_music.exe' % root_folder, None)
            return
        else:  # 32-bit Python
            update_paths(config, analyse, 'windows', 'windows\\mingw32\\libmusly.dll', '%s\\windows\\streaming_extractor_music.exe' % root_folder, None)
            return
    elif system == 'mac':
        if proc == 'i386':
            update_paths(config, analyse, 'mac', 'mac/i386/libmusly.dylib', '%s/mac/streaming_extractor_music' % root_folder, None)
            return
    #    else: # M1??? Can use x86_64 binaries on M1?
    #        update_paths(config, analyse, 'mac', 'mac/m1/libmusly.dylib', '%s/mac/streaming_extractor_music' % root_folder)
    #        return

    if not 'lib' in config['musly'] or (analyse and config['essentia']['enabled'] and not 'extractor' in config['essentia']):
        exit_with_error('No known binaries, etc, for %s / %s / %s' % (system, proc, arch))


def which(program):
    '''
    Return path of program
    '''
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ['PATH'].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def check_binaries(config):
    '''
    Check that binaries are in PATH
    '''
    apps = []
    if config['essentia']['enabled']:
        apps.append(config['essentia']['extractor'])

    # libmusly uses ffmpeg/ffprobe under Windows
    if system_name()=='windows':
        apps.append('ffmpeg.exe')
        apps.append('ffprobe.exe')

    if len(apps)>0:
        for app in apps:
            appPath = which(app)
            if appPath is None:
                if config['essentia']['enabled'] and app == config['essentia']['extractor']:
                    _LOGGER.info('Essentia extractor not in PATH, Essentia analysis disabled')
                    config['essentia']['enabled'] = False
                else:
                    exit_with_error('%s is not in PATH or is not executable' % app)
            else:
                if app == appPath:
                    _LOGGER.info('Found: %s' % appPath)
                else:
                    _LOGGER.info('Found: %s -> %s' % (app, appPath))


def read_config(path, analyse):
    config={}

    if not os.path.exists(path):
        exit_with_error('%s does not exist' % path)
    try:
        with open(path, 'r') as configFile:
            config = json.load(configFile)
    except ValueError:
        exit_with_error('Failed to parse config file')

    except IOError:
        exit_with_error('Failed to read config file')

    # Check required keys are present
    if not 'paths' in config:
        exit_with_error("'paths' not in config file")

    if analyse:
        for key in ['local', 'db']:
            if not key in config['paths']:
                exit_with_error("'paths.%s' not in config file" % key)
    else:
        if not 'db' in config['paths']:
            exit_with_error("'paths.db' not in config file")

    # Ensure paths end with /
    # and replace HOME, etc, env vars in paths
    for key in config['paths']:
        config['paths'][key] = fix_path(config['paths'][key])
        if not config['paths'][key].endswith(os.sep):
            config['paths'][key]=config['paths'][key]+os.sep

    if 'lmsdb' in config:
        config['lmsdb'] = fix_path(config['lmsdb'])

    # Check paths exist
    if analyse:
        for key in ['local', 'db']:
            if (key=='db' and not os.path.exists(config['paths'][key])) or (analyse and key=='local' and not os.path.exists(config['paths'][key])):
                exit_with_error("'%s' does not exist" % config['paths'][key])
    else:
        if not os.path.exists(config['paths']['db']):
            exit_with_error("'%s' does not exist" % config['paths']['db'])

    if analyse and 'lmsdb' in config:
        if not os.path.exists(config['lmsdb']):
            exit_with_error("'%s' does not exist" % config['lmsdb'])
        if not 'lms' in config['paths']:
            exit_with_error("'paths.lms' not in config file")
        if not os.path.exists(config['paths']['lms']):
            exit_with_error("'%s' does not exist" % config['paths']['lms'])

    if 'tmp' in config['paths'] and not os.path.exists(config['paths']['tmp']):
        exit_with_error("'%s' does not exist" % config['paths']['tmp'])

    # Check general settings
    if not 'port' in config:
        config['port']=11000

    if not 'host' in config:
        config['host']='0.0.0.0'

    if not 'threads' in config:
        config['threads']=os.cpu_count()

    if not 'simalgo' in config:
        config['simalgo']='musly'

    # Ensure 'musly' is in config
    if not 'musly' in config:
        config['musly']={'enabled':True}

    # Ensure 'essentia' is in config
    if not 'essentia' in config:
        config['essentia']={'enabled':True}

    # Ensure 'bliss' is in config
    if not 'bliss' in config:
        config['bliss']={'enabled':system_name() in SUPPORT_BLISS}

    setup_paths(config, analyse)

    # Check/default musly settings
    if not 'enabled' in config['musly']:
        config['musly']['enabled']=True

    if config['musly']['enabled']:
        if not 'lib' in config['musly']:
            exit_with_error("'musly.lib' not in config file" % key)
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
        if not 'filterkey' in config['essentia']:
            config['essentia']['filterkey']=True
        if not 'highlevel' in config['essentia']:
            config['essentia']['highlevel']=False
        if not 'filterattrib' in config['essentia']:
            config['essentia']['filterattrib']=True
        if not 'filterattrib_count' in config['essentia']:
            config['essentia']['filterattrib_count']=4
        if not 'filterattrib_lim' in config['essentia']:
            config['essentia']['filterattrib_lim']=0.2
        if not 'filterattrib_cand' in config['essentia']:
            config['essentia']['filterattrib_cand']=0.4
        if not 'attrmix_yes' in config['essentia']:
            config['essentia']['attrmix_yes']=0.6
        if not 'attrmix_no' in config['essentia']:
            config['essentia']['attrmix_no']=0.4

        if analyse:
            if not 'extractor' in config['essentia']:
                exit_with_error("'essentia.extractor' not in config file")
            else:
                config['essentia']['extractor'] = fix_path(config['essentia']['extractor'])
    else:
        config['essentia']['highlevel']=False

    # Check/default bliss settings
    if not 'enabled' in config['bliss']:
        config['bliss']['enabled']=system_name() in SUPPORT_BLISS

    if config['bliss']['enabled']:
        if analyse:
            if not 'analyser' in config['bliss']:
                exit_with_error("'bliss.analyser' not in config file")
            else:
                config['bliss']['analyser'] = fix_path(config['bliss']['analyser'])

    # Check genres, etc.
    if 'genres' in config:
        config['all_genres']=set()
        for i in range(len(config['genres'])):
            config['genres'][i]=set(config['genres'][i])
            config['all_genres'].update(config['genres'][i])

    if 'excludegenres' in config and len(config['excludegenres'])>0:
        config['excludegenres']=set(config['excludegenres'])
    else:
        config['excludegenres']=None

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

    if not 'minduration' in config:
        config['minduration']=30

    if not 'maxduration' in config:
        config['maxduration']=30*60

    if analyse:
        check_binaries(config)

    return config
