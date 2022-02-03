#
# Analyse files with Musly, Essentia, and Bliss, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021-2022 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import logging, pathlib, subprocess

_LOGGER = logging.getLogger(__name__)
NUM_BLISS_VALS = 20


def analyse_track(idx, analyser, abs_path):
    proc = subprocess.Popen([analyser, abs_path], shell=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=pathlib.Path(__file__).parent.parent.absolute())
    out = proc.communicate()[0].decode('utf-8')
    if out is None:
        _LOGGER.error('Failed to parse Bliss output for %s' % db_path)
        return None
    out = out.replace(',', '.').rstrip()
    parts = out.split(' ')
    if len(parts)!=NUM_BLISS_VALS:
        _LOGGER.error('Invalid result from Bliss for %s' % db_path)
        return None
    resp = []
    for part in parts:
        resp.append(float(part))

    # Tempo is first 
    return resp, int(resp[0]*412)
