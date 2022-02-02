#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021-2022 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import logging, os, pickle, random, signal, sqlite3, tempfile
from . import cue, essentia_analysis, tags, tracks_db, musly
from concurrent.futures import as_completed, CancelledError, ThreadPoolExecutor
from multiprocessing import Pipe, Process

_LOGGER = logging.getLogger(__name__)
AUDIO_EXTENSIONS = ['m4a', 'mp3', 'ogg', 'flac', 'opus']
TRACKS_PER_DB_COMMIT_MUSLY = 500
TRACKS_PER_DB_COMMIT_ESSENTIA = 100 # Analysing with Essentia is slower, so commit DB more often if this is enabled

STATUS_OK       = 0
STATUS_ERROR    = 1
STATUS_FILTERED = 2


futures_list = []
should_stop = False
def sig_handler(signum, frame):
    global should_stop
    global futures_list
    should_stop = True
    _LOGGER.info('Intercepted CTRL-C, stopping (might take a few seconds)...')

    # Cancel any non-running tasks
    for future in futures_list:
        future.cancel()


def analyze_audiofile(pipe, libmusly, essentia_extractor, index, db_path, abs_path, extract_len, extract_start, essentia_cache, essentia_highlevel):
    resp = {'index':index, 'status':STATUS_OK}

    if extract_len>0:
        mres = None
        try:
            mus = musly.Musly(libmusly, True)
            mres = mus.analyze_file(db_path, abs_path, extract_len, extract_start)
        except:
            pass
        if mres is not None and mres['ok']:
            resp['musly'] = pickle.dumps(bytes(mres['mtrack']), protocol=4)
        else:
            resp['status'] = STATUS_ERROR
            resp['extra'] = 'Musly'

    if len(essentia_extractor)>1 and STATUS_OK==resp['status']:
        eres = None
        try:
            eres = essentia_analysis.analyse_track(index, essentia_extractor, db_path, abs_path, essentia_cache, essentia_highlevel)
        except:
            pass
        if eres is None:
            resp['status'] = STATUS_ERROR
            resp['extra'] = 'Essentia'
        else:
            resp['essentia'] = eres

    pipe.send(resp);
    pipe.close()


def analyze_file(index, total, db_path, abs_path, config, musly_analysis, essentia_analysis):
    if should_stop:
        return None
    digits=len(str(total))
    fmt="[{:>%d} {:3}%%] {}" % ((digits*2)+1)
    _LOGGER.debug(fmt.format("%d/%d" % (index+1, total), int((index+1)*100/total), db_path))

    # Check file has valid tags
    meta = tags.read_tags(abs_path, tracks_db.GENRE_SEPARATOR)
    if meta is None or 'title' not in meta or meta['title'] is None:
        return {'index':index, 'status':STATUS_ERROR, 'extra':'Tags'}

    if 'duration' in meta and meta['duration']>0 and ((config['minduration']>0 and meta['duration']<config['minduration']) or (config['maxduration']>0 and meta['duration']>config['maxduration'])):
        return {'index':index, 'status':STATUS_FILTERED, 'extra':'Duration'}

    if 'genres' in meta and config['excludegenres'] is not None:
        for genre in meta['genres']:
            if genre in config['excludegenres']:
                return {'index':index, 'status':STATUS_FILTERED, 'extra':'Genre (%s)' % genre}

    if (not essentia_analysis or (essentia_analysis and not config['essentia']['enabled'])) and not musly_analysis:
        return {'index':index, 'status':STATUS_ERROR, 'extra':'Config'}

    pout, pin = Pipe(duplex=False)

    essentia_cache = config['paths']['cache'] if 'cache' in config['paths'] else "-"
    extractor = config['essentia']['extractor'] if essentia_analysis and config['essentia']['enabled'] else "-"
    musly_extractlen = config['musly']['extractlen'] if musly_analysis else 0
    p = Process(target=analyze_audiofile, args=(pin, config['musly']['lib'], extractor, index, db_path, abs_path, musly_extractlen, config['musly']['extractstart'], essentia_cache, config['essentia']['highlevel']))
    p.start()
    r = pout.recv()
    p.terminate()
    p.join()
    r['meta'] = meta
    return r


def process_files(config, trks_db, allfiles):
    numtracks = len(allfiles)
    analysed = 0
    failed = 0
    filtered = 0
    _LOGGER.info("Have {} files to analyze".format(numtracks))
    _LOGGER.info("Extraction length: {}s extraction start: {}s".format(config['musly']['extractlen'], config['musly']['extractstart']))
    if config['essentia']['enabled']:
        if config['essentia']['highlevel']:
            _LOGGER.info("Analyzing with Musly and Essentia (high level)")
        else:
            _LOGGER.info("Analyzing with Musly and Essentia")
    else:
        _LOGGER.info("Analyzing with Musly")

    global futures_list
    futures_list = []
    inserts_since_commit = 0

    tracks_per_db_commit = TRACKS_PER_DB_COMMIT_ESSENTIA if config['essentia']['enabled'] else TRACKS_PER_DB_COMMIT_MUSLY
    with ThreadPoolExecutor(max_workers=config['threads']) as executor:
        for i in range(numtracks):
            futures = executor.submit(analyze_file, i, numtracks, allfiles[i]['db'], allfiles[i]['abs'], config, allfiles[i]['musly'], allfiles[i]['essentia'])
            futures_list.append(futures)
        for future in as_completed(futures_list):
            try:
                result = future.result()

                if result['status'] == STATUS_OK:
                    eres = result['essentia'] if 'essentia' in result else None
                    mres = result['musly'] if 'musly' in result else None
                    meta = result['meta'] if 'meta' in result else meta
                    trks_db.add(allfiles[result['index']]['db'], mres, eres, meta)
                    inserts_since_commit += 1
                    analysed += 1
                    if inserts_since_commit >= tracks_per_db_commit:
                        inserts_since_commit = 0
                        trks_db.commit()
                elif result['status'] == STATUS_ERROR:
                    failed += 1
                    _LOGGER.error('Failed to analyze %s (%s)' % (allfiles[result['index']]['db'], result['extra']))
                elif result['status'] == STATUS_FILTERED:
                    filtered += 1
                    _LOGGER.debug('Skipped %s (%s)' % (allfiles[result['index']]['db'], result['extra']))

            except CancelledError as e:
                pass
            except Exception as e:
                if not should_stop:
                    msg = str(e)
                    if not "'NoneType' object is not subscriptable" in msg:
                        _LOGGER.debug('Thread exception? - %s' % msg)
                pass
    return analysed, failed, filtered


