#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021-2022 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import logging, math, numpy
from scipy.spatial import cKDTree
from . import tracks_db

_LOGGER = logging.getLogger(__name__)


min_bpm = None
bpm_range = None
max_sim = math.sqrt(len(tracks_db.ESSENTIA_HIGHLEVEL_ATTRIBS) + 2) # +2 for bpm, loudness
attrib_list = []
tree = None
num_tracks = 0


def init(db):
    global min_bpm, bpm_range, max_sim, attrib_list, tree, num_tracks
    if min_bpm is None:
        _LOGGER.debug('Loading essentia attribs from DB')
        cursor = db.get_cursor()
        cursor.execute('SELECT min(bpm), max(bpm) from tracks')
        row = cursor.fetchone()
        min_bpm = row[0]
        bpm_range = row[1] - min_bpm

        attr_list = []
        cols = 'bpm, loudness' # From lowlevel
        for ess in tracks_db.ESSENTIA_HIGHLEVEL_ATTRIBS:
            cols+=', %s' % ess

        cursor.execute('SELECT %s FROM tracks' % cols)
        for row in cursor:
            attribs=[]
            for attr in range(len(tracks_db.ESSENTIA_HIGHLEVEL_ATTRIBS) + 2): # +2 for bpm, loudness
                if 0==attr:
                    attribs.append((row[attr]-min_bpm)/bpm_range)
                else:
                    attribs.append(row[attr])
            attr_list.append(attribs)
            num_tracks+=1

        attrib_list = numpy.array(attr_list)
        tree = cKDTree(attrib_list)
            

def get_similars(db, track_id):
    init(db)
    global min_bpm, bpm_range, max_sim, attrib_list, tree, num_tracks
    distances, indexes = tree.query(numpy.array([attrib_list[track_id]]), k=num_tracks)

    entries = [1.0] * num_tracks
    for i in range(min(len(indexes[0]), num_tracks)):
        entries[indexes[0][i]] = distances[0][i]/max_sim

    return entries;
