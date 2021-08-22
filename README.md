# Music Similarity

Simple python3 API server to create a mix of music tracks for LMS.

## Musly

This service uses the [Musly audio music similarity library](https://github.com/CDrummond/musly)
This library needs to be compiled, and `config.json` (from this API project)
updated to store the location of this library. This repo contains pre-built
built versions for:

1. Fedora 64-bit
2. Raspbian Buster 32-bit

**macOS**

Instructions, and binaries, for Musly on macOS can be found [here](https://github.com/AF-1/sobras/tree/main/lms-music-similarity_on_macos)


## Essentia

The Essentia binaries and models are only required for anlysing tracks, and are
not required for the similarity API. Therefore, if analysis is performed on one
machine and API served on another (e.g. a Raspberry Pi) the contents of the
`essentia` folder are not required on the API machine.


## Analysing Tracks

Before starting the server your music needs to be analysed with Essentia and
Musly. This is accomplished via:

```
./music-similarity.py --analyse /path/to/music/folder
```

This can take about 20hrs to process 25k tracks. The process analyses tracks
with Essentia, analyuses with Musly, adds them to Musly, intialises Musly's
'jukebox' style with 1000 random tracks, and extracts certain tags. If re-run
new tracks will be added, and old (non-existant) will be removed. Pass
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
the API this script is designed for. To test if the analysis is correct you can
run the script in test mode:

```
./music-similarity.py --log-level INFO --test
```

This will query Musly for the 50 most similar tracks to the 1st analysed track.
It then checks that there are different similarities, and if not an error
message is shown.

If this script states that there is an error you can try simply removing the
jukebox file and re-runnnig this script - it will recreate the jukebox with
random tracks. If this keeps failing it might be better to adjust the
`styletracks` config item, delete the jukebox, and test again.

Alternatively, you can have this script run until it receives valid similarities
from Musly. In this mode the script will test the jukebox, remove it if the test
fails, recreate jukebox, test the jukebox, ...

```
./music-similarity.py --log-level INFO --test --repeat
```

## Similarity API 

The API server can be installed as a Systemd service, or started manually:

```
./music-similarity.py
```

...when the service starts, it will confirm that the number of tracks in its
SQLite database is the same as the number in the 'Musly jukebox'. If the
number differs, the jukebox is recreated.

Only 1 API is currently supported:

```
http://HOST:11000/api/similar?track=/path/of/track&track=/path/of/another/track&count=10&filtergenre=1&min=30&max=600&norepart=15&norepalb=25&filterxmas=1
```
...this will get 10 similar tracks to those supplied.

If `filtergenre=1` is supplied then only tracks whose genre matches a
pre-configured set of genres (mapped from seed tracks) will be used. e.g. if
`["Heavy Metal", "Metal", "Power Metal"]` is defined in the config, and a seed
tack's genre has `Metal` then only tracks with one of these 3 genres will be
considered.

If `filterxmas=1` is supplied, then tracks with 'Christmas' or 'Xmas' in their
genres will be excluded - unless it is December.

`min` and `max` can be used to set the minimum, and maximum, duration (in
seconds) of tracks to be considered.

`norepart` specifies the number of tracks where an artist should not be
repeated. This is not a hard-limit, as if there are too few candidates then
repeats can happen.

`norepalb` specifies the number of tracks where an album should not be
repeated. This does not aply to 'Various Artist' albums. This is also not a
hard-limit, as if there are too few candidates then repeats can happen.

`previous` may be used to list tracks currently in the play queue. This
parameter, like `track`, may be repeated multiple times. These tracks will be
used to filter chosen tracks on artist, or album, to prevent duplicates.

`maxsim` (range 0..100) can be used to set the maximum similarity factor. A
factor of 0 would imply the track is identical, 100 completely different. 75 is
the default value.

`shuffle` if set to `1` will cause extra tracks to be located, this list
shuffled, and then the desired `count` tracks taken from this shuffled list.

The API will use Musly to get the similarity between all tracks and each seed
track, and sort this by similarity (most similar first). The Essentia attributes
are then used to filter out some tracks (e.g. by checking BPM, etc.). Initially
the API will ignore tracks from the same artist or album of the seed tracks (and
any previous in the list, any albums from the (e.g.) 25 `previous` tracks, or
albums from the last (e.g.) 15 `previous` tracks). If, because of this
filtering, there are less than the requested amount then the highest similarity
tracks from the filtered-out lists are chosen.

Metadata for tracks is stored in an SQLite database, this has an `ignore` column
which if set to `1` will cause the API to not use this track if it is returned
as a similar track by Musly. In this way you can exclude specific tracks from
being added to mixes - but if they are already in the queue, then they can still
be used as seed tracks.

This API is intended to be used by [LMS Music Similarity Plugin](https://github.com/CDrummond/lms-musicsimilarity)

Genres are configured via the `genres` section of `config.json`, using the
following syntax:

```
{
 "genres:[
  [ "Rock", "Hard Rock", "Metal"],
  [ "Pop", "Dance", "R&B"]
 ]
}
```

If a seed track has `Hard Rock` as its genre, then only tracks with `Rock`,
`Hard Rock`, or `Metal` will be allowed. If a seed track has a genre that is not
listed here then any track returned by Musly, that does not contain any genre
listed here, will be considered acceptable. Therefore, if seed is `Pop` then
a `Hard Rock` track would not be considered.

### HTTP Post

Alternatively, the API may be accessed via a HTTP POST call. To do this, the
params of the call are passed as a JSON object. eg.

```
{
 "track":["/path/trackA.mp3", "/path/trackB.mp3"],
 "filtergenre":1,
 "count":10
}
```

This is the method that is used by the LMS plugin.

## Configuration

Configuration is read from a JSON file (default name is `config.json`). This has
the following format:

```
{
 "musly":{
  "lib":"lib/x86-64/fedora/libmusly.so",
  "styletracks":1000,
  "extractstart":-48,
  "extractlen":30
 },
 "essentia":{
  "enabled":true,
  "extractor":"essentia/bin/x86-64/essentia_streaming_extractor_music",
  "weight":0.0
 },
 "paths":{
  "db":"/home/user/.local/share/musly/",
  "local":"/home/Music/",
  "lms":"/media/Music/",
  "tmp":"/tmp/",
  "cache:"",
 },
 "lmsdb":"/path/to/lms/Cache/library.db",
 "genres":[
  ["Alternative Rock", "Classic Rock", "Folk/Rock", "Hard Rock", "Indie Rock", "Punk Rock", "Rock"],
  ["Dance", "Disco", "Hip-Hop", "Pop", "Pop/Folk", "Pop/Rock", "R&B", "Reggae", "Soul", "Trance"],
  ["Gothic Metal", "Heavy Metal", "Power Metal", "Progressive Metal", "Progressive Rock", "Symphonic Metal", "Symphonic Power Metal"]
 ],
 "ignoregenre":["Artist"],
 "normalize":{
  "artist":["feet", "ft", "featuring"],
  "album":["deluxe edition", "remastered"],
  "title"["demo", "radio edit"]
 },
 "port":10000,
 "host":"0.0.0.0",
 "threads":8
}
```

* `musly.lib` should contain the path the musy shared library - path is relative
to `music-similarity.py`
* `musly.styletracks` A  subset of tracks is passed to Musly's `setmusicstyle`
function, by default 1000 random tracks is chosen. This config item can be used
to alter this. Note, however, the larger the number here the longer it takes to
for this call to complete. As a rough guide it takes ~1min per 1000 tracks.
If you change this config item after the jukebox is written you will need to
delete the jukebox file and restart the server.
* `musly.styletracksmethod` configures how tracks are chosen for styletracks. If
set to `genres` (which is the default if not set) then the meta-data db is
queried for how many track each genre has and tracks are chosen for each of
these genres based upon the percentage of tracks in a genre. If set to `albums`
then at least one track from each album is used. If set to aything else then
random tracks are chosen.
* `musly.extractlen` The maximum length in seconds of the file to decode. If zero
or greater than the file length, then the whole file will be decoded. Note,
however, that only a maximum of 5 minutes is used for analysis.
* `musly.extractstart` The starting position in seconds of the excerpt to decode. If
zero, decoding starts at the beginning. If negative, the excerpt is centered in
the file, but starts at -`extractstart` the latest. If positive and
`extractstart`+`extractlen` exceeds the file length, then the excerpt is taken
from the end of the file.
* `essentia.enabled` should be set to true if Essentia is to be used for filtering
* `essentia.extractor` should containt the math to the Essentia extractor - path is
relative to `music-similarity.py`
* `essentia.weight` By default Musly is used for similarity score, and Essentia
is used to filter tracks. However, if you set `essentia.weight` to higher than
0.0 (and less than or equal to 1.0) then Essentia can also be used to score
similarity based upon the Essentia attributes. This value then configures the
percentage give to each meteric. e.g. an `essentia.weight` of 0.4 will cause the
similarity score to be base 60% Musly 40% Essentia.
* `paths.db` should be the path where the SQLite and jukebox files created by
this app can be written.
* `paths.local` should be the path where this script can access your music
files. This can be different to `path.lms` if you are running analysis on a
different machine to where you would run the script as the API server. Thi
script will only store the paths relative to this location - eg.
`paths.local=/home/music/` then `/home/music/A/b.mp3` will be stored as
`A/b.mp3`.
* `paths.lms` should be the path where LMS accesses your music files. The API
server will remove this path from API calls, so that it can look up tracks in
its database by their relative path.
* `paths.tmp` When analysing music, this script will create a temporary folder
to hold separate CUE file tracks. The path passed here needs to be writable.
This config item is only used for analysis.
* `lmsdb` During analysis, this script will also analyse individual CUE tracks.
To do this it needs access to the LMS database file to know the position of each
track, etc. This config item should hole the path to the LMS database file. This
is only required for analysis, and only if you have CUE files. `ffmpeg` is
required to split tracks.
* `genres` This is as described above.
* `ignoregenre` List of artists where genre filtering (excluding christmas)
should be ignored. To apply to all artists, use '*' - e.g. `"ignoregenre":"*"`
* `normalize.artist` List of strings to split artist names, e.g. "A ft. B"
becomes "A" (periods are automatically removed).
* `normalize.album` List of strings to remove from album names.
* `normalize.title` List of strings to remove from titles.
* `port` This is the port number the API is accessible on.
* `host` IP addres on which the API will listen on. Use `0.0.0.0` to listen on
all interfaces on your network.
* `threads` Number of threads to use during analysis phase. This controls how
many calls to `ffmpeg` are made concurrently, and how many concurrent tracks
Musly is asked to analyse. Defaults to CPU count, if not set.


## Ignoring artists, albums, etc.

To mark certains items as 'ignored' (i.e. so that they are not added to mixes),
create a text file where each line contains the unique path, e.g.:

```
AC-DC/Power Up/
The Police/
```

Then call:

```
./update-db.py --db music-similarity.db --ignore ignore.txt
```

This sets the `ignore` column to 1 for all items whose file starts with one of
the listed lines.

Setting a track's `ignore` to `1` will exclude tracks from being added to
mixes - but if they are already in the queue, then they can still be used as
seed tracks.


## Copying data from musly-server and essentia-analyzer

If you have previous results from [musly-server](https://github.com/CDrummond/musly-server)
and [essentia-analyzer](https://github.com/CDrummond/essentia-analyzer) then you
can use `merge-musly-essentia-dbs.py` to merge the contents of their DBs into a
single DB required for music-similarity.


## Credits

`lib/musly.py` (which is used as a python interface to the Musly library) is
taken, and modified, from [Musly Integration for the Logitech Media Server](https://www.nexus0.net/pub/sw/lmsmusly)

The Essentia binary is taken from Roland0's [LMS Essentia Integration](https://www.nexus0.net/pub/sw/lmsessentia/)
