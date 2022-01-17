#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021-2022 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import argparse, json, logging, math, os, random, re, sqlite3, urllib
from datetime import datetime
from flask import Flask, abort, request
from . import cue, essentia_sim, filters, tracks_db, musly

_LOGGER = logging.getLogger(__name__)


DEFAULT_TRACKS_TO_RETURN              = 5    # Number of tracks to return, if none specified
MIN_TRACKS_TO_RETURN                  = 1    # Min value for 'count' parameter
MAX_TRACKS_TO_RETURN                  = 50   # Max value for 'count' parameter
DEFAULT_NUM_PREV_TRACKS_FILTER_ARTIST = 15   # Try to ensure artist is not in previous N tracks
DEFAULT_NUM_PREV_TRACKS_FILTER_ALBUM  = 25   # Try to ensure album is not in previous N tracks
SHUFFLE_FACTOR                        = 2    # How many (shuffle_factor*count) tracks to shuffle?
MIN_MUSLY_NUM_SIM                     = 5000 # Min number of tracs to query musly for
DEFAULT_NO_GENRE_MATCH_ADJUSTMENT     = 15
DEFAULT_GENRE_GROUP_MATCH_ADJUSTMENT  = 7
WEIGHT_ALL_ESSENTIA                   = 0.99
WEIGHT_ALL_MUSLY                      = 0.01

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
        ids = None

        if paths is None or tracks is None:
            _LOGGER.error('DB not initialised, have you analysed any tracks?')
            tdb.close()
            exit(-1)

        # If we can, load musly from jukebox...
        if os.path.exists(jukebox_path):
            ids = self.mus.get_jukebox_from_file(jukebox_path)

        if ids==None or len(ids)!=len(tracks):
            _LOGGER.debug('Adding tracks from DB to musly')
            ids = self.mus.add_tracks(tracks, app_config['musly']['styletracks'], app_config['musly']['styletracksmethod'], tdb)
            self.mus.write_jukebox(jukebox_path)

        self.mta=musly.MuslyTracksAdded(paths, tracks, ids)

        if app_config['essentia']['enabled'] and len(paths)>0:
            app_config['essentia']['enabled'] = tdb.files_analysed_with_essentia()
            hl_prev = app_config['essentia']['highlevel']
            app_config['essentia']['highlevel'] = app_config['essentia']['enabled'] and tdb.files_analysed_with_essentia_highlevel()

            if not app_config['essentia']['enabled'] or hl_prev!=app_config['essentia']['highlevel']:
                tdb.close()
                tdb = tracks_db.TracksDb(app_config)

        if app_config['essentia']['enabled']:
            if app_config['essentia']['highlevel'] and app_config['essentia']['weight']>0.0:
                essentia_sim.init(tdb)
                _LOGGER.debug('May use Essentia attributes to filter tracks (highlevel) and for %d%% of similarity score' % int(app_config['essentia']['weight']*100))
            else:
                _LOGGER.debug('May use Essentia attributes to filter tracks (%s)' % ('highlevel' if app_config['essentia']['highlevel'] else 'lowlevel'))
        tdb.close()

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


def encode(root, path, add_file_protocol):
    full_path = '%s%s' % (root, path)
    if path.find(cue.CUE_TRACK)>0:
        return cue.convert_to_cue_url(full_path)
    if add_file_protocol:
        # Check if windows path, if so don't encode first ':'
        if re.match(r'^/[A-Za-z]:', full_path):
            return 'file://%s%s' % (full_path[:3], urllib.parse.quote(full_path[3:]))
        else:
            return 'file://%s' % urllib.parse.quote(full_path)
    return full_path


def genre_adjust(seed, entry, acceptable_genres, all_genres, no_genre_match_adj, genre_group_adj):
    if 'genres' not in seed:
        return no_genre_match_adj
    if 'genres' not in entry:
        return no_genre_match_adj
    if len(seed['genres'].intersection(entry['genres']))>0:
        # Exact genre match
        return 0.0
    if (acceptable_genres is not None and len(entry['genres'].intersection(acceptable_genres))==0) or \
       (acceptable_genres is None and all_genres is not None and len(entry['genres'].intersection(all_genres))==0):
        return no_genre_match_adj
    # Genre in group
    return genre_group_adj


