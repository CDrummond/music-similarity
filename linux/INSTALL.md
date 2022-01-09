Installation
============

- Install Python3 with package manager (e.g. apt or yum)

- Install python dependencies:
  a. via package manager, e.g.:
    Ubuntu/Debian:
      `sudo apt install python3-flask python3-numpy python3-requests python3-scipy python3-mutagen`
    RedHat/Fedora:
      `sudo yum install python3-flask python3-numpy python3-requests python3-scipy python3-mutagen`
  b. via pip:
    `pip install -r requirements.txt`

- For Intel/AMD Linux installs ffmpeg libraries are required as the Musly
  library links to these. The Musly build for Raspberry Pi systems is designed
  for serving the similarity HTTP API only, and not analysis, hence is not
  linked to ffmpeg and therefore these libraries are not required. For ffmpeg
  you can either:

  a. Install complete ffmpeg package (e.g. `sudo apt install ffmpeg`), or
  b. Install libavcodec, libavformat, and libavutil libraries - the names of
     of these may differ on your system.

- Edit config.json to contain correct paths
