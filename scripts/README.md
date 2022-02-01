# Ignoring artists, albums, etc.

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


# Copying data from musly-server and essentia-analyzer

If you have previous results from [musly-server](https://github.com/CDrummond/musly-server)
and [essentia-analyzer](https://github.com/CDrummond/essentia-analyzer) then you
can use `scripts/merge-musly-essentia-dbs.py` to merge the contents of their DBs into a
single DB required for music-similarity.


# Release

`mkrel.py` is used to create release ZIP files.

Following extra files, not checked into github, are required:
- windows/ffmpeg.exe - from https://github.com/BtbN/FFmpeg-Builds/releases
- windows/ffprobe.exe - from https://github.com/BtbN/FFmpeg-Builds/releases
- windows/streaming_extractor_music.exe - from https://github.com/AF-1/sobras/tree/main/lms-music-similarity_on_macos/binaries
- mac/streaming_extractor_music - from https://github.com/AF-1/sobras/tree/main/lms-music-similarity_on_macos/binaries
- essentia/models-beta5/ - from https://github.com/AF-1/sobras/tree/main/lms-music-similarity_on_macos/binaries