def get_similars(track_id, mus, num_sim, mta, tdb, ess_cfg):
    tracks = []

    if ess_cfg['enabled'] and ess_cfg['highlevel'] and ess_cfg['weight']>=WEIGHT_ALL_MUSLY:
        # Init essentia KDTree. If essentia weight was configured in JSON config file
        # then this will already have occured, so following call will do nothing. However,
        # if its not set in the config but is set in URL params then we do need to
        # initialise now.
        essentia_sim.init(tdb)

    if ess_cfg['enabled'] and ess_cfg['highlevel'] and ess_cfg['weight']>=WEIGHT_ALL_ESSENTIA:
        _LOGGER.debug('Get similar tracks to %d from Essentia' % track_id)
        et = essentia_sim.get_similars(tdb, track_id)
        idx = 0
        for track in et:
            tracks.append({'id':idx, 'sim':track})
            idx+=1
        return sorted(tracks, key=lambda k: k['sim'])

    if not ess_cfg['enabled'] or not ess_cfg['highlevel'] or ess_cfg['weight']<WEIGHT_ALL_MUSLY:
        _LOGGER.debug('Get %d similar tracks to %d from Musly' % (num_sim, track_id))
        return mus.get_similars(mta.mtracks, mta.mtrackids, track_id, num_sim)

    _LOGGER.debug('Get similar tracks to %d from Musly' % track_id)
    mt = mus.get_all_similars(mta.mtracks, mta.mtrackids, track_id)

    _LOGGER.debug('Get similar tracks to %d from Essentia' % track_id)
    et = essentia_sim.get_similars(tdb, track_id)
    num_et = len(et)
    tracks = []
    _LOGGER.debug('Merge similarity scores')
    for track in mt:
        if math.isnan(track['sim']):
            continue
        i = track['id']
        esval = et[i] if i<num_et else track['sim']
        tracks.append({'id':i, 'sim':(track['sim']*(1.0-ess_cfg['weight'])) + (esval*ess_cfg['weight'])})

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


def set_filtered(simtrack, mta, filtered_tracks, key):
    if simtrack['id'] in filtered_tracks['ids'][key] or (key=='attribs' and simtrack['id'] in filtered_tracks['ids']['meta']):
        return

    if simtrack['id'] in filtered_tracks['ids']['attribs']:
        # Remove from filtered_tracks::attribs
        for i in range(len(filtered_tracks['attribs'])):
            if filtered_tracks['attribs'][i]['id']==simtrack['id']:
                filtered_tracks['attribs'].pop(i)
                filtered_tracks['ids']['attribs'].remove(simtrack['id'])
                break

    filtered_tracks[key].append({'path':mta.paths[simtrack['id']], 'id':simtrack['id'], 'similarity':simtrack['sim']})
    filtered_tracks['ids'][key].add(simtrack['id'])


def get_album_key(track):
    aa = track['albumartist'] if 'albumartist' in track and track['albumartist'] is not None and len(track['albumartist'])>0 else track['artist']
    if aa in filters.VARIOUS_ARTISTS:
        return None
    return '%s::%s' % (aa, track['album'])


def get_genre_cfg(config, params):
    ''' Get genre settings from URL or config '''
    genre_cfg={}

    if 'genregroups' in params and params['genregroups'] is not None:
        genre_cfg['all_genres']=set()
        genre_cfg['genres']=[]
        for i in range(len(params['genregroups'])):
            genre_cfg['genres'].append(set(params['genregroups'][i]))
            genre_cfg['all_genres'].update(params['genregroups'][i])
    else:
        if 'genres' in config:
            genre_cfg['genres']=config['genres']
        if 'all_genres' in config:
            genre_cfg['all_genres']=config['all_genres']

    _LOGGER.debug('Genre cfg: %s' % json.dumps(genre_cfg, cls=SetEncoder))
    return genre_cfg


def get_essentia_cfg(config, params):
    ''' Get essentia(attrib) settings from URL or config '''
    ess_cfg={'enabled': config['essentia']['enabled'], 'highlevel': config['essentia']['highlevel']}
    if config['essentia']['enabled']:
        if 'maxbpmdiff' in params and params['maxbpmdiff'] is not None:
            ess_cfg['bpm'] = int(params['maxbpmdiff'])
        else:
            ess_cfg['bpm'] = config['essentia']['bpm']

        if 'maxloudnessdiff' in params and params['maxloudnessdiff'] is not None:
            ess_cfg['loudness'] = int(params['maxloudnessdiff'])/10.0
        else:
            ess_cfg['loudness'] = config['essentia']['loudness']/10.0

        if 'filterkey' in params and params['filterkey'] is not None:
            ess_cfg['filterkey'] = int(params['filterkey'])==1
        else:
            ess_cfg['filterkey'] = config['essentia']['filterkey']

        if 'filterattrib' in params and params['filterattrib'] is not None:
            ess_cfg['filterattrib'] = int(params['filterattrib'])==1
        else:
            ess_cfg['filterattrib'] = config['essentia']['filterattrib']

        if not config['essentia']['highlevel']:
            ess_cfg['weight'] = 0.0
        elif 'attribweight' in params and params['attribweight'] is not None:
            ess_cfg['weight'] = int(params['attribweight'])/100.0
        else:
            ess_cfg['weight'] = config['essentia']['weight']

    _LOGGER.debug('Essentia(attrib) cfg: %s' % json.dumps(ess_cfg, cls=SetEncoder))
    return ess_cfg


