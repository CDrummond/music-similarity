#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021-2022 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

from . import tracks_db


VARIOUS_ARTISTS = ['various', 'various artists'] # Artist names are normalised, and coverted to lower case
CHRISTMAS_GENRES = ['Christmas', 'Xmas']


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


# http://www.harmonic-mixing.com/Images/camelotHarmonicMixing.jpg
# A flat => G sharp
CAMELOT = {'BM':'1B', 'F#M':'2B', 'C#M':'3B', 'G#M':'4B', 'D#M':'5B', 'A#M':'6B', 'FM':'7B', 'CM':'8B', 'GM':'9B', 'DM':'10B', 'AM':'11B', 'EM':'12B',
           'G#m':'1A', 'D#m':'2A', 'A#m':'3A', 'Fm':'4A', 'Cm':'5A', 'Gm':'6A', 'Dm':'7A', 'Am':'8A', 'Em':'9A', 'Bm':'10A', 'F#m':'11A', 'C#m':'12A',
           # Also match on flats - just in case Essentia provides these...
           'GbM':'2B', 'DbM':'3B', 'AbM':'4B', 'EbM':'5B', 'BbM':'6B',
           'Abm':'1A', 'Ebm':'2A', 'Bbm':'3A', 'Gbm':'11A', 'Dbm':'12A'}

camelot = None # Map from 1B, etc, to a set of matches

def init_camelot():
    global camelot
    camelot = {}
    for key in CAMELOT:
        i = int(CAMELOT[key][:-1])
        grp = CAMELOT[key][-1:]
        match = set()
        match.add(CAMELOT[key]) # Match same code
        match.add('%d%s' % (i, 'B' if grp == 'A' else 'A')) # match (e.g) 3B -> 3A
        match.add('%d%s' % (i-1 if i>1 else 12, grp))
        match.add('%d%s' % (i+1 if i<12 else 1, grp))
        camelot[CAMELOT[key]] = match


def check_attribs(seed, candidate, ess_cfg):
    if 'bpm' not in seed or 'bpm' not in candidate:
        # No essentia attributes, so accept track
        return None

    if ess_cfg['bpm']<150 and abs(seed['bpm']-candidate['bpm'])>ess_cfg['bpm']:
        return 'bpm - %s/%s' % (str(seed['bpm']), str(candidate['bpm']))

    if ess_cfg['filterkey']:
        # Use camelot codes to test if can mix keys
        seed_cam = CAMELOT[seed['key']] if seed['key'] in CAMELOT else None
        if seed_cam is not None:
            candidate_cam = CAMELOT[candidate['key']] if candidate['key'] in CAMELOT else None
            if candidate_cam is None:
                return 'key - %s (%s) / %s (%s)' % (seed['key'], seed_cam, candidate['key'], 'None')
            global camelot
            if camelot is None:
                init_camelot()
            if candidate_cam not in camelot[seed_cam]:
                return 'key - %s (%s) / %s (%s)' % (seed['key'], seed_cam, candidate['key'], candidate_cam)

    if ess_cfg['highlevel'] and ess_cfg['filterattrib']:
        ess_attr_high = 1.0 - ess_cfg['essentia']['filterattrib_lim']
        ess_attr_low = ess_cfg['essentia']['filterattrib_lim']
        ess_cand_attr_high = 1.0 - config['essentia']['filterattrib_cand']
        ess_cand_attr_low = config['essentia']['filterattrib_cand']

        # Determine the 4 most accurate Essentia attributes, and filter on those
        # These will be the ones closest to 1.0 or 0.0
        if not 'ess' in seed:
            attr=[]
            for ess in tracks_db.ESSENTIA_HIGHLEVEL_ATTRIBS:
                if ((seed[ess]>=ess_attr_high and seed[ess]<1.0) or (seed[ess]>0.000001 and seed[ess]<=ess_attr_low)):
                    attr.append({'key':ess, 'val':abs(0.5-seed[ess])})
            attr=sorted(attr, key=lambda k: -1*k['val'])[:ess_cfg['filterattrib_count']]
            seed['ess']=[]
            for a in attr:
                seed['ess'].append(a['key'])

        for ess in seed['ess']:
            # Filter out tracks where attribute is in opposite end of spectrum
            if (seed[ess]>=ess_attr_high and candidate[ess]<ess_cand_attr_high) or (seed[ess]<=ess_attr_low and candidate[ess]>ess_cand_attr_low):
                return '%s - %f/%f' % (ess, seed[ess], candidate[ess])

    return None

