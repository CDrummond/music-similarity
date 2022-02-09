# Other Configuration Items

The main README.md details the basic config items, however more are supported,
and these are detailed below:


Bliss
-----

```
{
 "bliss":{
  "enabled":true,
  "analyser":"linux/x86-64/bliss-analyse"
 }
}
```

* `bliss.enabled` should be set to true if tracks should be analysed with bliss.
This defaults to true for Linux and macOS when analysing, and to true for API if
files have been analysed with Musly.
* `bliss.analyser` should contain the path to the Bliss analyser extractor -path
is relative to `music-similarity.py` Only required if analyising tracks. By
default music-similarity will attempt to set this automatically.


Musly
-----
```
{
 "musly":{
  "enabled":true,
  "lib":"lib/x86-64/fedora/libmusly.so",
  "styletracks":1000,
  "styletracksmethod":"genres",
  "extractlen":120,
  "extractstart":-210
 }
}
```
* `musly.enabled` should be set to true if Musly is to be used for similarity.
This defaults to true for Windows when analysing, and to true for API if files
have been analysed with Musly.
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
queried for how many tracks each genre has and tracks are chosen for each of
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


Essentia
--------

Apart from `enabled`, `extractor`, and `highlevel` the following config items
are usually supplied via the LMS plugin when it asks for mixes.


```
{
 "essentia":{
  "enabled":true,
  "extractor":"linux/x86-64/essentia_streaming_extractor_music",
  "highlevel":false,
  "filterattrib_count":4,
  "filterattrib_lim":0.2,
  "filterattrib_cand":0.4,
  "attrmix_yes":0.6,
  "attrmix_no":0.4
 },
 "paths":{
  "cache":"/path/to/store/cache"
 }
}
```

* `essentia.enabled` should be set to true if Essentia is to be used for
filtering, or similairty. This defaults to true if when analysing if the 
extractor is found, and to true for API if files have been analysed with
Essentia.
* `essentia.extractor` should contain the path to the Essentia extractor - path
is relative to `music-similarity.py` Only required if analyising tracks. By
default music-similarity will attempt to set this automatically.
* `essentia.highlevel` Specify whether to support high-level Essentia analysis
features. This defaults to true for Linux only.
* `essentia.filterattrib_count` Configures nubmer of attributes to use.
* `essentia.filterattrib_lim` If filtering on attributes, only attributes that
are less than this, or higher than 1.0-this will be used.
* `essentia.filterattrib_cand` When filtering on attributes, the selected
attributes of the seed need to be less than this, or higher than 1.0-this.
* `essentia.attrmix_yes` When using 'Smart Mixes', 'Yes' attributes need to be
higher than or equal to this.
* `essentia.attrmix_no` When using 'Smart Mixes', 'No' attributes need to be
lower than or equal to this.
* `paths.cache` if set, then the full output of Essentia analysis for each track
will be stored within a GZip compressed JSON file (`<music file>.json.gz`)


CUE Tracks
----------

During analysis, this script will also analyse individual CUE tracks. To do this
it needs access to the LMS database file to know the position of each track,
etc. as well as the path to your music files as LMS sees them.

```
{
 "paths":{
  "lms":"/media/Music/",
  "tmp":"/tmp/"
 },
 "lmsdb":"/path/to/lms/Cache/library.db"
}
```

* `paths.lms` should be the path where LMS accesses your music files.
* `lmsdb` should hold the path to the LMS database file. This is only required
for analysis, and only if you have CUE files. `ffmpeg` is required to split
tracks.
* `paths.tmp` When analysing music, this script will create a temporary folder
to hold any split CUE file tracks. The path set here needs to be writable. If
left unset, the default, then it will be set to the system's default temporary
folder path. This config item is only used for analysis.


Normalizing Strings
-------------------

```
{
 "normalize":{
  "artist":["feet", "ft", "featuring"],
  "album":["deluxe edition", "remastered"],
  "title"["demo", "radio edit"]
 }
}
```

* `normalize.artist` List of strings to split artist names, e.g. "A ft. B"
becomes "A" (periods are automatically removed). This is then used to aid
filtering of tracks - i.e. to prevent artists from being repeated in a mix.
* `normalize.album` List of strings to remove from album names. This is then
used to aid filtering of tracks - i.e. to prevent albums from being repeated in
a mix.
* `normalize.title` List of strings to remove from titles. This is then
used to aid filtering of tracks - i.e. to prevent duplicate tracks in the mix.


Genre grouping
--------------

Genres can configured via the `genres` section of `config.json`, using the
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

*NOTE* Genre groups can now be configured directly in the [LMS Music Similarity Plugin](https://github.com/CDrummond/lms-musicsimilarity),
therefore there is no need to add these to `config.json`, and this section
is no longer required.


Misc
----

```
{
 "port":11000,
 "host":"0.0.0.0",
 "threads":8,
 "minduration":30,
 "maxduration":1800,
 "excludegenres":[
   "Podcast", "Audiobook"
 ],
 "simalgo":"musly",
 "mixed":{
  "essentia":33,
  "bliss":33,
  "musly:34
 }
}
```

* `port` This is the port number the similarity server is accessible on.
* `host` IP address on which the similarity server will listen on. Use `0.0.0.0`
to listen on all interfaces on your network.
* `threads` Number of threads to use during analysis phase. This controls how
many calls to `ffmpeg` are made concurrently, and how many concurrent tracks
Musly and Essentia are asked to analyse. Defaults to CPU count, if not set.
* `minduration` Only analyse tracks with duration >= this.
* `maxduration` Only analyse tracks with duration <= this.
* `excludegenres` List of genres that should be excluded from analysis. Any
tracks that have a genre from this list will not be analysed.
* `simalgo` Which method to use for similarity score; musly, essentia, bliss, or
mixed. This defaults to `bliss` for Linux, and `musly` for Mac and Windows. This
only affects the API usage, analysis will use all enabled types.
* `mixed.essentia`, `mixed.bliss`, `mixed.musly` are used to define the
percentage each of these in the similarity score. Only used if `simalgo` is set
to `mixed`.
