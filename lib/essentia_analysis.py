#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021-2022 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import gzip, json, logging, os, pathlib, platform, subprocess

_LOGGER = logging.getLogger(__name__)
IS_WINDOWS = platform.system() == 'Windows'


def js_cache_name(path):
    if IS_WINDOWS:
        return path.encode('ascii', 'replace').decode('utf-8').replace('?', '_')
    return path


def process_essentia(data):
    key_scale = 'M' if data['tonal']['key_scale']=='major' else 'm'
    resp = {
              'bpm': int(data['rhythm']['bpm']),
              'loudness': float(data['lowlevel']['average_loudness']),
              'key': data['tonal']['key_key']+key_scale
           }
    if 'highlevel' in data:
        resp['danceable']=float(data['highlevel']['danceability']['all']['danceable'])
        resp['aggressive']=float(data['highlevel']['mood_aggressive']['all']['aggressive'])
        resp['electronic']=float(data['highlevel']['mood_electronic']['all']['electronic'])
        resp['acoustic']=float(data['highlevel']['mood_acoustic']['all']['acoustic'])
        resp['happy']=float(data['highlevel']['mood_happy']['all']['happy'])
        resp['party']=float(data['highlevel']['mood_party']['all']['party'])
        resp['relaxed']=float(data['highlevel']['mood_relaxed']['all']['relaxed'])
        resp['sad']=float(data['highlevel']['mood_sad']['all']['sad'])
        resp['dark']=float(data['highlevel']['timbre']['all']['dark'])
        resp['tonal']=float(data['highlevel']['tonal_atonal']['all']['tonal'])
        resp['voice']=float(data['highlevel']['voice_instrumental']['all']['voice'])
    return resp


def read_json_file(js):
    try:
        return process_essentia(json.load(js))
    except ValueError:
        return None


def read_json_string(js):
    try:
        return process_essentia(json.loads(js))
    except ValueError:
        return None


def analyse_track(idx, extractor, db_path, abs_path, cache_dir, highlevel):
    # Try to load previous JSON
    if len(cache_dir)>1:
        jsfile = "%s.json" % os.path.join(cache_dir, js_cache_name(db_path))
        jsfileGz = "%s.gz" % jsfile
        if os.path.exists(jsfile):
            # Plain, uncompressed
            with open(jsfile, 'r', encoding='utf8') as js:
                resp = read_json_file(js)
                if resp is not None:
                    return resp
        elif os.path.exists(jsfileGz):
            # GZIP compressed
            with gzip.open(jsfileGz, 'rt') as js:
                resp = read_json_file(js)
                if resp is not None:
                    return resp

        path = jsfile[:-(len(os.path.basename(jsfile)))-1]
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except:
                pass

    cmd = [extractor, abs_path, '-']
    if highlevel:
        cmd = [extractor, abs_path, '-', os.path.join('essentia', 'profile')]
    proc = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=pathlib.Path(__file__).parent.parent.absolute())
    out = proc.communicate()[0].decode('utf-8')
    if out is None:
        _LOGGER.error('Failed to parse Essentia output for %s' % db_path)
        return None
    resp = read_json_string(out)
    if resp is None:
        _LOGGER.error('Failed to parse Essentia output for %s (JSON failed)' % db_path)
        return None

    if len(cache_dir)>1:
        try:
            with gzip.open(jsfileGz, 'wt') as f:
                f.write(out)
        except:
            pass

    return resp
