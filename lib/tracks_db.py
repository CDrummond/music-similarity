#
# Analyse files with Musly, Essentia, and Bliss, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021-2022 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import json, logging, os, sqlite3
from . import cue, tags

DB_FILE = 'music-similarity.db'
GENRE_SEPARATOR = ';'
_LOGGER = logging.getLogger(__name__)
ESSENTIA_HIGHLEVEL_ATTRIBS = ['danceable', 'aggressive', 'electronic', 'acoustic', 'happy', 'party', 'relaxed', 'sad', 'dark', 'tonal', 'voice']
ESSENTIA_LOWLEVEL_ATTRIBS = ['bpm', 'key']

album_rem = ['anniversary edition', 'deluxe edition', 'expanded edition', 'extended edition', 'special edition', 'deluxe', 'deluxe version', 'extended deluxe', 'super deluxe', 're-issue', 'remastered', 'mixed', 'remixed and remastered']
artist_rem = ['feat', 'ft', 'featuring']
title_rem = ['demo', 'demo version', 'radio edit', 'remastered', 'session version', 'live', 'live acoustic', 'acoustic', 'industrial remix', 'alternative version', 'alternate version', 'original mix', 'bonus track', 're-recording', 'alternate']


def normalize_str(s):
    if not s:
        return s
    s=s.replace('.', '').replace('(', '').replace(')', '').replace('[', '').replace(']', '').replace(' & ', ' and ')
    while '  ' in s:
        s=s.replace('  ', ' ')
    return s


def normalize_album(album):
    if not album:
        return album
    s = album.lower()
    global album_rem
    for r in album_rem:
        s=s.replace(' (%s)' % r, '').replace(' [%s]' % r, '')
    return normalize_str(s)


def normalize_artist(artist):
    if not artist:
        return artist
    ar = normalize_str(artist.lower())
    global artist_rem
    for r in artist_rem:
        pos = ar.find(' %s ' % r)
        if pos>2:
            return ar[:pos]
    return ar
        

def normalize_title(title):
    if not title:
        return title
    s = title.lower()
    global title_rem
    for r in title_rem:
        s=s.replace(' (%s)' % r, '').replace(' [%s]' % r, '')
    return normalize_str(s)


def set_normalize_options(opts):
    if 'album' in opts and isinstance(opts['album'], list):
        global album_rem
        album_rem = [e.lower() for e in opts['album']]
    if 'artist' in opts and isinstance(opts['artist'], list):
        global artist_rem
        artist_rem = [e.lower() for e in opts['album']]
    if 'title' in opts and isinstance(opts['title'], list):
        global title_rem
        title_rem = [e.lower() for e in opts['title']]


