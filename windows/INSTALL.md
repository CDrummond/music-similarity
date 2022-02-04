Installation
============

- Install Python3

- Add location of `python.exe` to PATH - this can be achieved via the Windows
  control panel

- Add location of `pip` (usually located in scripts sub-folder of python
  install) to PATH

- Open a new Windows command console (cmd)

- Install python dependencies:

  `pip install -r requirements.txt`

- Edit `config.json` to contain correct paths

- Install ffmpeg:

  a) Download latest from `https://github.com/BtbN/FFmpeg-Builds/releases`, or
     `https://github.com/CDrummond/music-similarity-extra/raw/master/ffmpeg.zip`

  b) Place ffmpeg.exe and ffprope.exe into `windows` folder

- If you wish to analyze with Essentia:

  a) Download `http://ftp.acousticbrainz.org/pub/acousticbrainz/essentia-extractor-v2.1_beta2-1-ge3940c0-win-i686.zip`

  b) Place streaming_extractor_music.exe into `windows` folder

