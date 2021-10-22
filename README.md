# Music Similarity

Simple python3 script to create a mix of music tracks for LMS.

## Musly

This service uses the [Musly audio music similarity library](https://github.com/CDrummond/musly)
This library needs to be compiled, and `config.json` (from this project) updated
to store the location of this library. This repo contains pre-built versions
for:

1. Fedora 64-bit - `lib/x86-64/fedora/libmusly.so`
2. Raspbian Buster 32-bit, *not* linked to libav, therefore cannot be used for
analysis - `lib/armv7l/raspbian-buster/libmusly.so`
3. Raspbian Buster 32-bit, linked against libav - `lib/armv7l/raspbian-buster/libav/libmusly.so`

**macOS**

Instructions, and binaries, for Musly on macOS can be found [here](https://github.com/AF-1/sobras/tree/main/lms-music-similarity_on_macos)


## Essentia

The Essentia binaries and models are only required for analysing tracks, and are
not required for locating similar tracks. Therefore, if analysis is performed on
one machine and similar tracks located on another (e.g. a Raspberry Pi) the
contents of the `essentia` folder are not required on the similarity machine.


## Analysing Tracks

Before starting the server your music needs to be analysed with Essentia and
Musly. This is accomplished via:

```
./music-similarity.py --analyse /path/to/music/folder
```

This can take about 20hrs to process 25k tracks. The process analyses tracks
with Essentia, analyses with Musly, adds them to Musly, initialises Musly's
'jukebox' style with 1000 random tracks, and extracts certain tags. If re-run
new tracks will be added, and old (non-existent) will be removed. Pass
`--keep-old` to keep these old tracks.

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

`music-similarity` can be installed as a Systemd service, or started manually,
to provide a Music similarity service that can be called from the LMS plugin,
etc.

```
./music-similarity.py
```

...when the service starts, it will confirm that the number of tracks in its
SQLite database is the same as the number in the 'jukebox'. If the number
differs, the jukebox is recreated.

To install as a systemd service:

1. Edit `music-similarity.service` to ensure paths, etc, are correct
2. Copy `music-similarity.service` to `/etc/systemd/system`
3. `sudo systemctl daemon-reload`
4. `sudo systemcrl enable music-similarity`
5. `sudo systemctl start music-similarity`


## Configuration

Configuration is read from a JSON file (default name is `config.json`). This has
the following format:

```
{
 "musly":{
  "lib":"lib/x86-64/fedora/libmusly.so",
  "styletracks":1000,
  "styletracksmethod":"genres",
  "extractlen":120,
  "extractstart":-210
 },
 "essentia":{
  "enabled":true,
  "extractor":"essentia/bin/x86-64/essentia_streaming_extractor_music"
 },
 "paths":{
  "db":"/home/user/.local/share/music-similarity/",
  "local":"/home/Music/",
  "lms":"/media/Music/",
  "tmp":"/tmp/",
  "cache:"",
 },
 "lmsdb":"/path/to/lms/Cache/library.db",
 "normalize":{
  "artist":["feet", "ft", "featuring"],
  "album":["deluxe edition", "remastered"],
  "title"["demo", "radio edit"]
 },
 "port":11000,
 "host":"0.0.0.0",
 "threads":8
}
```

* `musly.lib` should contain the path the Musly shared library - path is
relative to `music-similarity.py`
* `musly.styletracks` A  subset of tracks is passed to Musly's `setmusicstyle`
function, by default 1000 random tracks is chosen. This config item can be used
to alter this. Note, however, the larger the number here the longer it takes to
for this call to complete. As a rough guide it takes ~1min per 1000 tracks.
If you change this config item after the jukebox is written you will need to
delete the jukebox file and restart the server. Only used if analyising tracks.
* `musly.styletracksmethod` configures how tracks are chosen for styletracks. If
set to `genres` (which is the default if not set) then the meta-data db is
queried for how many track each genre has and tracks are chosen for each of
these genres based upon the percentage of tracks in a genre. If set to `albums`
then at least one track from each album is used. If set to anything else then
random tracks are chosen. Only used if analyising tracks.
* `musly.extractlen` The maximum length in seconds of the file to decode. If
zero or greater than the file length, then the whole file will be decoded. Note,
however, that only a maximum of 5 minutes is used for analysis. Only used if
analyising tracks.
* `musly.extractstart` The starting position in seconds of the excerpt to
decode. If zero, decoding starts at the beginning. If negative, the excerpt is
centred in the file, but starts at `-extractstart` the latest. If positive and
`extractstart`+`extractlen` exceeds the file length, then the excerpt is taken
from the end of the file. Only used if analyising tracks.
* `essentia.enabled` should be set to true if Essentia is to be used for
filtering.
* `essentia.extractor` should contain the path to the Essentia extractor - path
is relative to `music-similarity.py` Only required if analyising tracks.
* `paths.db` should be the path where the SQLite and jukebox files created by
this app can be written to or can be read from.
* `paths.local` should be the path where this script can access your music
files. This can be different to `path.lms` if you are running analysis on a
different machine to where you would run the script as the similarity server.
This script will only store the paths relative to this location - eg.
`paths.local=/home/music/` then `/home/music/A/b.mp3` will be stored as
`A/b.mp3`. Only required if analysing tracks.
* `paths.lms` should be the path where LMS accesses your music files. The
similarity server will remove this path from API calls, so that it can look up
tracks in its database by their relative path. Only required if analysing
tracks - the LMS plugin will send this path to this service when obtaining
similar tracks.
* `paths.tmp` When analysing music, this script will create a temporary folder
to hold separate CUE file tracks. The path passed here needs to be writable.
This config item is only used for analysis.
* `lmsdb` During analysis, this script will also analyse individual CUE tracks.
To do this it needs access to the LMS database file to know the position of each
track, etc. This config item should hole the path to the LMS database file. This
is only required for analysis, and only if you have CUE files. `ffmpeg` is
required to split tracks.
* `normalize.artist` List of strings to split artist names, e.g. "A ft. B"
becomes "A" (periods are automatically removed). This is then used to aid
filtering of tracks - i.e. to prevent artists from being repeated in a mix.
* `normalize.album` List of strings to remove from album names. This is then
used to aid filtering of tracks - i.e. to prevent albums from being repeated in
a mix.
* `normalize.title` List of strings to remove from titles. This is then
used to aid filtering of tracks - i.e. to prevent duplicate tracks in the mix.
* `port` This is the port number the similarity server is accessible on.
* `host` IP address on which the similarity server will listen on. Use `0.0.0.0`
to listen on all interfaces on your network.
* `threads` Number of threads to use during analysis phase. This controls how
many calls to `ffmpeg` are made concurrently, and how many concurrent tracks
Musly and Essentia are asked to analyse. Defaults to CPU count, if not set.


## Ignoring artists, albums, etc.

To mark certain items as 'ignored' (i.e. so that they are not added to mixes),
create a text file where each line contains the unique path, e.g.:

```
AC-DC/Power Up/
The Police/
```

Then call:

```
./scripts/update-db.py --db music-similarity.db --ignore ignore.txt
```

This sets the `ignore` column to 1 for all items whose file starts with one of
the listed lines.

Setting a track's `ignore` to `1` will exclude tracks from being added to
mixes - but if they are already in the queue, then they can still be used as
seed tracks.


## Copying data from musly-server and essentia-analyzer

If you have previous results from [musly-server](https://github.com/CDrummond/musly-server)
and [essentia-analyzer](https://github.com/CDrummond/essentia-analyzer) then you
can use `scripts/merge-musly-essentia-dbs.py` to merge the contents of their DBs into a
single DB required for music-similarity.


## Credits

`lib/musly.py` (which is used as a python interface to the Musly library) is
taken, and modified, from [Musly Integration for the Logitech Media Server](https://www.nexus0.net/pub/sw/lmsmusly)

The Essentia binary is taken from Roland0's [LMS Essentia Integration](https://www.nexus0.net/pub/sw/lmsessentia/)
