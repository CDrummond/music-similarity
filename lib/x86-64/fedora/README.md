git clone https://github.com/CDrummond/musly.git
sudo yum install cmake install ffmpeg-devel
mkdir build
cd build
cmake .. -DLIBAV_INCLUDE_DIR=/usr/include/ffmpeg -DCMAKE_BUILD_TYPE=Release
