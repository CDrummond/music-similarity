#
# Analyse files with Musly, Essentia, and Bliss, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021-2022 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import json, logging

_LOGGER = logging.getLogger(__name__)

def get_ogg_or_flac(path):
    from mutagen.oggflac import OggFLAC
    from mutagen.oggopus import OggOpus
    from mutagen.oggvorbis import OggVorbis
    from mutagen.flac import FLAC

    try:
        return OggVorbis(path)
    except:
        pass
    try:
        return FLAC(path)
    except:
        pass
    try:
        return OggFLAC(path)
    except:
        pass
    try:
        return OggOpus(path)
    except:
        pass
    return None


def read_tags(path, genre_separator):
    from mutagen.id3 import ID3
    from mutagen.mp3 import MP3
    from mutagen.mp4 import MP4

    try:
        audio = MP4(path)
        tags = {'title':str(audio['\xa9nam'][0]), 'artist':str(audio['\xa9ART'][0]), 'album':str(audio['\xa9alb'][0]), 'duration':int(audio.info.length), 'albumartist':None, 'genres':None}
        if 'aART' in audio:
            tags['albumartist']=str(audio['aART'][0])
        if '\xa9gen' in audio:
            tags['genres']=[]
            for g in audio['\xa9gen']:
                tags['genres'].append(str(g))
        #_LOGGER.debug('MP4 File: %s Meta: %s' % (path, json.dumps(tags)))
        return tags
    except:
        pass

    try:
        audio = MP3(path)
        tags = {'title':str(audio['TIT2']), 'artist':str(audio['TPE1']), 'album':str(audio['TALB']), 'duration':int(audio.info.length), 'albumartist':None, 'genres':None}
        if 'TPE2' in audio:
            tags['albumartist']=str(audio['TPE2'])
        if 'TCON' in audio:
            tags['genres']=str(audio['TCON']).split(genre_separator)
        #_LOGGER.debug('MP3 File: %s Meta: %s' % (path, json.dumps(tags)))
        return tags
    except Exception as e:
        #print("EX:%s" % str(e))
        pass

    try:
        audio = ID3(path)
        tags = {'title':str(audio['TIT2']), 'artist':str(audio['TPE1']), 'album':str(audio['TALB']), 'duration':0, 'albumartist':None, 'genres':None}
        if 'TPE2' in audio:
            tags['albumartist']=str(audio['TPE2'])
        if 'TCON' in audio:
            tags['genres']=str(audio['TCON']).split(genre_separator)
        #_LOGGER.debug('ID3 File: %s Meta: %s' % (path, json.dumps(tags)))
        return tags
    except:
        pass

    audio = get_ogg_or_flac(path)
    if audio:
        try:
            tags = {'title':str(audio['TITLE'][0]), 'artist':str(audio['ARTIST'][0]), 'album':str(audio['ALBUM'][0]), 'duration':int(audio.info.length), 'albumartist':None, 'genres':None}
            if 'ALBUMARTIST' in audio:
                tags['albumartist']=str(audio['ALBUMARTIST'][0])
            if 'GENRE' in audio:
                tags['genres']=[]
                for g in audio['GENRE']:
                    tags['genres'].append(str(g))
            #_LOGGER.debug('OGG File: %s Meta: %s' % (path, json.dumps(tags)))
            return tags
        except:
            pass

    _LOGGER.debug('File:%s Meta:NONE' % path)
    return None
