#
# Analyse files with Musly, Essentia, and Bliss, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021-2022 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import argparse, json, logging, math, numpy, os, random, re, sqlite3, urllib
from datetime import datetime
from flask import Flask, abort, request
from scipy.spatial import cKDTree
from . import bliss_sim, cue, essentia_sim, filters, tracks_db, musly

_LOGGER = logging.getLogger(__name__)


DEFAULT_TRACKS_TO_RETURN              = 5    # Number of tracks to return, if none specified
MIN_TRACKS_TO_RETURN                  = 1    # Min value for 'count' parameter
MAX_TRACKS_TO_RETURN                  = 50   # Max value for 'count' parameter
DEFAULT_ATTTRMIX_COUNT                = 100  # Default number of tracks to return for 'attrmix' API
DEFAULT_NUM_PREV_TRACKS_FILTER_ARTIST = 15   # Try to ensure artist is not in previous N tracks
DEFAULT_NUM_PREV_TRACKS_FILTER_ALBUM  = 25   # Try to ensure album is not in previous N tracks
SHUFFLE_FACTOR                        = 5    # How many (shuffle_factor*count) tracks to shuffle?
MIN_NUM_SIM                           = 5000 # Min number of tracs to query for
DEFAULT_NO_GENRE_MATCH_ADJUSTMENT     = 15
DEFAULT_GENRE_GROUP_MATCH_ADJUSTMENT  = 7


class SimilarityApp(Flask):
    def init(self, args, app_config, jukebox_path):
        _LOGGER.debug('Start server')
        self.app_config = app_config
        self.mus = None
        
        flask_logging = logging.getLogger('werkzeug')
        flask_logging.setLevel(args.log_level)
        flask_logging.disabled = 'DEBUG'!=args.log_level
        tdb = tracks_db.TracksDb(app_config)
        random.seed()

        if app_config['essentia']['enabled']:
            app_config['essentia']['enabled'] = tdb.files_analysed_with_essentia()
            hl_prev = app_config['essentia']['highlevel']
            app_config['essentia']['highlevel'] = app_config['essentia']['enabled'] and tdb.files_analysed_with_essentia_highlevel()

        if app_config['musly']['enabled']:
            app_config['musly']['enabled'] = tdb.files_analysed_with_musly()

        if app_config['bliss']['enabled']:
            app_config['bliss']['enabled'] = tdb.files_analysed_with_bliss()

        if app_config['simalgo']=='musly' and not app_config['musly']['enabled']:
            app_config['simalgo'] = 'bliss' if app_config['bliss']['enabled'] else 'essentia'

        if app_config['simalgo']=='essentia' and (not app_config['essentia']['enabled'] or not app_config['essentia']['highlevel']):
            app_config['simalgo'] = 'bliss' if app_config['bliss']['enabled'] else 'musly'

        # Re-open DB now that essentia/bliss have been checked
        tdb.close()
        tdb = tracks_db.TracksDb(app_config)

        self.mus = None
        self.mta = {'tracks':None, 'ids':None}

        mixed = app_config['simalgo']=='mixed' or app_config['simalgo']=='simplemixed'
        if app_config['simalgo']=='essentia' or (mixed and app_config['mixed']['essentia']>0):
            self.paths = essentia_sim.init(tdb)
            _LOGGER.debug('%d track(s) loaded from Essentia' % len(self.paths) if self.paths is not None else 0)

        if app_config['simalgo']=='bliss' or (mixed and app_config['mixed']['bliss']>0):
            self.paths = bliss_sim.init(tdb)
            _LOGGER.debug('%d track(s) loaded from Bliss' % len(self.paths) if self.paths is not None else 0)

        if app_config['simalgo']=='musly' or (mixed and app_config['mixed']['musly']>0):
            self.mus = musly.Musly(app_config['musly']['lib'])
            (self.paths, self.mta['tracks']) = self.mus.get_alltracks_db(tdb.get_cursor())
            _LOGGER.debug('%d track(s) loaded from Musly' % len(self.paths) if self.paths is not None else 0)

            # If we can, load musly from jukebox...
            if os.path.exists(jukebox_path):
                self.mta['ids'] = self.mus.get_jukebox_from_file(jukebox_path)

            if self.mta['tracks'] is not None and self.paths is not None and (self.mta['ids']==None or len(self.mta['ids'])!=len(self.paths)):
                _LOGGER.debug('Adding tracks from DB to musly')
                self.mta['ids'] = self.mus.add_tracks(self.mta['tracks'], app_config['musly']['styletracks'], app_config['musly']['styletracksmethod'], tdb)
                self.mus.write_jukebox(jukebox_path)

        if self.paths is None or len(self.paths)==0 or (app_config['simalgo']=='musly' and self.mta['ids'] is None):
            _LOGGER.error('DB not initialised, have you analysed all tracks?')
            tdb.close()
            exit(-1)

        _LOGGER.info('Similarity via: {}'.format(app_config['simalgo']))


    def get_config(self):
        return self.app_config


    def get_musly(self):
        return self.mus, self.mta


    def get_paths(self):
        return self.paths


