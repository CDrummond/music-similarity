# Music Similarity

This is a python3 script to analyse your music collection with Musly and
(optionally) Essentia, and to provide a simple HTTP API allowing the creation
of mix of similar music for LMS.


## Musly

This script can use the [Musly audio music similarity library](https://github.com/CDrummond/musly)
to analyse tracks, and to locate similar tracks based upon timbre. This project
contains the following pre-built versions of this library:

1. Linux 64-bit - `linux/x86-64/libmusly.so`
2. Raspbian 32-bit, *not* linked to libav, therefore cannot be used for
analysis - `linux/armv7l/libmusly.so`
3. Raspbian 32-bit, linked against libav - `linux/armv7l/raspbian-buster/libav/libmusly.so`
4. Windows built with MinGW32, requires 32-bit Python - `windows/mingw32/libmusly.dll`
5. Windows built with MinGW64, requires 64-bit Python - `windows/mingw64/libmusly.dll`
6. macOS i386/64-bit, compiled by AF-1 - `mac/i386/libmusly.dylib`


## Essentia

Essentia is used to extract certain attributes about each track - e.g. which
key its in, bpm, etc - and the similarity API can then be configured to use
these attributes to filter the results (e.g. only accept tracks in a similar
key, etc.)

The Essentia binaries and models are only required for analysing tracks, and are
not required for locating similar tracks. Therefore, if analysis is performed on
one machine and similar tracks located on another (e.g. a Raspberry Pi) the
contents of the `essentia` folder, and the Essentia extractor, are not required
on the similarity machine.

Essentia binaries may be downloaded from [acousticbrainz.org](https://similarity.acousticbrainz.org/download).
However, please note that these *only* support low-level analysis (bpm, key). To
support high-level analysis (danceability, aggresiveness, etc.) you will need to
compile your own build of Essentia - or use the prebuilt binary if on Linux
(`linux/x86-64/essentia_streaming_extractor_music`).

- [Linux i386](http://ftp.acousticbrainz.org/pub/acousticbrainz/essentia-extractor-v2.1_beta2-linux-i686.tar.gz)
- [Linux x86_64](http://ftp.acousticbrainz.org/pub/acousticbrainz/essentia-extractor-v2.1_beta2-linux-x86_64.tar.gz)
- [Mac 64 bit](http://ftp.acousticbrainz.org/pub/acousticbrainz/essentia-extractor-v2.1_beta2-2-gbb40004-osx.tar.gz)
- [Windows 32](http://ftp.acousticbrainz.org/pub/acousticbrainz/essentia-extractor-v2.1_beta2-1-ge3940c0-win-i686.zip)

If you download a new version of the extractor, place this within `linux`,
`windows`, or `mac` sub-folder.


## Bliss

This script can use the [Bliss music analyser](https://github.com/Polochon-street/bliss-rs)
to analyse tracks, and to locate similar tracks.


## Analysing Tracks

Before starting the server your music needs to be analysed with Musly and
Essentia. This is accomplished via:

```
./music-similarity.py --analyse /path/to/music/folder
```

This can take about 20hrs to process 25k tracks. The process analyses tracks
with with Musly, with Essentia, initialises Musly's 'jukebox' style with 1000
random tracks, and extracts certain tags. If re-run new tracks will be added,
and old (non-existent) will be removed. Pass `--keep-old` to keep these old
tracks.

To analyse the Music path stored in the config file, the following shortcut can
be used:

```
./music-similarity.py --analyse m
```

### CUE files

If the analysis locates a music file with a similarly named CUE file (e.g.
`artist/album/album name.flac` and `artist/album/album name.cue`) then it will
read the track listing from the LMS db file and use `ffmpeg` to split the
music file into temporary 128kbps MP3 files for analysis. The files are removed
once analysis is complete.


## Testing Analysis

Musly has a [bug](https://github.com/dominikschnitzer/musly/issues/43) where
sometimes it gives the same similarity to all tracks, which will obviously break
the music similarity feature. To test if the analysis is correct you can run the
script in test mode:

```
./music-similarity.py --log-level INFO --test
```

This will query Musly for the 50 most similar tracks to the 1st analysed track.
It then checks that there are different similarities, and if not an error
message is shown.

If this script states that there is an error you can try simply removing the
jukebox file and re-running this script - it will recreate the jukebox with
random tracks. If this keeps failing it might be better to adjust the
`styletracks` config item, delete the jukebox, and test again.

Alternatively, you can have this script run until it receives valid similarities
from Musly. In this mode the script will test the jukebox, remove it if the test
fails, recreate jukebox, test the jukebox, ...

```
./music-similarity.py --log-level INFO --test --repeat
```

## Similarity service

`music-similarity` can be installed as a system service, or started manually,
to provide a Music similarity service that can be called from the LMS plugin,
etc.

```
./music-similarity.py
```

...when the service starts, it will confirm that the number of tracks in its
SQLite database is the same as the number in the 'jukebox'. If the number
differs, the jukebox is recreated.


## Configuration

Configuration is read from a JSON file (default name is `config.json`). This has
the following basic items:

```
{
 "paths":{
  "db":"/home/user/.local/share/music-similarity/",
  "local":"/home/Music/"
 }
}
```

* `paths.db` should be the path where the SQLite and jukebox files created by
this app can be written to / read from.
* `paths.local` should be the path where this script can access your music
files. This can be different to the path that LMS uses if you are running
analysis on a different machine to where you would run the script as the
similarity server. This script will only store the paths relative to this
location - eg. if `paths.local=/home/music/` then `/home/music/A/b.mp3` will
be stored as `A/b.mp3`. Only required if analysing tracks.

The `linux/x86-64`, `linux/armv7l`, `mac`, and `windows` folders contain example
config files for each system.

Please refer to `docs/OtherConfig.md` for all configuration items.

## Credits

`lib/musly.py` (which is used as a python interface to the Musly library) is
taken, and modified, from Roland0's [Musly Integration for LMS](https://www.nexus0.net/pub/sw/lmsmusly)

The Essentia binary is taken from Roland0's [LMS Essentia Integration](https://www.nexus0.net/pub/sw/lmsessentia/)

The macOS build of the Musly library has been built by AF-1 and a copy taken
from their [github repo.](https://github.com/AF-1/sobras/tree/main/lms-music-similarity_on_macos)
