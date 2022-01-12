Musly
=====

64-bit DLLs build with MinGW 64-bit

It is not necessary to rebuild this library, but for those interested these are
the required steps:

Build Eigen 3.4.0
```
    mkdir build
    cd build
    cmake .. -G "MinGW Makefiles" -DCMAKE_INSTALL_PREFIX=c:\Musly
    mingw32-make install
```

Build Musly
```
    mkdir build
    cd build
    cmake .. -G "MinGW Makefiles" -DCMAKE_INSTALL_PREFIX=c:\Musly -DUSE_LIBAV=OFF -DCMAKE_BUILD_TYPE=Release
    mingw32-make
```

To save building ffmpeg libraries for windows, this version of musly will call
ffprobe to detect track duration and call ffmpeg to decode tracks

ffmpeg and ffprobe executables required, and must be in path.
- https://github.com/BtbN/FFmpeg-Builds/releases
- ffmpeg-N-XXXXXX-xxxxxxxxxxx-win64-gpl.zip

64-bit Python *must* be used for this Windows build.