class TracksDb(object):
    def __init__(self, config, create=False):
        path = os.path.join(config['paths']['db'], DB_FILE)
        self.use_bliss = config['bliss']['enabled']
        self.use_essentia = config['essentia']['enabled']
        self.use_essentia_hl = config['essentia']['enabled'] and config['essentia']['highlevel']
        self.conn = None
        self.cursor = None
        if create or os.path.exists(path):
            self.conn = sqlite3.connect(path)
            self.cursor = self.conn.cursor()
            if create:
                for table in ['tracks', 'tracks_tmp']:
                    if config['essentia']['highlevel']:
                        self.cursor.execute('''CREATE TABLE IF NOT EXISTS %s (
                                    file varchar UNIQUE NOT NULL,
                                    title varchar,
                                    artist varchar,
                                    album varchar,
                                    albumartist varchar,
                                    genre varchar,
                                    duration integer,
                                    ignore integer,
                                    danceable integer,
                                    aggressive integer,
                                    electronic integer,
                                    acoustic integer,
                                    happy integer,
                                    party integer,
                                    relaxed integer,
                                    sad integer,
                                    dark integer,
                                    tonal integer,
                                    voice integer,
                                    bpm integer,
                                    key varchar,
                                    vals blob,
                                    bliss blob)''' % table)
                    else:
                        self.cursor.execute('''CREATE TABLE IF NOT EXISTS %s (
                                    file varchar UNIQUE NOT NULL,
                                    title varchar,
                                    artist varchar,
                                    album varchar,
                                    albumartist varchar,
                                    genre varchar,
                                    duration integer,
                                    ignore integer,
                                    bpm integer,
                                    key varchar,
                                    vals blob,
                                    bliss blob)''' % table)

                    # Add 'key' column - will fail if already exists (which it should, but older instances might not have it)
                    try:
                        self.cursor.execute('ALTER TABLE %s ADD COLUMN key varchar default null' % table)
                    except:
                        pass

                    try:
                        self.cursor.execute('ALTER TABLE %s ADD COLUMN bliss blob default null' % table)
                    except:
                        pass

                    if config['essentia']['highlevel']:
                        for col in ESSENTIA_HIGHLEVEL_ATTRIBS:
                            try:
                                self.cursor.execute('ALTER TABLE %s ADD COLUMN %s integer default null' % (table, col))
                            except:
                                pass

                self.cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS tracks_idx ON tracks(file)')


    def commit(self):
        if self.conn is not None:
            self.conn.commit()


    def close(self):
        if self.conn is not None:
            self.cursor.close()
            self.conn.close()


    def add(self, path, musly, essentia, bliss, meta, bpm):
        if musly is not None:
            if self.file_entry_exists(path):
                self.cursor.execute('UPDATE tracks SET vals=? WHERE file=?', (musly, path))
            else:
                self.cursor.execute('INSERT INTO tracks (file, vals) VALUES (?, ?)', (path, musly))

        if essentia is not None:
            if self.file_entry_exists(path):
                self.cursor.execute('UPDATE tracks SET bpm=?, key=? WHERE file=?', (essentia['bpm'], essentia['key'], path))
            else:
                self.cursor.execute('INSERT INTO tracks (file, bpm, key) VALUES (?, ?, ?)', (path, essentia['bpm'], essentia['key']))

            if self.use_essentia_hl and 'danceable' in essentia:
                try:
                    self.cursor.execute('UPDATE tracks SET danceable=?, aggressive=?, electronic=?, acoustic=?, happy=?, party=?, relaxed=?, sad=?, dark=?, tonal=?, voice=? WHERE file=?', (essentia['danceable'], essentia['aggressive'], essentia['electronic'], essentia['acoustic'], essentia['happy'], essentia['party'], essentia['relaxed'], essentia['sad'], essentia['dark'], essentia['tonal'], essentia['voice'], path))
                except:
                    pass

        if bliss is not None:
            if self.file_entry_exists(path):
                self.cursor.execute('UPDATE tracks SET bliss=? WHERE file=?', (bliss, path))
            else:
                self.cursor.execute('INSERT INTO tracks (file, bliss) VALUES (?, ?)', (path, bliss))

        if bpm is not None and self.file_entry_exists(path):
            self.cursor.execute('UPDATE tracks SET bpm=? WHERE file=? AND BPM IS NULL', (bpm, path))

        if meta is not None:
            self.update_metadata(path, meta)


    def get_track(self, i, withFile=False):
        try:
            cols = 'title, artist, album, albumartist, genre, duration, ignore'
            if self.use_essentia:
                for ess in ESSENTIA_LOWLEVEL_ATTRIBS:
                    cols+=', %s' % ess
                if self.use_essentia_hl:
                    for ess in ESSENTIA_HIGHLEVEL_ATTRIBS:
                        cols+=', %s' % ess
            elif self.use_bliss:
                cols+=', bpm'
            if withFile:
                cols+=', file'
            self.cursor.execute('SELECT %s FROM tracks WHERE rowid=%d' % (cols, i))
            row = self.cursor.fetchone()
            meta = {'title':normalize_title(row[0]), 'artist':normalize_artist(row[1]), 'album':normalize_album(row[2]), 'albumartist':normalize_artist(row[3]), 'duration':row[5]}
            if row[4] and len(row[4])>0:
                meta['genres']=set(row[4].split(GENRE_SEPARATOR))
            meta['ignore']=row[6] is not None and row[6]==1

            col = 7
            if self.use_essentia:
                for ess in ESSENTIA_LOWLEVEL_ATTRIBS:
                    meta[ess]=row[col]
                    col+=1
                if self.use_essentia_hl:
                    for ess in ESSENTIA_HIGHLEVEL_ATTRIBS:
                        meta[ess]=row[col]
                        col+=1
            elif self.use_bliss:
                meta['bpm']=row[col]
                col+=1
            if withFile:
                meta['file']=row[col]
            return meta
        except Exception as e:
            _LOGGER.error('Failed to read metadata for %d - %s' % (i, str(e)))
            pass
        return None


    def update_metadata(self, path, meta):
        #if not self.file_entry_exists(path):
        #    self.cursor.execute('INSERT INTO tracks (file) VALUES (?)', (path))

        if not 'albumartist' in meta or meta['albumartist'] is None:
            if not 'genres' in meta or meta['genres'] is None:
                self.cursor.execute('UPDATE tracks SET title=?, artist=?, album=?, duration=? WHERE file=?', (meta['title'], meta['artist'], meta['album'], meta['duration'], path))
            else:
                self.cursor.execute('UPDATE tracks SET title=?, artist=?, album=?, genre=?, duration=? WHERE file=?', (meta['title'], meta['artist'], meta['album'], GENRE_SEPARATOR.join(meta['genres']), meta['duration'], path))
        else:
            if not 'genres' in meta or meta['genres'] is None:
                self.cursor.execute('UPDATE tracks SET title=?, artist=?, album=?, albumartist=?, duration=? WHERE file=?', (meta['title'], meta['artist'], meta['album'], meta['albumartist'], meta['duration'], path))
            else:
                self.cursor.execute('UPDATE tracks SET title=?, artist=?, album=?, albumartist=?, genre=?, duration=? WHERE file=?', (meta['title'], meta['artist'], meta['album'], meta['albumartist'], GENRE_SEPARATOR.join(meta['genres']), meta['duration'], path))


    def set_metadata(self, track):
        meta = tags.read_tags(track['abs'], GENRE_SEPARATOR)
        if meta is not None:
            if 'track' in track and 'title' in track['track']: # Tracks from CUE files
                meta['title'] = track['track']['title']
            self.update_metadata(track['db'], meta)


    def remove_old_tracks(self, source_path, dry_run):
        non_existant_files = []
        _LOGGER.debug('Looking for old tracks to remove')
        try:
            self.cursor.execute('SELECT file FROM tracks')
            rows = self.cursor.fetchall()
            for row in rows:
                if not os.path.exists(os.path.join(source_path, cue.convert_to_source(row[0]))):
                    _LOGGER.debug("'%s' no longer exists" % row[0])
                    non_existant_files.append(row[0])

            _LOGGER.debug('Num old tracks: %d' % len(non_existant_files))
            if dry_run:
                return False
            if len(non_existant_files)>0:
                # Remove entries...
                for path in non_existant_files:
                    self.cursor.execute('DELETE from tracks where file=?', (path, ))
                self.force_rowid_update()
                return True
        except Exception as e:
            _LOGGER.error('Failed to remove old tracks - %s' % str(e))
            pass
        return False


    def update_if_required(self):
        try:
            self.cursor.execute("SELECT sql from sqlite_master where type='table' and name='tracks'")
            row = self.cursor.fetchone()
            if row is not None and row[0] is not None:
                sql = row[0].replace('\t', ' ').replace('  ', ' ')
                if '"vals" blob NOT NULL' in sql:
                    _LOGGER.debug('Updating DB to remove old constraint')
                    sql = sql.replace('"vals" blob NOT NULL', '"vals" blob')
                    self.commit()
                    self.cursor.execute('ALTER TABLE tracks RENAME TO tracks_old')
                    self.cursor.execute('DELETE from tracks_tmp')
                    self.cursor.execute('DROP TABLE tracks_tmp')
                    self.cursor.execute(sql)
                    self.cursor.execute('INSERT INTO tracks SELECT * from tracks_old')
                    self.cursor.execute('DELETE from tracks_old')
                    self.cursor.execute('DROP TABLE tracks_old')
                    sql = sql.replace('CREATE TABLE "tracks"', 'CREATE TABLE "tracks_tmp"')
                    self.cursor.execute(sql)
                    self.commit()
                    self.cursor.execute('VACUUM')
                    self.commit()
                    return
            _LOGGER.debug('No update required')
        except Exception as e:
            _LOGGER.error(str(e))
            pass


    def force_rowid_update(self):
        ''' Copy tracks into tmp and back - to force rowid to be updated '''
        self.commit()
        self.cursor.execute('DELETE from tracks_tmp')
        self.cursor.execute('INSERT INTO tracks_tmp SELECT * from tracks')
        self.cursor.execute('DELETE from tracks')
        self.cursor.execute('INSERT INTO tracks SELECT * from tracks_tmp')
        self.cursor.execute('DELETE from tracks_tmp')
        self.commit()
        self.cursor.execute('VACUUM')
        self.commit()


    def file_entry_exists(self, path):
        self.cursor.execute('SELECT rowid FROM tracks WHERE file=?', (path,))
        return self.cursor.fetchone() is not None


    def file_analysed_with_musly(self, path):
        try:
            self.cursor.execute('SELECT vals FROM tracks WHERE file=?', (path,))
            row = self.cursor.fetchone()
            return row is not None and row[0] is not None
        except:
            return False


    def file_analysed_with_essentia(self, path):
        try:
            self.cursor.execute('SELECT bpm FROM tracks WHERE file=?', (path,))
            row = self.cursor.fetchone()
            return row is not None and row[0] is not None
        except:
            return False


    def file_analysed_with_bliss(self, path):
        try:
            self.cursor.execute('SELECT bliss FROM tracks WHERE file=?', (path,))
            row = self.cursor.fetchone()
            return row is not None and row[0] is not None
        except:
            return False


    def files_analysed_with_musly(self):
        try:
            self.cursor.execute('SELECT vals FROM tracks WHERE vals is not null LIMIT 1')
            row = self.cursor.fetchone()
            return row is not None and row[0] is not None
        except:
            return False


    def files_analysed_with_essentia(self):
        try:
            self.cursor.execute('SELECT %s FROM tracks WHERE %s is not null LIMIT 1' % (ESSENTIA_LOWLEVEL_ATTRIBS[1], ESSENTIA_LOWLEVEL_ATTRIBS[1]))
            row = self.cursor.fetchone()
            return row is not None and row[0] is not None
        except:
            return False


    def files_analysed_with_essentia_highlevel(self):
        try:
            self.cursor.execute('SELECT %s FROM tracks WHERE %s is not null LIMIT 1' % (ESSENTIA_HIGHLEVEL_ATTRIBS[0], ESSENTIA_HIGHLEVEL_ATTRIBS[0]))
            row = self.cursor.fetchone()
            return row is not None and row[0] is not None
        except:
            return False


    def files_analysed_with_bliss(self):
        try:
            self.cursor.execute('SELECT bliss FROM tracks WHERE bliss is not null LIMIT 1')
            row = self.cursor.fetchone()
            return row is not None and row[0] is not None
        except:
            return False


    def get_albums(self):
        albums = []
        self.cursor.execute('SELECT distinct albumartist, album FROM tracks')
        rows = self.cursor.fetchall()
        for row in rows:
            albums.append({'artist':row[0], 'title':row[1]})
        return albums


    def num_tracks(self):
        self.cursor.execute('SELECT count(*) FROM tracks')
        row = self.cursor.fetchone()
        if row is not None:
            return int(row[0])
        return 0


    def get_genres_with_count(self):
        genres = []
        self.cursor.execute('SELECT distinct genre from tracks')
        rows = self.cursor.fetchall()
        for row in rows:
            self.cursor.execute('SELECT count(*) FROM tracks WHERE genre=?', (row[0],))
            cr = self.cursor.fetchone()
            if cr is not None:
                genres.append({'genre':row[0], 'count':cr[0]})
        return genres


    def get_sample_track(self, album):
        ''' Get a random track betwen 60 and 5mins '''
        self.cursor.execute('SELECT rowid from tracks where albumartist=? and album=? and duration>=90 and duration<=300 order by random() limit 1', (album['artist'], album['title']))
        row = self.cursor.fetchone()
        if row is None:
            self.cursor.execute('SELECT rowid from tracks where albumartist=? and album=? and duration>=90 and duration<=420 order by random() limit 1', (album['artist'], album['title']))
            row = self.cursor.fetchone()
        if row is None:
            self.cursor.execute('SELECT rowid from tracks where albumartist=? and album=? and duration>=90 and duration<=600 order by random() limit 1', (album['artist'], album['title']))
            row = self.cursor.fetchone()
        if row is None:
            self.cursor.execute('SELECT rowid from tracks where albumartist=? and album=? and duration>=90 order by random() limit 1', (album['artist'], album['title']))
            row = self.cursor.fetchone()
        if row is None:
            self.cursor.execute('SELECT rowid from tracks where albumartist=? and album=? order by random() limit 1', (album['artist'], album['title']))
            row = self.cursor.fetchone()
        if row is None:
            return None
        return row[0]


    def get_sample_genre_tracks(self, genre, count):
        tracks=[]
        self.cursor.execute('SELECT rowid from tracks where genre=? and duration>=90 and duration<=300 order by random() limit ?', (genre, count))
        rows = self.cursor.fetchall()
        if rows is not None:
            for row in rows:
                tracks.append(row[0]-1)
        if len(tracks)>=count:
            return tracks

        self.cursor.execute('SELECT rowid from tracks where genre=? and duration>300 and duration<=420 order by random() limit ?', (genre, count))
        rows = self.cursor.fetchall()
        if rows is not None:
            for row in rows:
                tracks.append(row[0]-1)
        return tracks


    def get_other_sample_tracks(self, limit, exclude):
        tracks=[]
        exclude_set = set(exclude)
        self.cursor.execute('SELECT rowid from tracks where duration>=90 and duration<=420 order by random()')
        rows = self.cursor.fetchall()
        for row in rows:
            index = row[0]-1
            if index not in exclude_set:
                tracks.append(index)
                if len(tracks)==limit:
                    return tracks
        if len(tracks)<limit:
            self.cursor.execute('SELECT rowid from tracks where duration>=420 order by random()')
            rows = self.cursor.fetchall()
            for row in rows:
                index = row[0]-1
                if index not in exclude_set:
                    tracks.append(index)
                    if len(tracks)==limit:
                        return tracks
        if len(tracks)<limit:
            self.cursor.execute('SELECT rowid from tracks order by random()')
            rows = self.cursor.fetchall()
            for row in rows:
                index = row[0]-1
                if index not in exclude_set:
                    tracks.append(index)
                    if len(tracks)==limit:
                        return tracks
        return tracks


    def get_track_ids(self, filters):
        sql = 'SELECT rowid FROM tracks WHERE ignore IS NOT 1'
        for f in filters:
            sql += ' AND %s' % f
        sql += ' ORDER BY random()'
        _LOGGER.debug('Select tracks using SQL:%s' % sql)
        self.cursor.execute(sql)
        return self.cursor.fetchall()


    def get_genres(self):
        genres=set()
        self.cursor.execute('SELECT DISTINCT genre from tracks')
        rows = self.cursor.fetchall()
        for row in rows:
            if row[0] is not None:
                genres.update(set(row[0].split(GENRE_SEPARATOR)))
        genre_list = list(genres)
        genre_list.sort()
        return genre_list


    def get_cursor(self):
        return self.cursor
