#
# Analyse files with Musly, Essentia, and Bliss, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021-2022 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import logging, os, sqlite3, subprocess, urllib
from concurrent.futures import ThreadPoolExecutor

CUE_TRACK = '.CUE_TRACK.'
_LOGGER = logging.getLogger(__name__)

def get_cue_tracks(lms_db, lms_path, path, local_root_len, tmp_path):
    tracks=[]
    if lms_db is not None and lms_path is not None:
        # Convert local path into LMS path...
        lms_full_path = 'file://%s' % urllib.parse.quote('%s%s' % (lms_path, path[local_root_len:]), safe="/-_.!~*'()")
        # Get list of cue tracks from LMS db...
        cursor = lms_db.execute("select url, title from tracks where url like '%%%s#%%'" % lms_full_path)
        for row in cursor:
            parts=row[0].split('#')
            if 2==len(parts):
                times=parts[1].split('-')
                if 2==len(times):
                    track_path='%s%s%s%s-%s.mp3' % (tmp_path, path[local_root_len:], CUE_TRACK, times[0], times[1])
                    tracks.append({'file':track_path, 'start':times[0], 'end':times[1], 'title':row[1]})
    else:
        _LOGGER.debug("Can't get CUE tracks for %s - no LMS DB" % path)
    return tracks


def split_cue_track(path, track):
    _LOGGER.debug('Create %s' % track['file'])
    dirname=os.path.dirname(track['file'])
    end = float(track['end'])-float(track['start'])
    command=['ffmpeg', '-hide_banner', '-loglevel', 'panic', '-i', path, '-b:a', '128k', '-ss', track['start'], '-t', "%f" % end, track['file']]
    subprocess.Popen(command).wait()
    return True


def split_cue_tracks(files, num_threads):    
    # Create temporary folders
    for file in files:
        if 'track' in file:
            dirname=os.path.dirname(file['track']['file'])
            if not os.path.exists(dirname):
                os.makedirs(dirname)

    # Split into tracks
    futures_list = []
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        for file in files:
            if 'track' in file:
                futures = executor.submit(split_cue_track, file['src'], file['track'])
                futures_list.append(futures)
        for future in futures_list:
            try:
                future.result()
            except Exception as e:
                _LOGGER.debug("Thread exception? - %s" % str(e))
                pass

                          
def convert_to_cue_url(path):
    cue = path.find(CUE_TRACK)
    if cue>0:
        parts = path.replace(CUE_TRACK, '#').split('#')
        path='file://'+quote(parts[0])+'#'+parts[1]
        return path[:-4]
    return path


def convert_from_cue_path(path):
    hsh = path.find('#')
    if hsh>0:
        # Try to ensure this is really a CUE track, not a filename with #!!!
        # e.g. we should have Name.ext#start-end

        pth = path[:hsh]
        pos = path[hsh+1:]
        # Check we have 2 times
        times = pos.split('-')
        if len(times) != 2:
            return path
        # Check time parts are floats...
        try:
            start = float(times[0])
            end = float(times[1])
        except:
            return path

        # Check we have file extension before #
        dot = pth.find('.')
        if dot<0:
            return path
        ext = pth[dot+1:].lower()
        if ext not in ['m4a', 'mp3', 'ogg', 'flac', 'opus']:
            return path

        return path.replace('#', CUE_TRACK)+'.mp3'
    return path


def convert_to_source(path):
    cue = path.find(CUE_TRACK)
    return path[:cue] if cue>0 else path
