#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import gzip, json, logging, os, pathlib, subprocess

_LOGGER = logging.getLogger(__name__)


def read_json_file(js):
    try:
        data = json.load(js)

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
    except ValueError:
        return None


def analyse_track(idx, extractor, db_path, abs_path, tmp_path, cache_dir, highlevel):
    # Try to load previous JSON
    if len(cache_dir)>1:
        jsfile = "%s/%s.json" % (cache_dir, db_path)
        jsfileGz = "%s.gz" % jsfile
        if os.path.exists(jsfile):
            # Plain, uncompressed
            with open(jsfile, 'r') as js:
                resp = read_json_file(js)
                if resp is not None:
                    return resp
        elif os.path.exists(jsfileGz):
            # GZIP compressed
            with gzip.open(jsfileGz, 'r') as js:
                resp = read_json_file(js)
                if resp is not None:
                    return resp

        path = jsfile[:-(len(os.path.basename(jsfile)))-1]
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except:
                pass
    else:
        jsfile = "%s/essentia-%d.json" % (tmp_path, idx)

    if not os.path.exists(jsfile):
        cmd = [extractor, abs_path, jsfile]
        if highlevel:
            cmd = [extractor, abs_path, jsfile, os.path.join('essentia', 'profile')]
        subprocess.call(cmd, shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=pathlib.Path(__file__).parent.parent.absolute())
    if not os.path.exists(jsfile):
        return None
    try:
        resp = None
        with open(jsfile, 'r') as js:
            resp = read_json_file(js)
        if len(cache_dir)>1:
            try:
                subprocess.call(['gzip', jsfile])
            except:
                pass # Don't throw errors - as may not have gzip?
        else:
            os.remove(jsfile)
        return resp
    except ValueError:
        _LOGGER.error('Failed to parse %s for %s' % (jsfile, db_path))
    return None
