# Similarity API

Obtain mix of tracks similar to seed tracks.

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
repeated. This does not apply to 'Various Artist' albums. This is also not a
hard-limit, as if there are too few candidates then repeats can happen.

`previous` may be used to list tracks currently in the play queue. This
parameter, like `track`, may be repeated multiple times. These tracks will be
used to filter chosen tracks on artist, or album, to prevent duplicates.

`maxsim` (range 0..100) can be used to set the maximum similarity factor. A
factor of 0 would imply the track is identical, 100 completely different. 75 is
the default value.

`shuffle` if set to `1` will cause extra tracks to be located, this list
shuffled, and then the desired `count` tracks taken from this shuffled list.

The API will use Musly and/or Essentia to get the similarity between all tracks
and each seed track, and sort this by similarity (most similar first). The
Essentia attributes may then used to filter out some tracks (e.g. by checking
BPM, etc.). Initially the API will ignore tracks from the same artist or album
of the seed tracks (and any previous in the list, any albums from the (e.g.) 25
`previous` tracks, or albums from the last (e.g.) 15 `previous` tracks). If,
because of this filtering, there are less than the requested amount then the
highest similarity tracks from the filtered-out lists are chosen.

Metadata for tracks is stored in an SQLite database, this has an `ignore` column
which if set to `1` will cause the API to not use this track if it is returned
as a similar track by Musly. In this way you can exclude specific tracks from
being added to mixes - but if they are already in the queue, then they can still
be used as seed tracks.

This API is intended to be used by [LMS Music Similarity Plugin](https://github.com/CDrummond/lms-musicsimilarity)
when creating mixes via `Don't Stop The Music`


# Attribute Mix API

Obtain a mix of tracks that match selected attribute filter.

```
http://HOST:11000/api/attrmix?minduration=30&maxduration=600&minbpm=50&maxbpm=100&minloudness=40&maxloudness=100&norepart=15&norepalb=25&filterxmas=1&danceable=10&aggressive=10&electronic=10&acoustic=10&happy=10&party=10&relaxed=10&sad=10&dark=10&tonal=10&voice=10&genre=Rock&count=50
```

`minduration` and `maxduration` specify the min and max duraiton tracks can be.

`minbpm` and `maxbpm` specify a BPM range.

`minloudness` and `maxloudness` specify a loudness range, 0..100

`norepart` specifies the number of tracks where an artist should not be
repeated. This is not a hard-limit, as if there are too few candidates then
repeats can happen.

`norepalb` specifies the number of tracks where an album should not be
repeated. This does not apply to 'Various Artist' albums. This is also not a
hard-limit, as if there are too few candidates then repeats can happen.

`filterxmas=1` causes tracks with 'Christmas' or 'Xmas' in their
genres will be excluded - unless it is December.

`danceable`, `aggressive`, `electronic`, `acoustic`, `happy`, `party`,
`relaxed`, `sad`, `dark`, `tonal`, `voice` are the Essentia highlevel attributes
that can be filtered on. If one of these is specified with a value less than 50,
then only tracs where this attribute is also less than 50 will be accepted.
Likewise if a value greater than 50 is specified only tracks where this is also
greater than 50 will be used. This is because these Essentia atttributes are how
confident Essentia is that a track is of this type. e.g. 'danceable=85' implies
Essentia is 85% confident this is a danceable track - 'danceable=25' implies
only 25 confidence, so in effect Essentia is confident this is *not* a danceable
track. Range is 0..100

For most parameters, if not set or 0 is passed then no filtering will be applied
using that attribute. For Essentia highlevel attributes, if 50 is passed it is
also treated as a do not filter on case.

Tracks are chosen from the DB in a random order, and the first `count` of these
is returned. Less tracks than `count` may be returned if filtering exclused too
many. In effect `count` is a maximum count setting.

This API is intended to be used by [LMS Music Similarity Plugin](https://github.com/CDrummond/lms-musicsimilarity)
when obtaining 'Smart' mixes.


# HTTP Post

Alternatively, the APIs may be accessed via a HTTP POST call. To do this, the
params of the calls are passed as a JSON object. eg.

```
{
 "track":["/path/trackA.mp3", "/path/trackB.mp3"],
 "filtergenre":1,
 "count":10
}
```

This is the method that is used by the LMS plugin.
