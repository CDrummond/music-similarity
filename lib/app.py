#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import argparse, json, logging, math, os, random, sqlite3, urllib
from datetime import datetime
from flask import Flask, abort, request
from . import cue, filters, tracks_db, musly

_LOGGER = logging.getLogger(__name__)


DEFAULT_TRACKS_TO_RETURN              = 5    # Number of tracks to return, if none specified
MIN_TRACKS_TO_RETURN                  = 5    # Min value for 'count' parameter
MAX_TRACKS_TO_RETURN                  = 50   # Max value for 'count' parameter
DEFAULT_NUM_PREV_TRACKS_FILTER_ARTIST = 15   # Try to ensure artist is not in previous N tracks
DEFAULT_NUM_PREV_TRACKS_FILTER_ALBUM  = 25   # Try to ensure album is not in previous N tracks
NUM_SIMILAR_TRACKS_FACTOR             = 25   # Request count*NUM_SIMILAR_TRACKS_FACTOR from musly
SHUFFLE_FACTOR                        = 1.75 # How many (shuffle_factor*count) tracks to shuffle?


class SimilarityApp(Flask):
    def init(self, args, app_config, jukebox_path):
        _LOGGER.debug('Start server')
        self.app_config = app_config
        self.mus = musly.Musly(app_config['musly']['lib'])
        
        flask_logging = logging.getLogger('werkzeug')
        flask_logging.setLevel(args.log_level)
        flask_logging.disabled = 'DEBUG'!=args.log_level
        tdb = tracks_db.TracksDb(app_config)
        (paths, tracks) = self.mus.get_alltracks_db(tdb.get_cursor())
        random.seed()
        if app_config['essentia']['weight']>0.0:
            from . import essentia_sim
            essentia_sim.init(tdb)
        ids = None

        # If we can, load musly from jukebox...
        if os.path.exists(jukebox_path):
            ids = self.mus.get_jukebox_from_file(jukebox_path)

        if ids==None or len(ids)!=len(tracks):
            _LOGGER.debug('Adding tracks from DB to musly')
            ids = self.mus.add_tracks(tracks, app_config['musly']['styletracks'], app_config['musly']['styletracksmethod'], tdb)
            self.mus.write_jukebox(jukebox_path)

        tdb.close()
        self.mta=musly.MuslyTracksAdded(paths, tracks, ids)
        if app_config['essentia']['enabled']:
            _LOGGER.debug('Will use Essentia attributes to filter tracks')

    def get_config(self):
        return self.app_config

    def get_musly(self):
        return self.mus

    def get_mta(self):
        return self.mta
    
similarity_app = SimilarityApp(__name__)


class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


def get_value(params, key, defVal, isPost):
    if isPost:
        return params[key] if key in params else defVal
    return params[key][0] if key in params else defVal


def decode(url, root):
    u = urllib.parse.unquote(url)
    if u.startswith('file://'):
        u=u[7:]
    elif u.startswith('tmp://'):
        u=u[6:]
    if u.startswith(root):
        u=u[len(root):]
    return cue.convert_from_cue_path(u)


def genre_adjust(seed, entry, acceptable_genres, all_genres, match_all_genres):
    if match_all_genres:
        return 0.0
    if 'genres' not in seed:
        return 0.15
    if 'genres' not in entry:
        return 0.15
    if len(seed['genres'].intersection(entry['genres']))>0:
        # Exact genre match
        return 0.0
    if (acceptable_genres is not None and len(entry['genres'].intersection(acceptable_genres)))==0 or \
       (acceptable_genres is None and all_genres is not None and len(entry['genres'].intersection(all_genres)))==0:
        return 0.15
    # Genre in group
    return 0.075


