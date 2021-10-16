#!/usr/bin/env python3

#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2020-2021 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import argparse
import os
import sqlite3
import sys
from lib import version


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
    parser = argparse.ArgumentParser(description='Update Music Simliartiy DB (v%s)' % version.MUSIC_SIMILARITY_VERSION)
    parser.add_argument('-d', '--db', type=str, help='Database file', default='music-similarity.db')
    parser.add_argument('-i', '--ignore', type=str, help='Path to file containing items to ignore', default=None)
    args = parser.parse_args()

    if args.ignore is None:
        info("Nothing todo")
    else:
        try:
            conn = sqlite3.connect(args.db)
            cursor = conn.cursor()
        except:
            error("Failed to open DB")

        ignore(conn, cursor, args.ignore)