def get_files_to_analyse(trks_db, lms_db, lms_path, path, files, local_root_len, tmp_path, tmp_path_len, meta_only, force, essentia_enabled):
    if not os.path.exists(path):
        _LOGGER.error("'%s' does not exist" % path)
        return
    if os.path.isdir(path):
        for e in sorted(os.listdir(path)):
            get_files_to_analyse(trks_db, lms_db, lms_path, os.path.join(path, e), files, local_root_len, tmp_path, tmp_path_len, meta_only, force, essentia_enabled)

    parts = path.rsplit('.', 1)
    if len(parts)>1 and parts[1].lower() in AUDIO_EXTENSIONS:
        if os.path.exists(parts[0]+'.cue'):
            if tmp_path is not None:
                for track in cue.get_cue_tracks(lms_db, lms_path, path, local_root_len, tmp_path):
                    db_path = track['file'][tmp_path_len:].replace('\\', '/')
                    musly = not meta_only and ('m' in force or not trks_db.file_analysed_with_musly(db_path))
                    essentia = not meta_only and ('e' in force or essentia_enabled and not trks_db.file_analysed_with_essentia(db_path))
                    if meta_only or musly or essentia:
                        files.append({'abs':track['file'], 'db':db_path, 'track':track, 'src':path, 'musly':musly, 'essentia':essentia})
        else:
            db_path = path[local_root_len:].replace('\\', '/')
            musly = not meta_only and ('m' in force or not trks_db.file_analysed_with_musly(db_path))
            essentia = not meta_only and ('e' in force or essentia_enabled and not trks_db.file_analysed_with_essentia(db_path))
            if meta_only or musly or essentia:
                files.append({'abs':path, 'db':db_path, 'musly':musly, 'essentia':essentia})


def analyse_files(config, path, remove_tracks, meta_only, force, jukebox, max_tracks):
    signal.signal(signal.SIGINT, sig_handler)
    _LOGGER.debug('Analyse %s' % path)
    trks_db = tracks_db.TracksDb(config, True)
    lms_db = sqlite3.connect(config['lmsdb']) if 'lmsdb' in config else None
        
    files = []
    local_root_len = len(config['paths']['local'])
    lms_path = config['paths']['lms'] if 'lms' in config['paths'] else None
    temp_dir = config['paths']['tmp'] if 'tmp' in config['paths'] else None
    removed_tracks = trks_db.remove_old_tracks(config['paths']['local']) if remove_tracks and not meta_only else False
    mus = musly.Musly(config['musly']['lib'])
    essentia_enabled = config['essentia']['enabled']

    tmp_dir = None if lms_db is None else tempfile.TemporaryDirectory(dir=temp_dir)
    tmp_path = None
    tmp_path_len = 0
    if tmp_dir is not None:
        tmp_path = tmp_dir.name+'/'
        tmp_path_len = len(tmp_path)
        _LOGGER.debug('Temp folder: %s' % tmp_path)

    get_files_to_analyse(trks_db, lms_db, lms_path, path, files, local_root_len, tmp_path, tmp_path_len, meta_only, force, essentia_enabled)
    _LOGGER.debug('Num tracks to update: %d' % len(files))
    if len(files)>max_tracks:
        _LOGGER.debug('Only analysing %d tracks' % max_tracks)
        files=files[:max_tracks]
    cue.split_cue_tracks(files, config['threads'])
    added_tracks = len(files)>0
    analysed = 0
    if added_tracks or removed_tracks:
        if added_tracks:
            if meta_only:
                _LOGGER.debug('Read metadata')
                total=len(files)
                digits=len(str(total))
                fmt="[{:>%d} {:3}%%] {}" % ((digits*2)+1)
                index = 0
                for f in files:
                    _LOGGER.debug(fmt.format("%d/%d" % (index+1, total), int((index+1)*100/total), f['db']))
                    trks_db.set_metadata(f)
                    index +=1
            else:
                analysed, failed, filtered = process_files(config, trks_db, files)
                _LOGGER.info('Analysed: %d, Failed: %d, Filtered: %d' % (analysed, failed, filtered))

        trks_db.commit()

        if should_stop:
            trks_db.close()
        else:
            if removed_tracks or (analysed>0 and not meta_only):
                (paths, db_tracks) = mus.get_alltracks_db(trks_db.get_cursor())
                mus.add_tracks(db_tracks, config['musly']['styletracks'], config['musly']['styletracksmethod'], trks_db)
            trks_db.close()
            if removed_tracks or (analysed>0 and not meta_only):
                mus.write_jukebox(jukebox)
    if tmp_dir is not None:
        tmp_dir.cleanup()
    _LOGGER.debug('Finished analysis')
