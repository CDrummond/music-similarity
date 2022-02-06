#
# Analyse files with Musly, Essentia, and Bliss, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021-2022 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import logging, pickle, math, numpy
from scipy.spatial import cKDTree
from . import bliss_analysis, tracks_db

_LOGGER = logging.getLogger(__name__)



attrib_list = []
max_sim = None
tree = None


def init(db):
    global attrib_list, max_sim, tree
    if tree is None:
        _LOGGER.debug('Loading bliss from DB')
        cursor = db.get_cursor()

        attr_list = []
        paths = []
        empty = [0.0] * bliss_analysis.NUM_BLISS_VALS
        cursor.execute('SELECT file, bliss FROM tracks ORDER BY rowid ASC')
        for row in cursor:
            paths.append(row[0])
            if row[1] is None:
                _LOGGER.error('%s has not been analysed with Bliss' % row[0])
                attr_list.append(empty)
            else:
                attr_list.append(pickle.loads(row[1]))

        if max_sim is None:
            max_sim = math.sqrt(len(attr_list))
        attrib_list = numpy.array(attr_list)
        tree = cKDTree(attrib_list)
        return paths
    return None
            

def get_similars(track_id, num_tracks):
    global attrib_list, max_sim, tree
    distances, indexes = tree.query(numpy.array([attrib_list[track_id]]), k=num_tracks)

    entries = []
    for i in range(min(len(indexes[0]), num_tracks)):
        entries.append({'id':indexes[0][i], 'sim':distances[0][i]/max_sim})

    return entries;
