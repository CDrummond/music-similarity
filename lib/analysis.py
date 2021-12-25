#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import logging, os, pickle, random, signal, sqlite3, tempfile
from . import cue, essentia_analysis, tracks_db, musly
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Process, Pipe

_LOGGER = logging.getLogger(__name__)
AUDIO_EXTENSIONS = ['m4a', 'mp3', 'ogg', 'flac', 'opus']
TRACKS_PER_DB_COMMIT = 500


should_stop = False
def sig_handler(signum, frame):
    global should_stop
    should_stop = True
    _LOGGER.info('Intercepted CTRL-C, stopping (might take a few seconds)...')


def analyze_audiofile(pipe, libmusly, essentia_extractor, index, db_path, abs_path, extract_len, extract_start, essentia_cache, essentia_highlevel, tmp_path):
    resp = {'index':index, 'ok':False}

    if extract_len>0:
        mus = musly.Musly(libmusly, True)
        mres = mus.analyze_file(db_path, abs_path, extract_len, extract_start)
        resp['ok'] = mres['ok']
        resp['musly'] = pickle.dumps(bytes(mres['mtrack']), protocol=4)

    if len(essentia_extractor)>1 and (extract_len<=0 or resp['ok']):
        eres = essentia_analysis.analyse_track(index, essentia_extractor, db_path, abs_path, tmp_path, essentia_cache, essentia_highlevel)
        resp['ok'] = eres is not None
        resp['essentia'] = eres

    pipe.send(resp);
    pipe.close()


def analyze_file(index, total, db_path, abs_path, config, tmp_path, musly_analysis, essentia_analysis):
    global should_stop
    if should_stop:
        return None
    digits=len(str(total))
    fmt="[{:>%d} {:3}%%] {}" % ((digits*2)+1)
    _LOGGER.debug(fmt.format("%d/%d" % (index+1, total), int((index+1)*100/total), db_path))
    pout, pin = Pipe(duplex=False)
    
    essentia_cache = config['paths']['cache'] if 'cache' in config['paths'] else "-"
    extractor = config['essentia']['extractor'] if essentia_analysis and config['essentia']['enabled'] else "-"
    musly_extractlen = config['musly']['extractlen'] if musly_analysis else 0
    p = Process(target=analyze_audiofile, args=(pin, config['musly']['lib'], extractor, index, db_path, abs_path, musly_extractlen, config['musly']['extractstart'], essentia_cache, config['essentia']['highlevel'], tmp_path))
    p.start()
    r = pout.recv()
    p.terminate()
    p.join()
    return r


def process_files(config, trks_db, allfiles, tmp_path):
    numtracks = len(allfiles)
    _LOGGER.info("Have {} files to analyze".format(numtracks))
    _LOGGER.info("Extraction length: {}s extraction start: {}s".format(config['musly']['extractlen'], config['musly']['extractstart']))
    if config['essentia']['enabled']:
        if config['essentia']['highlevel']:
            _LOGGER.info("Analyzing with Musly and Essentia (high level)")
        else:
            _LOGGER.info("Analyzing with Musly and Essentia")
    else:
        _LOGGER.info("Analyzing with Musly")
    
    futures_list = []
    inserts_since_commit = 0
    with ThreadPoolExecutor(max_workers=config['threads']) as executor:
        for i in range(numtracks):
            futures = executor.submit(analyze_file, i, numtracks, allfiles[i]['db'], allfiles[i]['abs'], config, tmp_path, allfiles[i]['musly'], allfiles[i]['essentia'])
            futures_list.append(futures)
        for future in futures_list:
            try:
                result = future.result()
                if result['ok']:
                    eres = result['essentia'] if 'essentia' in result else None
                    mres = result['musly'] if 'musly' in result else None
                    trks_db.add(allfiles[result['index']]['db'], mres, eres)
                    inserts_since_commit += 1
                    if inserts_since_commit >= TRACKS_PER_DB_COMMIT:
                        inserts_since_commit = 0
                        trks_db.commit()
            except Exception as e:
                global should_stop
                if not should_stop:
                    msg = str(e)
                    if not "'NoneType' object is not subscriptable" in msg:
                        _LOGGER.debug("Thread exception? - %s" % msg)
                pass


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


def analyse_files(config, path, remove_tracks, meta_only, force, jukebox):
    global should_stop
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

    with tempfile.TemporaryDirectory(dir=temp_dir) as tmp_path:
        _LOGGER.debug('Temp folder: %s' % tmp_path)
        get_files_to_analyse(trks_db, lms_db, lms_path, path, files, local_root_len, tmp_path+'/', len(tmp_path)+1, meta_only, force, essentia_enabled)
        _LOGGER.debug('Num tracks to update: %d' % len(files))
        cue.split_cue_tracks(files, config['threads'])
        added_tracks = len(files)>0
        if added_tracks or removed_tracks:
            if added_tracks:
                if not meta_only:
                    process_files(config, trks_db, files, tmp_path)
                _LOGGER.debug('Save metadata')
                for file in files:
                    trks_db.set_metadata(file)
            trks_db.commit()

            if should_stop:
                trks_db.close()
            else:
                if removed_tracks or (added_tracks and not meta_only):
                    (paths, db_tracks) = mus.get_alltracks_db(trks_db.get_cursor())
                    mus.add_tracks(db_tracks, config['musly']['styletracks'], config['musly']['styletracksmethod'], trks_db)
                trks_db.close()
                if removed_tracks or not meta_only:
                    mus.write_jukebox(jukebox)
    _LOGGER.debug('Finished analysis')