similarity_app = SimilarityApp(__name__)


class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


def get_value(params, key, defVal, isPost):
    val = (params[key] if key in params else defVal) if isPost else (params[key][0] if key in params else defVal)
    return defVal if val is None else val


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


def get_similars(track_id, mus, num_sim, mta, tdb, cfg):
    tracks = []

    if cfg['simalgo']=='mixed' or cfg['simalgo']=='simplemixed':
        etracks = []
        btracks = []
        mtracks = []
        num_tracks = tdb.num_tracks()
        use_ess = cfg['essentia']['enabled'] and cfg['essentia']['highlevel'] and 'essentia' in cfg['mixed'] and cfg['mixed']['essentia']>0
        use_bliss = cfg['bliss']['enabled'] and 'bliss' in cfg['mixed'] and cfg['mixed']['bliss']>0
        use_musly = cfg['musly']['enabled'] and 'musly' in cfg['mixed'] and cfg['mixed']['musly']>0
        epc = cfg['mixed']['essentia']/100.0 if use_ess else 0.0
        bpc = cfg['mixed']['bliss']/100.0 if use_bliss else 0.0
        mpc = cfg['mixed']['musly']/100.0 if use_musly else 0.0
        use_ess = use_ess and epc>0.0
        use_bliss = use_bliss and bpc>0.0
        use_musly = use_musly and mpc>0.0

        # Get similarities from enabled algorithms
        if use_ess:
            _LOGGER.debug('Get distances for all tracks from Essentia')
            etracks = essentia_sim.get_similars(track_id, num_tracks)
            etracks = sorted(etracks, key=lambda k: k['id'])
        if use_bliss:
            _LOGGER.debug('Get distances for all tracks from Bliss')
            btracks = bliss_sim.get_similars(track_id, num_tracks)
            btracks = sorted(btracks, key=lambda k: k['id'])
        if use_musly:
            _LOGGER.debug('Get distances for all tracks from Musly')
            mtracks = mus.get_similars(mta['tracks'], mta['ids'], track_id, num_tracks)
            mtracks = sorted(mtracks, key=lambda k: k['id'])

        if len(etracks)>0 or len(btracks)>0 or len(mtracks)>0:
            _LOGGER.debug('Combining similarities')
            tracks = []

            if cfg['simalgo']=='simplemixed':
                for i in range(num_tracks):
                    sim = 0.0
                    if use_ess:
                        sim += etracks[i]['sim']*epc
                    if use_bliss:
                        sim += btracks[i]['sim']*bpc
                    if use_musly:
                        sim += mtracks[i]['sim']*mpc
                    tracks.append({'sim': sim, 'id':i})
                return sorted(tracks, key=lambda k: k['sim'])[:num_sim]

            # Create a KDTree of these similarities
            sim_list = []
            for i in range(num_tracks):
                sims = []
                if use_ess:
                    sims.append(etracks[i]['sim']*epc)
                if use_bliss:
                    sims.append(btracks[i]['sim']*bpc)
                if use_musly:
                    sims.append(mtracks[i]['sim']*mpc)
                sim_list.append(sims)

            sims_list = numpy.array(sim_list)
            _LOGGER.debug('Create tree')
            tree = cKDTree(sims_list)

            # Find items closest to 0
            zero = []
            if use_ess:
                zero.append(0.0)
            if use_bliss:
                zero.append(0.0)
            if use_musly:
                zero.append(0.0)
            _LOGGER.debug('Query tree')
            distances, indexes = tree.query(numpy.array([zero]), k=num_sim)
            tracks = []
            for i in range(min(len(indexes[0]), num_sim)):
                tracks.append({'id':indexes[0][i], 'sim':distances[0][i]})
            return tracks

    if cfg['simalgo']=='essentia':
        _LOGGER.debug('Get %d similar tracks to %d from Essentia' % (num_sim, track_id))
        return essentia_sim.get_similars(track_id, num_sim)

    if cfg['simalgo']=='bliss':
        _LOGGER.debug('Get %d similar tracks to %d from Bliss' % (num_sim, track_id))
        return bliss_sim.get_similars(track_id, num_sim)

    _LOGGER.debug('Get %d similar tracks to %d from Musly' % (num_sim, track_id))
    return mus.get_similars(mta['tracks'], mta['ids'], track_id, num_sim)


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


