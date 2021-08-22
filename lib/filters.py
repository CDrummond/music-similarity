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
            for tg in track['genres']:
                if tg in config['all_genres']:
                    # Track's genre is in config list, but not in seeds, so filter out track
                    return False
        # No seed genres, and track's genre not in filters, so accept track
        return True

    for sg in seed_genres:
        if sg in track['genres']:
            return True

    return False


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


def check_attribs(seed, candidate):
    if 'bpm' not in seed or 'bpm' not in candidate:
        # No essentia attributes, so accept track
        return True

    if abs(seed['bpm']-candidate['bpm'])>50:
        #_LOGGER.debug('DISCARD %s %s due to BPM' % (candidate['artist'], candidate['title']))
        return False

    # Determine the 4 most accurate Essentia attributes, and filter on those
    # These will be the ones closes to 1.0 or 0.0
    if not 'ess' in seed:
        attr=[]
        for ess in tracks_db.ESSENTIA_ATTRIBS:
            if ess != 'bpm' and (seed[ess]>=0.8 or seed[ess]<=0.2):
               attr.append({'key':ess, 'val':abs(0.5-seed[ess])})
        attr=sorted(attr, key=lambda k: -1*k['val'])[:4]
        seed['ess']=[]
        for a in attr:
            seed['ess'].append(a['key'])
        #_LOGGER.debug('SEED attribs: %s' % str(seed['ess']))
 
    for ess in seed['ess']:
        if abs(seed[ess]-candidate[ess])>0.75:
            #_LOGGER.debug('DISCARD %s %s due to %s [%f - %f]' % (candidate['artist'], candidate['title'], ess, seed[ess], candidate[ess]))
            return False
    #for ess in tracks_db.ESSENTIA_ATTRIBS:
    #    if not ess in ['bpm', 'danceable'] and seed[ess]>=0.001 and seed[ess]<=0.9999 and candidate[ess]>=0.001 and candidate[ess]<=0.9999 and abs(seed[ess]-candidate[ess])>0.75:
    #        _LOGGER.debug('DISCARD %s %s due to %s [%f - %f]' % (candidate['artist'], candidate['title'], ess, seed[ess], candidate[ess]))
    #        return False
    return True


def check_attribs_all(seeds, candidate):
    for seed in seeds:
        if not check_attribs(seed, candidate):
            return False
    return True
