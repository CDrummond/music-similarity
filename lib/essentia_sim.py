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
attrib_list = []
total_tracks = 0
tree = None


def init(db):
    global min_bpm, bpm_range, max_sim, attrib_list, total_tracks, tree
    if min_bpm is None:
        _LOGGER.debug('Loading essentia attribs from DB')
        cursor = db.get_cursor()
        cursor.execute('SELECT min(bpm), max(bpm) from tracks')
        row = cursor.fetchone()
        if row[0] is None or row[1] is None:
            min_bpm = 0
            bpm_range = 100
        else:
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
            loggedError = False
            for attr in range(len(tracks_db.ESSENTIA_HIGHLEVEL_ATTRIBS) + 1): # +1 for bpm
                if row[attr+1] is None:
                    attribs.append(0.0)
                    if not loggedError:
                        _LOGGER.error('%s has not been analysed with Essentia' % row[0])
                        loggedError = True
                elif 0==attr:
                    attribs.append((row[attr+1]-min_bpm)/bpm_range)
                else:
                    attribs.append(row[attr+1])
            attr_list.append(attribs)

        attrib_list = numpy.array(attr_list)
        tree = cKDTree(attrib_list)
        total_tracks = len(paths)
        return paths
    return None
            

def get_similars(track_id, num_tracks):
    global attrib_list, max_sim, total_tracks, tree
    if num_tracks>total_tracks or num_tracks<0:
        num_tracks = total_tracks
    distances, indexes = tree.query(numpy.array([attrib_list[track_id]]), k=num_tracks)

    entries = []
    for i in range(min(len(indexes[0]), num_tracks)):
        entries.append({'id':indexes[0][i], 'sim':distances[0][i]/max_sim})

    return entries;
