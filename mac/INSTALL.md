Installation
============

- Install **Python3**

- Install **XCode Command Line Tools**: `xcode-select --install`

- Install **homebrew**:
  `/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"`

- Use Homebrew to install **ffmpeg**: `brew install ffmpeg`

- Remove Apple's quarantine flag from the binary files:<br>
  `sudo xattr -r -d com.apple.quarantine mac/x86-64/libmusly.dylib`<br>
  `sudo xattr -r -d com.apple.quarantine mac/streaming_extractor_music`

- Create a **Python3 virtual environment** (change the name if you like) and activate it:<br>
  `python3 -m venv ~/musicsimilarity-pyenv`<br>
  `source ~/musicsimilarity-pyenv/bin/activate`<br>

- Install requited Python modules:<br>
  `pip install -r requirements.txt`<br>
  `pip install cherrypy`

- Edit *config.json* to contain correct paths