def get_music_path(params, cfg):
    path = None
    if 'mpath' in params:
        path = params['mpath']
    elif 'lms' in cfg['paths']:
        path = cfg['paths']['lms']
    else:
        return ''

    if re.match(r'^[A-Za-z]:\\', path):
        # LMS will supply (e.g.) c:\Users\user\Music and we want /C:/Users/user/Music/
        # This is because tracks will be file:///C:/Users/user/Music
        path = '/'+path.replace('\\', '/')
    if not path.endswith('/'):
        path += '/'
    return path


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
    genre_cfg = get_genre_cfg(cfg, params)
    ess_cfg = get_essentia_cfg(cfg, params)

    # Strip LMS root path from track path
    root = get_music_path(params, cfg)
    _LOGGER.debug('Music root: %s' % root)

    add_file_protocol = params['track'][0].startswith('file://')

    track = decode(params['track'][0], root)
    no_genre_match_adj = int(get_value(params, 'nogenrematchadj', DEFAULT_NO_GENRE_MATCH_ADJUSTMENT, isPost))/100.0
    genre_group_adj = int(get_value(params, 'genregroupadj', DEFAULT_GENRE_GROUP_MATCH_ADJUSTMENT, isPost))/100.0
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

        all_genres = genre_cfg['all_genres'] if 'all_genres' in genre_cfg else None
        acceptable_genres=set()
        if 'genres' in meta:
            acceptable_genres.update(meta['genres'])
            if 'genres' in genre_cfg:
                for genre in meta['genres']:
                    for group in genre_cfg['genres']:
                        if genre in group:
                            acceptable_genres.update(group)

        count = int(get_value(params, 'count', 1000, isPost))
        num_sim = count * 50
        if num_sim<MIN_MUSLY_NUM_SIM:
            num_sim = MIN_MUSLY_NUM_SIM
        simtracks = get_similars(track_id, mus, num_sim, mta, tdb, ess_cfg)

        resp=[]
        prev_id=-1

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
            if simtrack['id']!=track_id and 'title' in track and 'title' in meta and track['title'] == meta['title']:
                continue
            if ess_cfg['enabled']:
                filtered_due_to = filters.check_attribs(meta, track, ess_cfg)
                if filtered_due_to is not None:
                    _LOGGER.debug('DISCARD(%s): %s' % (filtered_due_to, str(track)))
                    continue

            sim = simtrack['sim'] + genre_adjust(meta, track, acceptable_genres, all_genres, no_genre_match_adj, genre_group_adj)
            tracks.append({'path':mta.paths[simtrack['id']], 'sim':sim})
            if len(tracks)==MIN_MUSLY_NUM_SIM:
                break

        tracks = sorted(tracks, key=lambda k: k['sim'])
        for track in tracks:
            _LOGGER.debug("%s %s" % (track['path'], track['sim']))
            if txt:
                resp.append("%s\t%f" % (track['path'], track['sim']))
            elif txt_url:
                resp.append(encode(root, track['path'], add_file_protocol))
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
    no_genre_match_adj = int(get_value(params, 'nogenrematchadj', DEFAULT_NO_GENRE_MATCH_ADJUSTMENT, isPost))/100.0
    genre_group_adj = int(get_value(params, 'genregroupadj', DEFAULT_GENRE_GROUP_MATCH_ADJUSTMENT, isPost))/100.0

    if no_repeat_artist<0 or no_repeat_artist>200:
        no_repeat_artist = DEFAULT_NUM_PREV_TRACKS_FILTER_ARTIST
    if no_repeat_album<0 or no_repeat_album>200:
        no_repeat_album = DEFAULT_NUM_PREV_TRACKS_FILTER_ALBUM

    mta = similarity_app.get_mta()
    mus = similarity_app.get_musly()
    cfg = similarity_app.get_config()
    tdb = tracks_db.TracksDb(cfg)
    genre_cfg = get_genre_cfg(cfg, params)
    ess_cfg = get_essentia_cfg(cfg, params)

    # Strip LMS root path from track path
    root = get_music_path(params, cfg)
    _LOGGER.debug('Music root: %s' % root)

    # Similar tracks
    similar_tracks=[]
    similar_track_positions={}

    # Details of filtered tracks. We _might_ need to use some of these fitered tracks if there are
    # insufficient similar_tracks chosen.
    filtered_tracks = {'meta':[], 'attribs':[], 'ids':{'meta':set(), 'attribs':set()}}

    filter_out = {'artists':set(), 'albums':set(), 'titles':set()}

    # IDs of previous or discarded tracks
    skip_track_ids = set()

    track_id_seed_metadata={} # Map from seed track's ID to its metadata
    acceptable_genres=set()
    seed_genres=set()
    all_genres = genre_cfg['all_genres'] if 'all_genres' in genre_cfg else None

    if min_duration>0 or max_duration>0:
        _LOGGER.debug('Duration:%d .. %d' % (min_duration, max_duration))

    have_prev_tracks = 'previous' in params
    # Musly IDs of seed tracks
    track_ids = []
    trk_count = 0
    add_file_protocol = params['track'][0].startswith('file://')

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
                track_id_seed_metadata[track_id]=meta
                # Get genres for this seed track - this takes its genres and gets any matching genres from config
                if 'genres' in meta:
                    seed_genres.update(meta['genres'])
                    # Only add genres from configured groups to acceptable_genres
                    #acceptable_genres.update(meta['genres'])
                    if 'genres' in genre_cfg:
                        for genre in meta['genres']:
                            for group in genre_cfg['genres']:
                                if genre in group:
                                    acceptable_genres.update(group)
                                    seed_genres.update(group)
                if 'title' in meta:
                    filter_out['titles'].add(meta['title'])
                if not have_prev_tracks:
                    if trk_count<no_repeat_artist:
                        filter_out['artists'].add(meta['artist'])
                    if trk_count<no_repeat_album:
                        akey = get_album_key(meta)
                        if akey is not None:
                            filter_out['albums'].add(akey)
            trk_count += 1
        else:
            _LOGGER.debug('Could not locate %s in DB' % track)

    if have_prev_tracks:
        trk_count = 0
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
                meta = tdb.get_metadata(track_id+1) # IDs (rowid) in SQLite are 1.. musly is 0..
                if meta:
                    if 'title' in meta:
                        filter_out['titles'].add(meta['title'])
                    if trk_count<no_repeat_artist:
                        filter_out['artists'].add(meta['artist'])
                    if trk_count<no_repeat_album:
                        akey = get_album_key(meta)
                        if akey is not None:
                            filter_out['albums'].add(akey)
                    if match_genre:
                        # Get genres for this track - this takes its genres and gets any matching genres from config
                        if 'genres' in meta:
                            # Only add genres from configured groups to acceptable_genres
                            #acceptable_genres.update(meta['genres'])
                            if 'genres' in genre_cfg:
                                for genre in meta['genres']:
                                    for group in genre_cfg['genres']:
                                        if genre in group:
                                            acceptable_genres.update(group)
            else:
                _LOGGER.debug('Could not locate %s in DB' % track)
            trk_count += 1

    _LOGGER.debug('Seed genres: %s' % seed_genres)
    if match_genre and len(acceptable_genres)>0:
        _LOGGER.debug('Acceptable genres: %s' % acceptable_genres)

    similarity_count = int(count * SHUFFLE_FACTOR) if shuffle and (count<20 or len(track_ids)<10) else count
    tracks_per_seed = int(similarity_count*2.5) if similarity_count<15 else similarity_count

    num_sim = count * len(track_ids) * 50
    if num_sim<MIN_MUSLY_NUM_SIM:
        num_sim = MIN_MUSLY_NUM_SIM

    matched_artists={}
    for track_id in track_ids:
        # Query musly and/or essentia for similar tracks
        simtracks = get_similars(track_id, mus, num_sim, mta, tdb, ess_cfg)
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
                    sim = simtrack['sim'] + genre_adjust(track_id_seed_metadata[track_id], meta, seed_genres, all_genres, no_genre_match_adj, genre_group_adj)
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
                elif match_genre and not filters.genre_matches(genre_cfg, acceptable_genres, meta):
                    _LOGGER.debug('DISCARD(genre) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                    skip_track_ids.add(simtrack['id'])
                elif exclude_christmas and filters.is_christmas(meta):
                    _LOGGER.debug('DISCARD(xmas) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                    skip_track_ids.add(simtrack['id'])
                else:
                    if ess_cfg['enabled']:
                        filtered_due_to = filtered_due_to = filters.check_attribs(track_id_seed_metadata[track_id], meta, ess_cfg)
                        if filtered_due_to is not None:
                            _LOGGER.debug('FILTERED(attribs(%s)) ID:%d Path:%s Similarity:%f Meta:%s' % (filtered_due_to, simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                            set_filtered(simtrack, mta, filtered_tracks, 'attribs')
                            continue

                    if no_repeat_artist>0:
                        if meta['artist'] in filter_out['artists']:
                            _LOGGER.debug('FILTERED(artist) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                            set_filtered(simtrack, mta, filtered_tracks, 'meta')

                            if meta['artist'] in matched_artists and len(matched_artists[meta['artist']]['tracks'])<5 and simtrack['sim'] - matched_artists[meta['artist']]['similarity'] <= 0.1:
                                # Only add this track as a possibility if album not in previous
                                akey = get_album_key(meta)
                                if akey is None or akey not in filter_out['albums']:
                                    matched_artists[meta['artist']]['tracks'].append({'path':mta.paths[simtrack['id']], 'similarity':simtrack['sim']})
                            continue

                    if no_repeat_album>0:
                        akey = get_album_key(meta)
                        if akey is not None and akey in filter_out['albums']:
                            _LOGGER.debug('FILTERED(album) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                            set_filtered(simtrack, mta, filtered_tracks, 'meta')
                            continue

                    if 'title' in meta and meta['title'] in filter_out['titles']:
                        _LOGGER.debug('FILTERED(title) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                        set_filtered(simtrack, mta, filtered_tracks, 'meta')
                        continue

                    key = '%s::%s::%s' % (meta['artist'], meta['album'], meta['albumartist'] if 'albumartist' in meta and meta['albumartist'] is not None else '')
                    sim = simtrack['sim'] + genre_adjust(track_id_seed_metadata[track_id], meta, seed_genres, all_genres, no_genre_match_adj, genre_group_adj)

                    _LOGGER.debug('USABLE ID:%d Path:%s Similarity:%f AdjSim:%s Meta:%s' % (simtrack['id'], mta.paths[simtrack['id']], simtrack['sim'], sim, json.dumps(meta, cls=SetEncoder)))
                    similar_tracks.append({'path':mta.paths[simtrack['id']], 'similarity':sim})
                    # Keep list of all tracks of an artist, so that we can randomly select one => we don't always use the same one
                    matched_artists[meta['artist']]={'similarity':simtrack['sim'], 'tracks':[{'path':mta.paths[simtrack['id']], 'similarity':sim}], 'pos':len(similar_tracks)-1}
                    if 'title' in meta:
                        filter_out['titles'].add(meta['title'])

                    if no_repeat_album>0:
                        akey = get_album_key(meta)
                        if akey is not None:
                            filter_out['albums'].add(akey)
                    if no_repeat_artist>0:
                        filter_out['artists'].add(meta['artist'])

                    accepted_tracks += 1
                    # Save mapping of this ID to its position in similar_tracks so that we can determine if we have
                    # seen this track before.
                    similar_track_positions[simtrack['id']]=len(similar_tracks)-1
                    if accepted_tracks>=tracks_per_seed:
                        break

    # For each matched_artists randomly select a track...
    for matched in matched_artists:
        if len(matched_artists[matched]['tracks'])>1:
            _LOGGER.debug('Choosing random track for %s (%d tracks)' % (matched, len(matched_artists[matched]['tracks'])))
            sim = similar_tracks[matched_artists[matched]['pos']]['similarity']
            similar_tracks[matched_artists[matched]['pos']] = random.choice(matched_artists[matched]['tracks'])
            similar_tracks[matched_artists[matched]['pos']]['similarity'] = sim

    # Too few tracks? Add some from the filtered lists
    _LOGGER.debug('similar_tracks: %d, filtered_tracks::meta: %d, filtered_tracks::attribs: %d' % (len(similar_tracks), len(filtered_tracks['meta']), len(filtered_tracks['attribs'])))
    min_count = 2
    for key in ['meta', 'attribs']:
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
        path = encode(root, track['path'], add_file_protocol)
        track_list.append(path)
        _LOGGER.debug('Path:%s %f' % (path, track['similarity']))

    tdb.close()
    if get_value(params, 'format', '', isPost)=='text':
        return '\n'.join(track_list)
    else:
        return json.dumps(track_list)


@similarity_app.route('/api/config', methods=['GET', 'POST'])
def config_api():
    return json.dumps(similarity_app.get_config())


def start_app(args, config, jukebox_path):
    similarity_app.init(args, config, jukebox_path)
    _LOGGER.debug('Ready to process requests')
    similarity_app.run(host=config['host'], port=config['port'])
