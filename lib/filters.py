#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

from . import tracks_db


VARIOUS_ARTISTS = ['various', 'various artists'] # Artist names are normalised, and coverted to lower case
CHRISTMAS_GENRES = ['Christmas', 'Xmas']
ESS_ATTR_LIM = 0.2


def genre_matches(config, seed_genres, track):
    if 'genres' not in track or len(track['genres'])<1:
        return True # Track has no genre? Then can't filter out...

    if len(seed_genres)<1:
        # Seed is not in a genre group, but candidate track is in a genre group - so filter out track
        if 'all_genres' in config and len(track['genres'].intersection(config['all_genres']))>0:
            return False

        # No seed genres, and track's genre not in group, so accept track
        return True

    return len(seed_genres.intersection(track['genres']))>0


def is_christmas(track):
    if 'genres' in track and len(track['genres'])>=0:
        for genre in track['genres']:
            if genre in CHRISTMAS_GENRES:
                return True

    return False


def check_duration(min_duration, max_duration, meta):
    if 'duration' not in meta or meta['duration'] is None or meta['duration']<=0:
        return True # No duration to check!

    if min_duration>0 and meta['duration']<min_duration:
        return False

    if max_duration>0 and meta['duration']>max_duration:
        return False

    return True


def check_attribs(seed, candidate, max_bpm_diff, max_attr_diff):
    if 'bpm' not in seed or 'bpm' not in candidate:
        # No essentia attributes, so accept track
        return None

    if abs(seed['bpm']-candidate['bpm'])>max_bpm_diff:
        return 'bpm - %s/%s' % (seed['bpm'], candidate['bpm'])

    ess_attr_high = 1.0 - ESS_ATTR_LIM
    ess_attr_low = ESS_ATTR_LIM
    # Determine the 4 most accurate Essentia attributes, and filter on those
    # These will be the ones closest to 1.0 or 0.0
    if not 'ess' in seed:
        attr=[]
        for ess in tracks_db.ESSENTIA_ATTRIBS:
            if ess != 'bpm' and ((seed[ess]>=ess_attr_high and seed[ess]<1.0) or (seed[ess]>0.000001 and seed[ess]<=ess_attr_low)):
               attr.append({'key':ess, 'val':abs(0.5-seed[ess])})
        attr=sorted(attr, key=lambda k: -1*k['val'])[:4]
        seed['ess']=[]
        for a in attr:
            seed['ess'].append(a['key'])
 
    for ess in seed['ess']:
        # Filter out tracks where attribute is in opposite end of spectrum
        if (seed[ess]>=ess_attr_high and candidate[ess]<(ess_attr_high-max_attr_diff)) or (seed[ess]<=ess_attr_low and candidate[ess]>(ess_attr_low+max_attr_diff)):
        #if abs(seed[ess]-candidate[ess])>max_attr_diff:
            return '%s - %f/%f' % (ess, seed[ess], candidate[ess])
    #for ess in tracks_db.ESSENTIA_ATTRIBS:
    #    if 'bpm'!=ess and seed[ess]>=0.000001 and candidate[ess]>=0.000001 and seed[ess]<1.0 and candidate[ess]<1.0 and abs(seed[ess]-candidate[ess])>max_attr_diff:
    #        return '%s - %f/%f' % (ess, seed[ess], candidate[ess])
    return None