def set_filtered(simtrack, paths, filtered_tracks, key):
    if simtrack['id'] in filtered_tracks['ids'][key] or (key=='attribs' and simtrack['id'] in filtered_tracks['ids']['meta']):
        return

    if simtrack['id'] in filtered_tracks['ids']['attribs']:
        # Remove from filtered_tracks::attribs
        for i in range(len(filtered_tracks['attribs'])):
            if filtered_tracks['attribs'][i]['id']==simtrack['id']:
                filtered_tracks['attribs'].pop(i)
                filtered_tracks['ids']['attribs'].remove(simtrack['id'])
                break

    filtered_tracks[key].append({'path':paths[simtrack['id']], 'id':simtrack['id'], 'similarity':simtrack['sim']})
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
    ess_cfg={'enabled': config['essentia']['enabled']}

    if config['essentia']['enabled']:
        ess_cfg={'enabled': config['essentia']['enabled'], 'highlevel': config['essentia']['highlevel'],
                 'filterattrib_lim': config['essentia']['filterattrib_lim'],
                 'filterattrib_cand': config['essentia']['filterattrib_cand'],
                 'filterattrib_count': config['essentia']['filterattrib_count']}

    _LOGGER.debug('Essentia(attrib) cfg: %s' % json.dumps(ess_cfg, cls=SetEncoder))
    return ess_cfg


