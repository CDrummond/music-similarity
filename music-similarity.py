#!/usr/bin/env python3

#
# Analyse files with Musly, Essentia, and Bliss, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021-2022 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import argparse, logging, os
from lib import analysis, app, config, test, tracks_db, version

JUKEBOX_FILE = 'music-similarity.jukebox'
_LOGGER = logging.getLogger(__name__)
        
if __name__=='__main__':
    parser = argparse.ArgumentParser(description='Music Similarity (v%s)' % version.MUSIC_SIMILARITY_VERSION)
    parser.add_argument('-c', '--config', type=str, help='Config file (default: config.json)', default='config.json')
    parser.add_argument('-l', '--log-level', action='store', choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'], default='INFO', help='Set log level (default: %(default)s)')
    parser.add_argument('-a', '--analyse', metavar='PATH', type=str, help="Analyse file/folder (use 'm' for configured music folder)", default='')
    parser.add_argument('-d', '--dry-run', action='store_true', default=False, help='Show number of files to be updated, removed, etc, but do nothing,  (used in conjuction with --analyse)')
    parser.add_argument('-M', '--max-tracks', action='store', type=int, default=-1, help='Set maximum number of tracks to analyse')
    parser.add_argument('-m', '--meta-only', action='store_true', default=False, help='Update metadata database only (used in conjuction with --analyse)')
    parser.add_argument('-k', '--keep-old', action='store_true', default=False, help='Do not remove non-existant tracks from DB (used in conjuction with --analyse)')
    parser.add_argument('-f', '--force', type=str, default='', help="Force rescan of specified data (use 'm' for musly, 'e' for essentia, 'b' for bliss, 'meb' for all; used in conjuction with --analyse)")
    parser.add_argument('-t', '--test', action='store_true', default=False, help='Test musly')
    parser.add_argument('-r', '--repeat', action='store_true', default=False, help='Repeat test until OK (used in conjuction with --test)')
    parser.add_argument('-u', '--update-db', action='store_true', default=False, help='Update database to remove contraints')
    args = parser.parse_args()
    logging.basicConfig(format='%(asctime)s %(levelname).1s %(message)s', level=args.log_level, datefmt='%Y-%m-%d %H:%M:%S')
    cfg = config.read_config(args.config, args.analyse)
    _LOGGER.debug('Init DB')
    jukebox_file = os.path.join(cfg['paths']['db'], JUKEBOX_FILE)
    if args.update_db:
        db = tracks_db.TracksDb(cfg, False)
        db.update_if_required()
    elif args.analyse:
        path = cfg['paths']['local'] if args.analyse =='m' else args.analyse
        analysis.analyse_files(cfg, path, not args.keep_old, args.meta_only, args.force, jukebox_file, args.max_tracks, args.dry_run)
    elif args.test:
        test.test_jukebox(cfg, jukebox_file, args.repeat)
    else:
        app.start_app(args, cfg, jukebox_file)