def get_similarity(track_id, mus, mta, tdb, ess_weight):
    if ess_weight>0.0:
        _LOGGER.debug('Call musly')
    mt = mus.get_similars( mta.mtracks, mta.mtrackids, track_id )
    if ess_weight>0.0:
        from . import essentia_sim
        _LOGGER.debug('Call essentia')
        et = essentia_sim.get_similars( track_id )
        num_et = len(et)
        tracks = []
        for track in mt:
            i = track['id']
            esval = et[i] if i<num_et else track['sim']
            tracks.append({'id':i, 'sim':(track['sim']*(1.0-ess_weight)) + (esval*ess_weight)})
    else:
        tracks = mt
    return sorted(tracks, key=lambda k: k['sim'])


def append_list(orig, to_add, min_count):
    paths=set()
    for item in orig:
        paths.add(item['path'])
    sorted_add = sorted(to_add, key=lambda k: k['similarity'])
    for item in sorted_add:
        if not item['path'] in paths:
            paths.add(item['path'])
            orig.append(item)
            if len(orig)>=min_count:
                break
    return orig


def set_filtered(simtrack, mta, filtered_tracks, key, ids):
    if simtrack['id'] in filtered_tracks['ids'][ids] or (ids=='attribs' and simtrack['id'] in filtered_tracks['ids']['other']):
        return

    if simtrack['id'] in filtered_tracks['ids']['attribs']:
        # Remove from filtered_tracks::attribs
        for i in len(filtered_tracks['attribs']):
            if filtered_tracks['attribs'][i]['id']==simtrack['id']:
                filtered_tracks['attribs'].pop(i)
                filtered_tracks['ids']['attribs'].remove(simtrack['id'])
                break

    filtered_tracks[key].append({'path':mta.paths[simtrack['id']], 'similarity':simtrack['sim']})
    filtered_tracks['ids'][ids].add(simtrack['id'])


@similarity_app.route('/api/dump', methods=['GET', 'POST'])
def dump_api():
    isPost = False
    if request.method=='GET':
        params = request.args.to_dict(flat=False)
    else:
        isPost = True
        params = request.get_json()
        _LOGGER.debug('Request: %s' % json.dumps(params))

    if not params:
        abort(400)

    if not 'track' in params:
        abort(400)

    if len(params['track'])!=1:
        abort(400)

    mta = similarity_app.get_mta()
    mus = similarity_app.get_musly()
    cfg = similarity_app.get_config()
    tdb = tracks_db.TracksDb(cfg)

    # Strip LMS root path from track path
    root = cfg['paths']['lms']

    ess_enabled = cfg['essentia']['enabled']
    ess_weight = cfg['essentia']['weight'] if ess_enabled else 0.0

    track = decode(params['track'][0], root)
    _LOGGER.debug('S TRACK %s -> %s' % (params['track'][0], track))

    # Check that musly knows about this track
    track_id = -1
    try:
        track_id = mta.paths.index( track )
        if track_id<0:
            abort(404)
        fmt = get_value(params, 'format', '', isPost)
        txt = fmt=='text'
        txt_url = fmt=='text-url'
        match_artist = int(get_value(params, 'filterartist', '0', isPost))==1
        meta = tdb.get_metadata(track_id+1) # IDs (rowid) in SQLite are 1.. musly is 0..

        all_genres = cfg['all_genres'] if 'all_genres' in cfg else None
        acceptable_genres=set()
        if 'genres' in meta:
            acceptable_genres.update(meta['genres'])
            if 'genres' in cfg:
                for genre in meta['genres']:
                    for group in cfg['genres']:
                        if genre in group:
                            acceptable_genres.update(group)

        simtracks = get_similarity(track_id, mus, mta, tdb, ess_weight)

        resp=[]
        prev_id=-1
        count = int(get_value(params, 'count', 1000, isPost))

        tracks=[]
        for simtrack in simtracks:
            if simtrack['id']==prev_id:
                break
            prev_id=simtrack['id']
            if math.isnan(simtrack['sim']):
                continue

            track = tdb.get_metadata(simtrack['id']+1)
            if match_artist and track['artist'] != meta['artist']:
                continue
            if not match_artist and track['ignore']:
                continue
            if ess_enabled and not filters.check_attribs(meta, track, cfg['essentia']['bpm']):
                #_LOGGER.debug('DISCARD: %s' % str(track))
                continue
            match_all_genres = ('ignoregenre' in cfg) and (('*'==cfg['ignoregenre'][0]) or (meta is not None and meta['artist'] in cfg['ignoregenre']))
            sim = simtrack['sim'] + genre_adjust(meta, track, acceptable_genres, all_genres, match_all_genres)
            tracks.append({'path':mta.paths[simtrack['id']], 'sim':sim})
            if len(tracks)>=count*10:
                break

        tracks = sorted(tracks, key=lambda k: k['sim'])
        for track in tracks:
            _LOGGER.debug("%s %s" % (track['path'], track['sim']))
            if txt:
                resp.append("%s\t%f" % (track['path'], track['sim']))
            elif txt_url:
                resp.append(cue.convert_to_cue_url('%s%s' % (root, track['path'])))
            else:
                resp.append({'file':track['path'], 'sim':track['sim']})
            if len(resp)>=count:
                break

        if txt or txt_url:
            return '\n'.join(resp)
        else:
            return json.dumps(resp)
    except Exception as e:
        _LOGGER.error("EX:%s" % str(e))
        abort(404)