def get_music_path(params, cfg):
    path = ''
    if 'mpath' in params and params['mpath'] is not None:
        path = params['mpath']
    elif 'lms' in cfg['paths'] and cfg['paths']['lms'] is not None:
        path = cfg['paths']['lms']

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

    mus, mta = similarity_app.get_musly()
    paths = similarity_app.get_paths()
    cfg = similarity_app.get_config()
    tdb = tracks_db.TracksDb(cfg)
    genre_cfg = get_genre_cfg(cfg, params)
    ess_cfg = get_essentia_cfg(cfg, params)

    # Strip LMS root path from track path
    root = get_music_path(params, cfg)
    _LOGGER.debug('Music root: %s' % root)

    add_file_protocol = params['track'][0].startswith('file://')

    track = decode(params['track'][0], root)
    raw = int(get_value(params, 'raw', 0, isPost))==1
    match_artist = int(get_value(params, 'filterartist', '0', isPost))==1
    no_genre_match_adj = int(get_value(params, 'nogenrematchadj', DEFAULT_NO_GENRE_MATCH_ADJUSTMENT, isPost))/100.0
    genre_group_adj = int(get_value(params, 'genregroupadj', DEFAULT_GENRE_GROUP_MATCH_ADJUSTMENT, isPost))/100.0
    count = int(get_value(params, 'count', 1000, isPost))
    fmt = get_value(params, 'format', '', isPost)
    txt = fmt=='text'
    txt_url = fmt=='text-url'
    _LOGGER.debug('S TRACK %s -> %s' % (params['track'][0], track))

    # Check that musly knows about this track
    track_id = -1
    try:
        track_id = paths.index( track )
        if track_id<0:
            abort(404)

        if not raw:
            meta = tdb.get_track(track_id+1) # IDs (rowid) in SQLite are 1.. musly is 0..
            all_genres = genre_cfg['all_genres'] if 'all_genres' in genre_cfg else None
            acceptable_genres=set()
            if 'genres' in meta:
                acceptable_genres.update(meta['genres'])
                if 'genres' in genre_cfg:
                    for genre in meta['genres']:
                        for group in genre_cfg['genres']:
                            if genre in group:
                                acceptable_genres.update(group)

        num_sim = count * 50
        if num_sim<MIN_NUM_SIM:
            num_sim = MIN_NUM_SIM
        if num_sim>len(paths):
            num_sim = len(paths)

        simtracks = get_similars(track_id, mus, num_sim, mta, tdb, cfg)

        resp=[]
        prev_id=-1

        tracks=[]
        for simtrack in simtracks:
            if simtrack['id']==prev_id:
                break
            prev_id=simtrack['id']
            if math.isnan(simtrack['sim']):
                continue

            track = tdb.get_track(simtrack['id']+1)
            if raw:
                tracks.append({'path':paths[simtrack['id']], 'sim':simtrack['sim']})
            else:
                if match_artist and track['artist'] != meta['artist']:
                    continue
                if not match_artist and track['ignore']:
                    continue
                if simtrack['id']!=track_id and 'title' in track and 'title' in meta and track['title'] == meta['title']:
                    continue

                sim = simtrack['sim'] + genre_adjust(meta, track, acceptable_genres, all_genres, no_genre_match_adj, genre_group_adj)
                tracks.append({'path':paths[simtrack['id']], 'sim':sim})
            if len(tracks)==MIN_NUM_SIM:
                break

        if not raw:
            # Might have used genres to adjust sim score, so need to re-sort
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


