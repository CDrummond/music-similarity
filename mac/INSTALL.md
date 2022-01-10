Installation
============

- Install XCode Command Line Tools:

  `xcode-select --install`

- Install homebrew:

  `/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"`

- Use Homebrew to install Python3:

  `brew install python3`

- Use Homebrew to install ffmpeg:

  `brew install ffmpeg`

- Remove Apple's quarantine flag from the binary files:

  `sudo xattr -r -d com.apple.quarantine mac/x86-64/libmusly.dylib && sudo xattr -r -d com.apple.quarantine mac/streaming_extractor_music`

- Create a Python3 virtual environment (change the name if you like) and activate it:

  `python3 -m venv ~/musicsimilarity-pyenv && source ~/musicsimilarity-pyenv/bin/activate`

- Install required Python modules:

  `pip install -r requirements.txt && pip install cherrypy`

- Edit config.json to contain correct paths

- Optional: Run Music Similarity Server as a daemon (in the background): https://github.com/AF-1/sobras/blob/main/lms-music-similarity_on_macos/README.md#running-music-similarity-server-as-a-daemonin-the-background