@similarity_app.route('/api/similar', methods=['GET', 'POST'])
def similar_api():
    isPost = False
    if request.method=='GET':
        params = request.args.to_dict(flat=False)
    else:
        isPost = True
        params = request.get_json()
        _LOGGER.debug('Request: %s' % json.dumps(params))

    if not params:
        abort(400)

    if not 'track' in params:
        abort(400)

    count = int(get_value(params, 'count', DEFAULT_TRACKS_TO_RETURN, isPost))
    if count < MIN_TRACKS_TO_RETURN:
        count = MIN_TRACKS_TO_RETURN
    elif count > MAX_TRACKS_TO_RETURN:
        count = MAX_TRACKS_TO_RETURN

    match_genre = int(get_value(params, 'filtergenre', '0', isPost))==1
    shuffle = int(get_value(params, 'shuffle', '1', isPost))==1
    max_similarity = int(get_value(params, 'maxsim', 75, isPost))/100.0
    min_duration = int(get_value(params, 'min', 0, isPost))
    max_duration = int(get_value(params, 'max', 0, isPost))
    no_repeat_artist = int(get_value(params, 'norepart', 0, isPost))
    no_repeat_album = int(get_value(params, 'norepalb', 0, isPost))
    exclude_christmas = int(get_value(params, 'filterxmas', '0', isPost))==1 and datetime.now().month!=12

    if no_repeat_artist<0 or no_repeat_artist>200:
        no_repeat_artist = DEFAULT_NUM_PREV_TRACKS_FILTER_ARTIST
    if no_repeat_album<0 or no_repeat_album>200:
        no_repeat_album = DEFAULT_NUM_PREV_TRACKS_FILTER_ALBUM

    no_repeat_artist_or_album = no_repeat_album if no_repeat_album>no_repeat_artist else no_repeat_artist

    mta = similarity_app.get_mta()
    mus = similarity_app.get_musly()
    cfg = similarity_app.get_config()
    tdb = tracks_db.TracksDb(cfg)

    # Strip LMS root path from track path
    root = cfg['paths']['lms']

    ess_enabled = cfg['essentia']['enabled']
    ess_weight = cfg['essentia']['weight'] if ess_enabled else 0.0

    # Similar tracks
    similar_tracks=[]
    similar_track_positions={}

    # Details of filtered tracks. We _might_ need to use some of these fitered tracks if there are
    # insufficient similar_tracks chosen.
    filtered_tracks = {'current':[], 'previous':[], 'attribs':[], 'ids':{'other':set(), 'attribs':set()}}

    # IDs of previous or discarded tracks
    skip_track_ids = set()

    # Keep track of titles so that we can filter against
    current_titles = set()

    track_id_seed_metadata={} # Map from seed track's ID to its metadata
    acceptable_genres=set()
    seed_genres=set()
    all_genres = cfg['all_genres'] if 'all_genres' in cfg else None

    # Artist/album of chosen tracks
    current_metadata_keys={}

    track_metadata={'current':[], 'seeds':[], 'previous':[]}

    if min_duration>0 or max_duration>0:
        _LOGGER.debug('Duration:%d .. %d' % (min_duration, max_duration))

    # Musly IDs of seed tracks
    track_ids = []
    for trk in params['track']:
        track = decode(trk, root)
        _LOGGER.debug('S TRACK %s -> %s' % (trk, track))

        # Check that musly knows about this track
        track_id = -1
        try:
            track_id = mta.paths.index( track )
            _LOGGER.debug('Get %d similar track(s) to %s, index: %d' % (count, track, track_id))
        except:
            pass
        if track_id is not None and track_id>=0 and track_id not in track_ids:
            track_ids.append(track_id)
            skip_track_ids.add(track_id)
            meta = tdb.get_metadata(track_id+1) # IDs (rowid) in SQLite are 1.. musly is 0..
            _LOGGER.debug('Seed %d metadata:%s' % (track_id, json.dumps(meta, cls=SetEncoder)))
            if meta is not None:
                track_metadata['seeds'].append(meta)
                track_id_seed_metadata[track_id]=meta
                # Get genres for this seed track - this takes its genres and gets any matching genres from config
                if 'genres' in meta:
                    acceptable_genres.update(meta['genres'])
                    if 'genres' in cfg:
                        for genre in meta['genres']:
                            for group in cfg['genres']:
                                if genre in group:
                                    acceptable_genres.update(group)
                if 'title' in meta:
                    current_titles.add(meta['title'])
        else:
            _LOGGER.debug('Could not locate %s in DB' % track)

    seed_genres.update(acceptable_genres)

    if 'previous' in params:
        for trk in params['previous']:
            track = decode(trk, root)
            _LOGGER.debug('I TRACK %s -> %s' % (trk, track))

            # Check that musly knows about this track
            track_id = -1
            try:
                track_id = mta.paths.index(track)
            except:
                pass
            if track_id is not None and track_id>=0:
                skip_track_ids.add(track_id)
                use_to_filter_prev = len(track_metadata['previous'])<no_repeat_artist_or_album
                if use_to_filter_prev or match_genre:
                    meta = tdb.get_metadata(track_id+1) # IDs (rowid) in SQLite are 1.. musly is 0..
                    if meta:
                        if use_to_filter_prev:
                            track_metadata['previous'].append(meta)
                            if 'title' in meta:
                                current_titles.add(meta['title'])
                        if match_genre:
                            # Get genres for this track - this takes its genres and gets any matching genres from config
                            if 'genres' in meta:
                                acceptable_genres.update(meta['genres'])
                                if 'genres' in cfg:
                                    for genre in meta['genres']:
                                        for group in cfg['genres']:
                                            if genre in group:
                                                acceptable_genres.update(group)
            else:
                _LOGGER.debug('Could not locate %s in DB' % track)
    else:
        _LOGGER.debug('No previous track specified, using seeds as previous tracks')
        track_metadata['previous']=track_metadata['seeds']

    _LOGGER.debug('Seed genres: %s' % seed_genres)
    if match_genre:
        _LOGGER.debug('Acceptable genres: %s' % acceptable_genres)

    similarity_count = int(count * SHUFFLE_FACTOR) if shuffle and (count<20 or len(track_ids)<10) else count

    matched_artists={}
    for track_id in track_ids:
        match_all_genres = ('ignoregenre' in cfg) and (('*'==cfg['ignoregenre'][0]) or ((track_id in track_id_seed_metadata) and (track_id_seed_metadata[track_id]['artist'] in cfg['ignoregenre'])))

        # Query musly for similar tracks
        _LOGGER.debug('Query musly for %d similar tracks to index: %d' % (similarity_count, track_id))
        simtracks = get_similarity(track_id, mus, mta, tdb, ess_weight)
        accepted_tracks = 0
        for simtrack in simtracks:
            if math.isnan(simtrack['sim']):
                continue
            if simtrack['sim']>max_similarity:
                break

            if (simtrack['sim']>0.0) and (simtrack['sim']<=max_similarity) and (not simtrack['id'] in skip_track_ids):
                prev_idx = similar_track_positions[simtrack['id']] if simtrack['id'] in similar_track_positions else -1
                meta = similar_tracks[prev_idx] if prev_idx>=0 else tdb.get_metadata(simtrack['id']+1) # IDs (rowid) in SQLite are 1.. musly is 0..
                if prev_idx>=0:
                    # Seen from previous seed, so set similarity to lowest value
                    sim = simtrack['sim'] + genre_adjust(track_metadata['seeds'], meta, seed_genres, all_genres, match_all_genres)
                    if similar_tracks[prev_idx]['similarity']>sim:
                        _LOGGER.debug('SEEN %d before, prev:%f, current:%f' % (simtrack['id'], similar_tracks[prev_idx]['similarity'], sim))
                        similar_tracks[prev_idx]['similarity']=sim
                elif not meta:
                    _LOGGER.debug('DISCARD(not found) ID:%d Path:%s Similarity:%f' % (simtrack['id'], mta.paths[simtrack['id']], simtrack['sim']))
                    skip_track_ids.add(simtrack['id'])
                elif meta['ignore']:
                    _LOGGER.debug('DISCARD(ignore) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                    skip_track_ids.add(simtrack['id'])
                elif (min_duration>0 or max_duration>0) and not filters.check_duration(min_duration, max_duration, meta):
                    _LOGGER.debug('DISCARD(duration) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                    skip_track_ids.add(simtrack['id'])
                elif match_genre and not match_all_genres and not filters.genre_matches(cfg, acceptable_genres, meta):
                    _LOGGER.debug('DISCARD(genre) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                    skip_track_ids.add(simtrack['id'])
                elif exclude_christmas and filters.is_christmas(meta):
                    _LOGGER.debug('DISCARD(xmas) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                    skip_track_ids.add(simtrack['id'])
                else:
                    if ess_enabled and not filters.check_attribs(track_metadata['seeds'], meta, cfg['essentia']['bpm']):
                        _LOGGER.debug('FILTERED(attribs) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                        set_filtered(simtrack, mta, filtered_tracks, 'attribs', 'attribs')
                        continue

                    if no_repeat_artist>0:
                        filtered = False
                        for key in ['current', 'previous']:
                            no_rep = no_repeat_artist if 'previous'==key else 0
                            _LOGGER.debug('FILTERED CHECK (%s(artist) %d) ID:%d Path:%s Similarity:%f Meta:%s' % (key, len(track_metadata[key]), simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                            if filters.same_artist_or_album(track_metadata[key], meta, False, no_rep):
                                _LOGGER.debug('FILTERED(%s(artist)) ID:%d Path:%s Similarity:%f Meta:%s' % (key, simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                                filtered=True
                                set_filtered(simtrack, mta, filtered_tracks, key, 'other')

                                if 'current'==key and meta['artist'] in matched_artists and len(matched_artists[meta['artist']]['tracks'])<5 and simtrack['sim'] - matched_artists[meta['artist']]['similarity'] <= 0.1:
                                    matched_artists[meta['artist']]['tracks'].append({'path':mta.paths[simtrack['id']], 'similarity':simtrack['sim']})
                                break
                        if filtered:
                            continue

                    if no_repeat_album>0:
                        filtered = False
                        for key in ['current', 'previous']:
                            no_rep = no_repeat_album if 'previous'==key else 0
                            if filters.same_artist_or_album(track_metadata[key], meta, True, no_rep):
                                _LOGGER.debug('FILTERED(%s(album)) ID:%d Path:%s Similarity:%f Meta:%s' % (key, simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                                filtered=True
                                set_filtered(simtrack, mta, filtered_tracks, key, 'other')
                                break
                        if filtered:
                            continue

                    if filters.match_title(current_titles, meta):
                        _LOGGER.debug('FILTERED(title) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                        set_filtered(simtrack, mta, filtered_tracks, 'current', 'other')
                        continue

                    key = '%s::%s::%s' % (meta['artist'], meta['album'], meta['albumartist'] if 'albumartist' in meta and meta['albumartist'] is not None else '')
                    if not key in current_metadata_keys:
                        current_metadata_keys[key]=1
                        track_metadata['current'].append(meta)
                    sim = simtrack['sim'] + genre_adjust(track_metadata['seeds'], meta, seed_genres, all_genres, match_all_genres)

                    _LOGGER.debug('USABLE ID:%d Path:%s Similarity:%f AdjSim:%s Meta:%s' % (simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], sim, json.dumps(meta, cls=SetEncoder)))
                    similar_tracks.append({'path':mta.paths[simtrack['id']], 'similarity':sim})
                    # Keep list of all tracks of an artist, so that we can randomly select one => we don't always use the same one
                    matched_artists[meta['artist']]={'similarity':simtrack['sim'], 'tracks':[{'path':mta.paths[simtrack['id']], 'similarity':sim}], 'pos':len(similar_tracks)-1}
                    if 'title' in meta:
                        current_titles.add(meta['title'])

                    accepted_tracks += 1
                    # Save mapping of this ID to its position in similar_tracks so that we can determine if we have
                    # seen this track before.
                    similar_track_positions[simtrack['id']]=len(similar_tracks)-1
                    if accepted_tracks>=similarity_count:
                        break

    # For each matched_artists randomly select a track...
    for matched in matched_artists:
        if len(matched_artists[matched]['tracks'])>1:
            _LOGGER.debug('Choosing random track for %s (%d tracks)' % (matched, len(matched_artists[matched]['tracks'])))
            sim = similar_tracks[matched_artists[matched]['pos']]['similarity']
            similar_tracks[matched_artists[matched]['pos']] = random.choice(matched_artists[matched]['tracks'])
            similar_tracks[matched_artists[matched]['pos']]['similarity'] = sim

    # Too few tracks? Add some from the filtered lists
    _LOGGER.debug('similar_tracks: %d, filtered_tracks::previous: %d, filtered_tracks::current: %d, filtered_tracks::attribs: %d' % (len(similar_tracks), len(filtered_tracks['previous']), len(filtered_tracks['current']), len(filtered_tracks['attribs'])))
    min_count = 2
    for key in ['previous', 'current', 'attribs']:
        if len(similar_tracks)>=min_count:
            break
        if len(filtered_tracks[key])>0:
            _LOGGER.debug('Add some tracks from filtered_tracks::%s, %d/%d' % (key, len(similar_tracks), len(filtered_tracks[key])))
            similar_tracks = append_list(similar_tracks, filtered_tracks[key], min_count)

    # Sort by similarity
    similar_tracks = sorted(similar_tracks, key=lambda k: k['similarity'])
    
    # Take top 'similarity_count' tracks
    similar_tracks = similar_tracks[:similarity_count]

    if shuffle:
        random.shuffle(similar_tracks)
        similar_tracks = similar_tracks[:count]

    track_list = []
    for track in similar_tracks:
        path = '%s%s' % (root, track['path'])
        track_list.append(cue.convert_to_cue_url(path))
        _LOGGER.debug('Path:%s %f' % (path, track['similarity']))

    tdb.close()
    if get_value(params, 'format', '', isPost)=='text':
        return '\n'.join(track_list)
    else:
        return json.dumps(track_list)


def start_app(args, config, jukebox_path):
    similarity_app.init(args, config, jukebox_path)
    _LOGGER.debug('Ready to process requests')
    similarity_app.run(host=config['host'], port=config['port'])
