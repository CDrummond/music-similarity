#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import logging, os, pickle, random, sqlite3, tempfile
from . import cue, essentia_analysis, tracks_db, musly
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Process, Pipe

_LOGGER = logging.getLogger(__name__)
AUDIO_EXTENSIONS = ['m4a', 'mp3', 'ogg', 'flac', 'opus']


def analyze_audiofile(pipe, libmusly, essentia_extractor, index, db_path, abs_path, extract_len, extract_start, essentia_cache, tmp_path):
    mus = musly.Musly(libmusly, True)
    mres = mus.analyze_file(db_path, abs_path, extract_len, extract_start)
    if len(essentia_extractor)>1:
        eres = essentia_analysis.analyse_track(index, essentia_extractor, db_path, abs_path, tmp_path, essentia_cache)
        ok = mres['ok'] and eres is not None
        pipe.send({'index':index, 'ok':ok, 'musly':pickle.dumps(bytes(mres['mtrack']), protocol=4), 'essentia':eres})
    else:
        pipe.send({'index':index, 'ok':mres['ok'], 'musly':pickle.dumps(bytes(mres['mtrack']), protocol=4)})
    pipe.close()


def analyze_file(index, total, db_path, abs_path, config, tmp_path):
    if 'stop' in config and os.path.exists(config['stop']):
        return None
    _LOGGER.debug("[{}/{} {}%] Analyze: {}".format(index+1, total, int((index+1)*100/total), db_path))
    pout, pin = Pipe(duplex=False)
    
    essentia_cache = config['paths']['cache'] if 'cache' in config['paths'] else "-"
    extractor = config['essentia']['extractor'] if config['essentia']['enabled'] else "-"
    p = Process(target=analyze_audiofile, args=(pin, config['musly']['lib'], extractor, index, db_path, abs_path, config['musly']['extractlen'], config['musly']['extractstart'], essentia_cache, tmp_path))
    p.start()
    r = pout.recv()
    p.terminate()
    p.join()
    return r


def process_files(config, trks_db, allfiles, tmp_path):
    numtracks = len(allfiles)
    _LOGGER.info("Have {} files to analyze".format(numtracks))
    _LOGGER.info("Extraction length: {}s extraction start: {}s".format(config['musly']['extractlen'], config['musly']['extractstart']))
    
    futures_list = []
    inserts_since_commit = 0
    with ThreadPoolExecutor(max_workers=config['threads']) as executor:
        for i in range(numtracks):
            futures = executor.submit(analyze_file, i, numtracks, allfiles[i]['db'], allfiles[i]['abs'], config, tmp_path)
            futures_list.append(futures)
        for future in futures_list:
            try:
                result = future.result()
                if result['ok']:
                    eres = result['essentia'] if 'essentia' in result else None
                    trks_db.add(allfiles[result['index']]['db'], result['musly'], eres)
                    inserts_since_commit += 1
                    if inserts_since_commit >= 500:
                        inserts_since_commit = 0
                        trks_db.commit()
            except Exception as e:
                _LOGGER.debug("Thread exception? - %s" % str(e))
                pass


def get_files_to_analyse(trks_db, lms_db, lms_path, path, files, local_root_len, tmp_path, tmp_path_len, meta_only, essentia_enabled):
    if not os.path.exists(path):
        _LOGGER.error("'%s' does not exist" % path)
        return
    if os.path.isdir(path):
        for e in sorted(os.listdir(path)):
            get_files_to_analyse(trks_db, lms_db, lms_path, os.path.join(path, e), files, local_root_len, tmp_path, tmp_path_len, meta_only, essentia_enabled)

    parts = path.rsplit('.', 1)
    if len(parts)>1 and parts[1].lower() in AUDIO_EXTENSIONS:
        if os.path.exists(parts[0]+'.cue'):
            for track in cue.get_cue_tracks(lms_db, lms_path, path, local_root_len, tmp_path):
                if meta_only or not trks_db.file_already_analysed(track['file'][tmp_path_len:]) or (essentia_enabled and not trks_db.file_already_analysed_with_essentia(track['file'][tmp_path_len:])):
                    files.append({'abs':track['file'], 'db':track['file'][tmp_path_len:], 'track':track, 'src':path})
        elif meta_only or not trks_db.file_already_analysed(path[local_root_len:]) or (essentia_enabled and not trks_db.file_already_analysed_with_essentia(path[local_root_len:])):
            files.append({'abs':path, 'db':path[local_root_len:]})


def analyse_files(config, path, remove_tracks, meta_only, jukebox):
    _LOGGER.debug('Analyse %s' % path)
    trks_db = tracks_db.TracksDb(config)
    lms_db = sqlite3.connect(config['lmsdb']) if 'lmsdb' in config else None
        
    files = []
    local_root_len = len(config['paths']['local'])
    lms_path = config['paths']['lms']
    temp_dir = config['paths']['tmp'] if 'tmp' in config['paths'] else None
    removed_tracks = trks_db.remove_old_tracks(config['paths']['local']) if remove_tracks and not meta_only else False
    mus = musly.Musly(config['musly']['lib'])
    essentia_enabled = config['essentia']['enabled']

    with tempfile.TemporaryDirectory(dir=temp_dir) as tmp_path:
        _LOGGER.debug('Temp folder: %s' % tmp_path)
        get_files_to_analyse(trks_db, lms_db, lms_path, path, files, local_root_len, tmp_path+'/', len(tmp_path)+1, meta_only, essentia_enabled)
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

            if removed_tracks or (added_tracks and not meta_only):
                (paths, db_tracks) = mus.get_alltracks_db(trks_db.get_cursor())
                mus.add_tracks(db_tracks, config['musly']['styletracks'], config['musly']['styletracksmethod'], trks_db)
            trks_db.close()
            if removed_tracks or not meta_only:
                mus.write_jukebox(jukebox)
    _LOGGER.debug('Finished analysis')
