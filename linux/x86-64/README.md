Config
======

The example config is intended for usage on a Linux machine for analysis and API
server.

`paths.db` should be updated to contain the location where music-similarity's
database and jukebox files can be saved.

`paths.local` should point the location of music files to be analysed.

  
Essentia
========

Pre-built verison of Essentia etractor that is compiled agains GAIA/SVM. This is
taken from Roland0's [LMS Essentia Integration](https://www.nexus0.net/pub/sw/lmsessentia/)

This verison of Essentia allows highlevel (e.g. danaceability, aggresivness, etc)
attributes to be analysed.


Musly
=====

x86-64 Linux build of libmulsy, built on Fedora

It is not necessary to rebuild this library, but for those interested these are
the required steps:

```
    sudo yum install cmake ffmpeg-devel eigen3-devel
    git clone https://github.com/CDrummond/musly.git
    cd musly
    mkdir build
    cd build
    cmake .. -DLIBAV_INCLUDE_DIR=/usr/include/ffmpeg -DCMAKE_BUILD_TYPE=Release
```


Bliss
=====

x86-64 Linux build of bliss-analyse, built on Ubuntu

It is not necessary to rebuild this app, but for those interested this is
documented on its github page https://github.com/CDrummond/bliss-analyse

