#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

from . import tracks_db
import logging

_LOGGER = logging.getLogger(__name__)

VARIOUS_ARTISTS = ['various', 'various artists'] # Artist names are normalised, and coverted to lower case
CHRISTMAS_GENRES = ['Christmas', 'Xmas']

def same_artist_or_album(seeds, track, check_album_only=False, max_check=0):
    check = 0
    for seed in seeds:
        if seed['artist']==track['artist'] and not check_album_only:
            return True
        if seed['album']==track['album'] and 'albumartist' in seed and 'albumartist' in track and seed['albumartist']==track['albumartist'] and track['albumartist'] not in VARIOUS_ARTISTS:
            return True
        check+=1
        if max_check>0 and check>=max_check:
            return False
    return False


def genre_matches(config, seed_genres, track):
    if 'genres' not in track or len(track['genres'])<1:
        return True # Track has no genre? Then can't filter out...

    # Ignore genre for an artist?
    if 'ignoregenre' in config and track['artist'] in config['ignoregenre']:
        return True

    if len(seed_genres)<1:
        # No filtering for seed track genres
        if 'all_genres' in config:
            if len(track['genres'].intersection(config['all_genres']))>0:
                # Track's genre is in config list, but not in seeds, so filter out track
                return False
        # No seed genres, and track's genre not in filters, so accept track
        return True

    return len(seed_genres.intersection(track['genres']))>0


def is_christmas(track):
    if 'genres' in track and len(track['genres'])>=0:
        for genre in track['genres']:
            if genre in CHRISTMAS_GENRES:
                return True

    return False


def match_artist(artists, track):
    for artist in artists:
        if artist==track['artist'] or ('albumartist' in track and artist==track['albumartist']):
            return True
    return False


def match_album(albums, track):
    if (not 'album' in track) or ( ('albumartist' not in track) and ('artist' not in track)):
        return False

    album = '%s - %s' % (track['albumartist'] if 'albumartist' in track else track['artist'], track['album'])
    return album in albums


def match_title(titles, track):
    if not 'title' in track:
        return False

    return track['title'] in titles 


def check_duration(min_duration, max_duration, meta):
    if 'duration' not in meta or meta['duration'] is None or meta['duration']<=0:
        return True # No duration to check!

    if min_duration>0 and meta['duration']<min_duration:
        return False

    if max_duration>0 and meta['duration']>max_duration:
        return False

    return True


ess_attr_lim = None
def check_attribs(seed, candidate, max_bpm_diff, max_attr_diff):
    if 'bpm' not in seed or 'bpm' not in candidate:
        # No essentia attributes, so accept track
        return True

    if abs(seed['bpm']-candidate['bpm'])>max_bpm_diff:
        _LOGGER.debug('DISCARD %s %s due to BPM [%d / %d]' % (candidate['artist'], candidate['title'], seed['bpm'], candidate['bpm']))
        return False

    global ess_attr_lim
    if ess_attr_lim is None:
        if max_attr_diff>0.8:
            ess_attr_lim = 0.2
        elif max_attr_diff>0.6:
            ess_attr_lim = 0.3
        else:
            ess_attr_lim = 0.4

    # Determine the 4 most accurate Essentia attributes, and filter on those
    # These will be the ones closest to 1.0 or 0.0
    if not 'ess' in seed:
        attr=[]
        for ess in tracks_db.ESSENTIA_ATTRIBS:
            if ess != 'bpm' and ((seed[ess]>=(1.0-ess_attr_lim) and seed[ess]<1.0) or (seed[ess]>0.000001 and seed[ess]<=ess_attr_lim)):
               attr.append({'key':ess, 'val':abs(0.5-seed[ess])})
        attr=sorted(attr, key=lambda k: -1*k['val'])[:5]
        seed['ess']=[]
        for a in attr:
            seed['ess'].append(a['key'])
        _LOGGER.debug('SEED attribs: %s' % str(seed['ess']))
 
    for ess in seed['ess']:
        # Filter out tracks where attribute is in opposite end of spectrum
        if abs(seed[ess]-candidate[ess])>max_attr_diff:
            _LOGGER.debug('DISCARD %s %s due to %s [%f - %f]' % (candidate['artist'], candidate['title'], ess, seed[ess], candidate[ess]))
            return False
    #for ess in tracks_db.ESSENTIA_ATTRIBS:
    #    if 'bpm'!=ess and seed[ess]>=0.000001 and candidate[ess]>=0.000001 and seed[ess]<1.0 and candidate[ess]<1.0 and abs(seed[ess]-candidate[ess])>max_attr_diff:
    #        _LOGGER.debug('DISCARD %s %s due to %s [%f - %f]' % (candidate['artist'], candidate['title'], ess, seed[ess], candidate[ess]))
    #        return False
    return True