@similarity_app.route('/api/attrmix', methods=['GET', 'POST'])
def attrmix_api():
    isPost = False
    if request.method=='GET':
        params = request.args.to_dict(flat=False)
    else:
        isPost = True
        params = request.get_json()
        _LOGGER.debug('Request: %s' % json.dumps(params))

    if not params:
        abort(400)

    cfg = similarity_app.get_config()
    tdb = tracks_db.TracksDb(cfg)

    if not cfg['essentia']['enabled'] or not cfg['essentia']['highlevel']:
        _LOGGER.error('Essentia highlevel not supported/enabled')
        abort(400)

    count = int(get_value(params, 'count', DEFAULT_ATTTRMIX_COUNT, isPost))
    if count<1:
        _LOGGER.error('Count must be higher than 0')
        abort(400)

    req_filters=[]

    for attr in ['duration', 'bpm']:
        minv = int(get_value(params, 'min%s' % attr, 0, isPost))
        maxv = int(get_value(params, 'max%s' % attr, 0, isPost))
        if minv>maxv:
            x = maxv
            maxv=minv
            minv=x

        if minv>0:
            req_filters.append('%s >= %d' % (attr, minv))
        if maxv>0:
            req_filters.append('%s <= %d' % (attr, maxv))


    for attr in tracks_db.ESSENTIA_HIGHLEVEL_ATTRIBS:
        strval = get_value(params, attr, '', isPost)
        val = 0.0
        if strval is None or strval=='':
            continue
        elif strval == 'y':
            val = cfg['essentia']['attrmix_yes']
        elif strval == 'n':
            val = cfg['essentia']['attrmix_no']
        else:
            val = int(strval)/100.0

        if val>0.0 and val<0.5:
            req_filters.append('%s <= %.1f' % (attr, val))
        elif val>0.5:
            req_filters.append('%s >= %.1f' % (attr, val))

    if len(req_filters)<1:
        _LOGGER.error('No filters supplied')
        abort(400)

    root = get_music_path(params, cfg)
    _LOGGER.debug('Music root: %s' % root)
    add_file_protocol = int(get_value(params, 'addfp', 0, isPost))==1
    no_repeat_artist = int(get_value(params, 'norepart', 5, isPost))
    no_repeat_album = int(get_value(params, 'norepalb', 5, isPost))

    try:
        genres = set(params['genre']) if 'genre' in params else None
        exclude_christmas = int(get_value(params, 'filterxmas', '0', isPost))==1 and datetime.now().month!=12
        rows = tdb.get_track_ids(req_filters)
        selected_tracks = []
        resp = []
        artist_map = {} # Map of artist -> last index
        album_map = {}  # Map of album -> last index
        titles = set()
        _LOGGER.debug('Num rows: %d' % len(rows))
        for row in rows:
            track = tdb.get_track(row[0], True)
            if genres is not None and not filters.genre_matches({}, genres, track):
                _LOGGER.debug('DISCARD(genre) %s' % json.dumps(track, cls=SetEncoder))
                continue
            if exclude_christmas and filters.is_christmas(track):
                 _LOGGER.debug('DISCARD(christmas) %s' % json.dumps(track, cls=SetEncoder))
                 continue
            if track['title'] in titles:
                _LOGGER.debug('DISCARD(title) %s' % json.dumps(track, cls=SetEncoder))
                continue
            if no_repeat_artist>0 and track['artist'] in artist_map and (len(selected_tracks)-artist_map[track['artist']])<no_repeat_artist:
                titles.add(track['title'])
                _LOGGER.debug('FILTER(artist) %s' % json.dumps(track, cls=SetEncoder))
                continue
            akey = get_album_key(track)
            if no_repeat_album > 0 and akey is not None and akey in album_map and (len(selected_tracks)-album_map[akey])<no_repeat_album:
                titles.add(track['title'])
                _LOGGER.debug('FILTER(album) %s' % json.dumps(track, cls=SetEncoder))
                continue

            resp.append(encode(root, track['file'], add_file_protocol))
            if len(resp)>=count:
                break

            selected_tracks.append(track)
            if no_repeat_album>0 and akey is not None:
                album_map[akey] = len(selected_tracks)
            if no_repeat_artist>0:
                artist_map[track['artist']] = len(selected_tracks)
            titles.add(track['title'])

        if get_value(params, 'format', '', isPost)=='text':
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
    bpm_max_diff = int(get_value(params, 'maxbpmdiff', 0, isPost))
    filter_on_key = int(get_value(params, 'filterkey', '0', isPost))==1
    filter_on_attribs = int(get_value(params, 'filterattrib', '0', isPost))==1

    if no_repeat_artist<0 or no_repeat_artist>200:
        no_repeat_artist = DEFAULT_NUM_PREV_TRACKS_FILTER_ARTIST
    if no_repeat_album<0 or no_repeat_album>200:
        no_repeat_album = DEFAULT_NUM_PREV_TRACKS_FILTER_ALBUM

    mus, mta = similarity_app.get_musly()
    paths = similarity_app.get_paths()
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
            track_id = paths.index( track )
            _LOGGER.debug('Get %d similar track(s) to %s, index: %d' % (count, track, track_id))
        except:
            pass
        if track_id is not None and track_id>=0 and track_id not in track_ids:
            track_ids.append(track_id)
            skip_track_ids.add(track_id)
            meta = tdb.get_track(track_id+1) # IDs (rowid) in SQLite are 1.. musly is 0..
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
                track_id = paths.index(track)
            except:
                pass
            if track_id is not None and track_id>=0:
                skip_track_ids.add(track_id)
                meta = tdb.get_track(track_id+1) # IDs (rowid) in SQLite are 1.. musly is 0..
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
    # If only 1 seed then get more tracks to increase randomness
    if 1==len(track_ids):
        similarity_count *= 2
    tracks_per_seed = int(similarity_count*2.5) if similarity_count<15 else similarity_count

    num_sim = count * len(track_ids) * 50
    if num_sim<MIN_NUM_SIM:
        num_sim = MIN_NUM_SIM
    if num_sim>len(paths):
        num_sim = len(paths)

    matched_artists={}
    artist_max_sim = 0.01 if cfg['bliss']['enabled'] else 0.1
    for track_id in track_ids:
        # Query musly and/or essentia for similar tracks
        simtracks = get_similars(track_id, mus, num_sim, mta, tdb, cfg)
        accepted_tracks = 0
        for simtrack in simtracks:
            if math.isnan(simtrack['sim']):
                continue
            if simtrack['sim']>max_similarity:
                break

            if (simtrack['sim']>0.0) and (simtrack['sim']<=max_similarity) and (not simtrack['id'] in skip_track_ids):
                prev_idx = similar_track_positions[simtrack['id']] if simtrack['id'] in similar_track_positions else -1
                meta = similar_tracks[prev_idx] if prev_idx>=0 else tdb.get_track(simtrack['id']+1) # IDs (rowid) in SQLite are 1.. musly is 0..
                filtered_due_to = None
                if prev_idx>=0:
                    # Seen from previous seed, so set similarity to lowest value
                    sim = simtrack['sim'] + genre_adjust(track_id_seed_metadata[track_id], meta, seed_genres, all_genres, no_genre_match_adj, genre_group_adj)
                    if similar_tracks[prev_idx]['similarity']>sim:
                        _LOGGER.debug('SEEN %d before, prev:%f, current:%f' % (simtrack['id'], similar_tracks[prev_idx]['similarity'], sim))
                        similar_tracks[prev_idx]['similarity']=sim
                elif not meta:
                    _LOGGER.debug('DISCARD(not found) ID:%d Path:%s Similarity:%f' % (simtrack['id'], paths[simtrack['id']], simtrack['sim']))
                    skip_track_ids.add(simtrack['id'])
                elif meta['ignore']:
                    _LOGGER.debug('DISCARD(ignore) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                    skip_track_ids.add(simtrack['id'])
                elif (min_duration>0 or max_duration>0) and not filters.check_duration(min_duration, max_duration, meta):
                    _LOGGER.debug('DISCARD(duration) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                    skip_track_ids.add(simtrack['id'])
                elif match_genre and not filters.genre_matches(genre_cfg, acceptable_genres, meta):
                    _LOGGER.debug('DISCARD(genre) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                    skip_track_ids.add(simtrack['id'])
                elif exclude_christmas and filters.is_christmas(meta):
                    _LOGGER.debug('DISCARD(xmas) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                    skip_track_ids.add(simtrack['id'])
                else:
                    if (ess_cfg['enabled'] or cfg['bliss']['enabled']) and bpm_max_diff is not None and bpm_max_diff>0 and bpm_max_diff<150:
                        filtered_due_to = filters.check_bpm(track_id_seed_metadata[track_id], meta, bpm_max_diff)
                        if filtered_due_to is not None:
                            _LOGGER.debug('FILTERED(attribs(%s)) ID:%d Path:%s Similarity:%f Meta:%s' % (filtered_due_to, simtrack['id'], paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                            set_filtered(simtrack, paths, filtered_tracks, 'attribs')
                            continue

                    if ess_cfg['enabled']:
                        if filter_on_key:
                            filtered_due_to = filters.check_key(track_id_seed_metadata[track_id], meta, ess_cfg)
                        if filtered_due_to is None and filter_on_attribs:
                            filtered_due_to = filters.check_attribs(track_id_seed_metadata[track_id], meta, ess_cfg)
                        if filtered_due_to is not None:
                            _LOGGER.debug('FILTERED(attribs(%s)) ID:%d Path:%s Similarity:%f Meta:%s' % (filtered_due_to, simtrack['id'], paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                            set_filtered(simtrack, paths, filtered_tracks, 'attribs')
                            continue

                    if no_repeat_artist>0:
                        if meta['artist'] in filter_out['artists']:
                            _LOGGER.debug('FILTERED(artist) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                            set_filtered(simtrack, paths, filtered_tracks, 'meta')

                            if meta['artist'] in matched_artists and len(matched_artists[meta['artist']]['tracks'])<5 and simtrack['sim'] - matched_artists[meta['artist']]['similarity'] <= artist_max_sim:
                                # Only add this track as a possibility if album not in previous
                                akey = get_album_key(meta)
                                if akey is None or akey not in filter_out['albums']:
                                    matched_artists[meta['artist']]['tracks'].append({'path':paths[simtrack['id']], 'similarity':simtrack['sim']})
                            continue

                    if no_repeat_album>0:
                        akey = get_album_key(meta)
                        if akey is not None and akey in filter_out['albums']:
                            _LOGGER.debug('FILTERED(album) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                            set_filtered(simtrack, paths, filtered_tracks, 'meta')
                            continue

                    if 'title' in meta and meta['title'] in filter_out['titles']:
                        _LOGGER.debug('FILTERED(title) ID:%d Path:%s Similarity:%f Meta:%s' % (simtrack['id'], paths[simtrack['id']], simtrack['sim'], json.dumps(meta, cls=SetEncoder)))
                        set_filtered(simtrack, paths, filtered_tracks, 'meta')
                        continue

                    key = '%s::%s::%s' % (meta['artist'], meta['album'], meta['albumartist'] if 'albumartist' in meta and meta['albumartist'] is not None else '')
                    sim = simtrack['sim'] + genre_adjust(track_id_seed_metadata[track_id], meta, seed_genres, all_genres, no_genre_match_adj, genre_group_adj)

                    _LOGGER.debug('USABLE ID:%d Path:%s Similarity:%f AdjSim:%f Meta:%s' % (simtrack['id'], paths[simtrack['id']], simtrack['sim'], sim, json.dumps(meta, cls=SetEncoder)))
                    similar_tracks.append({'path':paths[simtrack['id']], 'similarity':sim})
                    # Keep list of all tracks of an artist, so that we can randomly select one => we don't always use the same one
                    matched_artists[meta['artist']]={'similarity':simtrack['sim'], 'tracks':[{'path':paths[simtrack['id']], 'similarity':sim}], 'pos':len(similar_tracks)-1}
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
    if shuffle:
        similar_tracks = similar_tracks[:similarity_count]
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


@similarity_app.route('/api/config', methods=['GET'])
def config_api():
    return json.dumps(similarity_app.get_config())


@similarity_app.route('/api/features', methods=['GET'])
def essentia_api():
    cfg = similarity_app.get_config()
    f=''
    if cfg['essentia']['enabled']:
        f += 'E' if cfg['essentia']['highlevel'] else 'e'
    if cfg['bliss']['enabled']:
        f+='b'
    return f


genre_list = None
@similarity_app.route('/api/genres', methods=['GET'])
def genres_api():
    global genre_list
    if genre_list is None:
        cfg = similarity_app.get_config()
        tdb = tracks_db.TracksDb(cfg)
        genre_list = tdb.get_genres()
    if genre_list is None:
        abort(404)
    return '\n'.join(genre_list)


def start_app(args, config, jukebox_path):
    similarity_app.init(args, config, jukebox_path)
    _LOGGER.debug('Ready to process requests')
    similarity_app.run(host=config['host'], port=config['port'])
