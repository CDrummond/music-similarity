#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import logging
import math
import os
import sys
from . import tracks_db, musly

_LOGGER = logging.getLogger(__name__)

def test_jukebox(app_config, jukebox_path, repeat):
    _LOGGER.info('Testing musly')

    mus = musly.Musly(app_config['musly']['lib'])
    meta_db = tracks_db.TracksDb(app_config)
    (paths, tracks) = mus.get_alltracks_db(meta_db.get_cursor())

    while True:
        ids = None

        # If we can, load musly from jukebox...
        if os.path.exists(jukebox_path):
            ids = mus.get_jukebox_from_file(jukebox_path)

        if ids==None or len(ids)!=len(tracks):
            _LOGGER.info('Adding tracks from DB to musly')
            ids = mus.add_tracks(tracks, app_config['musly']['styletracks'], app_config['musly']['styletracksmethod'], meta_db)
            mus.write_jukebox(jukebox_path)

        meta_db.close()
        mta=musly.MuslyTracksAdded(paths, tracks, ids)

        simtracks = mus.get_similars( mta.mtracks, mta.mtrackids, 0 )
        if len(simtracks)<2:
            _LOGGER.error('Too few tracks returned from similarity query???')
        else:
            simtracks = simtracks[:51]
            sims=[]
            nans=0
            for i in range(1, len(simtracks)):
                _LOGGER.debug('[%i] ID:%i Sim:%f' % (i, simtracks[i]['id'], simtracks[i]['sim']))
                if math.isnan(simtracks[i]['sim']):
                    nans += 1
                elif simtracks[i]['sim'] not in sims:
                    sims.append(simtracks[i]['sim'])
            if nans>0:
                if not repeat:
                    _LOGGER.error('Musly returned an invalid similarity? Suggest you remove %s (and perhaps alter styletracks in config?)' % jukebox_path)
                    sys.exit(-1)
            elif len(sims)<=1:
                if not reopeat:
                    _LOGGER.error('All similarities the same? Suggest you remove %s (and perhaps alter styletracks in config?)' % jukebox_path)
                    sys.exit(-1)
            else:
                _LOGGER.info('Musly returned %d different similarities for %d tracks' % (len(sims), len(simtracks)-1))
                return
        if repeat:
            _LOGGER.error('All similarities the same, or invalid similarity returned. Deleteing jukebox and re-trying')
            os.remove(jukebox_path)
