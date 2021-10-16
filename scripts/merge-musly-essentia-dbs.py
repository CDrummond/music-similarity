#!/usr/bin/env python3

#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2020-2021 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import argparse, os, sqlite3, sys
from lib import config, tracks_db, version


def info(s):
    print("INFO: %s" % s)


def error(s):
    print("ERROR: %s" % s)
    exit(-1)


def ignore(conn, cursor, f):
    if not os.path.exists(f):
        error('%s does not exist' % f)

    try:
        lines=[]
        with open(f, 'r') as ifile:
            lines = ifile.readlines();
        cursor.execute('UPDATE tracks set ignore=0')
        for line in lines:
            val = line.strip()
            info('Ignore: %s' % val)
            cursor.execute('UPDATE tracks set ignore=1 where file like ?', ('{}%'.format(val),))
        conn.commit()
    except Exception as e:
        error('Failed to parse %s - %s' % (f, str(e)))


if __name__=='__main__':
    parser = argparse.ArgumentParser(description='Merge Essenti and Musly DBs to create Music Simliartiy DB (v%s)' % version.MUSIC_SIMILARITY_VERSION)
    parser.add_argument('-c', '--config', type=str, help='Config file (default: config.json)', default='config.json')
    parser.add_argument('-m', '--musly', type=str, help='Musly database file', default='musly.db')
    parser.add_argument('-e', '--essentia', type=str, help='Essentia database file', default='essentia.db')
    args = parser.parse_args()
    cfg = config.read_config(args.config, False)

    try:
        mconn = sqlite3.connect(args.musly)
        mcursor = mconn.cursor()
    except:
        error("Failed to open musly DB")

    try:
        econn = sqlite3.connect(args.essentia)
        ecursor = econn.cursor()
    except:
        error("Failed to open essentia DB")

    tdb = tracks_db.TracksDb(cfg)
    mcursor.execute('SELECT file, vals, title, artist, album, albumartist, genre, duration, ignore FROM tracks')
    ess_cols = ''
    first = True
    for ess in tracks_db.ESSENTIA_ATTRIBS:
        if not first:
            ess_cols+=", "
        ess_cols+=ess
        first=False
    for mrow in mcursor:
        ecursor.execute('SELECT %s FROM tracks WHERE file=?' % ess_cols, (mrow[0],))
        erow = ecursor.fetchone()
        if erow is not None:
            eres={}
            for e in range(len(tracks_db.ESSENTIA_ATTRIBS)):
                eres[tracks_db.ESSENTIA_ATTRIBS[e]]=erow[e]
            tdb.add(mrow[0], mrow[1], eres)
            meta = {'title':mrow[2], 'artist':mrow[3], 'album':mrow[4], 'albumartist':mrow[5], 'duration':mrow[7], 'ignore':mrow[8]}
            if mrow[6] is not None:
                meta['genres'] = mrow[6].split(tracks_db.GENRE_SEPARATOR)
            tdb.update_metadata(mrow[0], meta)
        else:
            info('%s has no essentia results, not adding to DB' % mrow[0])
    tdb.commit()
    tdb.close()

