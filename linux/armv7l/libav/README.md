32-bit ARM build of libmusly, built on Raspbian Buster. This version is linked
against libav/ffmpeg libraries - and so will allow analysis of music on a Pi.


```
git clone https://github.com/CDrummond/musly.git
mkdir build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
```
