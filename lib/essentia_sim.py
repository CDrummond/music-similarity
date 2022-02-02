#
# Analyse files with Musly, Essentia, and Bliss, and provide an API to retrieve similar tracks
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
max_sim = math.sqrt(len(tracks_db.ESSENTIA_HIGHLEVEL_ATTRIBS) + 1) # +1 for bpm
num_tracks = 0
attrib_list = []
tree = None


def init(db):
    global min_bpm, bpm_range, max_sim, num_tracks, attrib_list, tree
    if min_bpm is None:
        _LOGGER.debug('Loading essentia attribs from DB')
        cursor = db.get_cursor()
        cursor.execute('SELECT min(bpm), max(bpm) from tracks')
        row = cursor.fetchone()
        min_bpm = row[0]
        bpm_range = row[1] - min_bpm

        attr_list = []
        paths = []
        cols = 'file, bpm' # From lowlevel
        for ess in tracks_db.ESSENTIA_HIGHLEVEL_ATTRIBS:
            cols+=', %s' % ess

        cursor.execute('SELECT %s FROM tracks ORDER BY rowid ASC' % cols)
        for row in cursor:
            attribs=[]
            paths.append(row[0])
            for attr in range(len(tracks_db.ESSENTIA_HIGHLEVEL_ATTRIBS) + 1): # +1 for bpm
                if 0==attr:
                    attribs.append((row[attr+1]-min_bpm)/bpm_range)
                else:
                    attribs.append(row[attr+1])
            attr_list.append(attribs)

        attrib_list = numpy.array(attr_list)
        tree = cKDTree(attrib_list)
        num_tracks = len(paths)
        return paths
    return None
            

def get_similars(db, track_id):
    global attrib_list, max_sim, num_tracks, tree
    distances, indexes = tree.query(numpy.array([attrib_list[track_id]]), k=num_tracks)

    entries = []
    for i in range(min(len(indexes[0]), num_tracks)):
        entries.append({'id':indexes[0][i], 'sim':distances[0][i]/max_sim})

    return entries;
