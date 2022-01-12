Config
======

The example config is intended for usage on a Pi that will be used for the
similarity API server, and not for analysis.

`paths.db` should be updated to contain the location where music-similarity's
database and jukebox files can be found.


Musly
=====

32-bit ARM build of libmusly, built on Raspbian Buster. This version has NOT
been linked against libav/ffmpeg libraries - and so will NOT allow analysis of
music.

It is not necessary to rebuild this library, but for those interested these are
the required steps:

```
    sudo apt install cmake libeigen3-dev
    git clone https://github.com/CDrummond/musly.git
    cd musly
    mkdir build
    cd build
    cmake .. -DCMAKE_BUILD_TYPE=Release -DUSE_LIBAV=OFF
```
