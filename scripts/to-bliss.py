#!/usr/bin/env python3
import argparse, os, pickle, sqlite3, sys

GENRE_SEPARATOR = ';'

def convert(mp, bp):
    msim = sqlite3.connect(mp)
    bliss = sqlite3.connect(bp)
    mc = msim.cursor()
    bc = bliss.cursor()
    bc.execute('''CREATE TABLE IF NOT EXISTS Tracks (
                   File varchar UNIQUE NOT NULL,
                   Title varchar,
                   Artist varchar,
                   AlbumArtist varchar,
                   Album varchar,
                   Genre varchar,
                   Duration integer,
                   Ignore integer,
                   Tempo real,
                   Zcr real,
                   MeanSpectralCentroid real,
                   StdDevSpectralCentroid real, 
                   MeanSpectralRolloff real,
                   StdDevSpectralRolloff real,
                   MeanSpectralFlatness real,
                   StdDevSpectralFlatness real,
                   MeanLoudness real,
                   StdDevLoudness real,
                   Chroma1 real,
                   Chroma2 real,
                   Chroma3 real,
                   Chroma4 real,
                   Chroma5 real,
                   Chroma6 real,
                   Chroma7 real,
                   Chroma8 real,
                   Chroma9 real,
                   Chroma10 real)''')
    bc.execute('CREATE UNIQUE INDEX IF NOT EXISTS Tracks_idx ON Tracks(File)')
    mc.execute('SELECT file, title, artist, albumartist, album, genre, duration, ignore, bliss FROM tracks')
    rows = mc.fetchall()
    for row in rows:
        b = pickle.loads(row[8])
        bc.execute('INSERT into Tracks (File, Title, Artist, AlbumArtist, Album, Genre, Duration, Ignore, Tempo, Zcr, MeanSpectralCentroid, StdDevSpectralCentroid, MeanSpectralRolloff, StdDevSpectralRolloff, MeanSpectralFlatness, StdDevSpectralFlatness, MeanLoudness, StdDevLoudness, Chroma1, Chroma2, Chroma3, Chroma4, Chroma5, Chroma6, Chroma7, Chroma8, Chroma9, Chroma10) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7], b[8], b[9], b[10], b[11], b[12], b[13], b[14], b[15], b[16], b[17], b[18], b[19]))

    bliss.commit()
    bc.close()
    bliss.close()


if __name__=='__main__':
    parser = argparse.ArgumentParser(description='Create Bliss DB from MusicSimilarity DB')
    parser.add_argument('-m', '--msimdb', type=str, help='MusicSimilarity DB file', default='music-similarity.db')
    parser.add_argument('-b', '--blissdb', type=str, help='Bliss DB file', default='bliss.db')
    args = parser.parse_args()
    convert(args.msimdb, args.blissdb)
