Installation
============

- Install Python3

- Install homebrew:
  /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"

- Use Homebrew to install ffmpeg:
  brew install ffmpeg

- Remove Apple's quarantine flag from the binary files
  sudo xattr -r -d com.apple.quarantine mac/x86-64/libmusly.dylib
  sudo xattr -r -d com.apple.quarantine mac/streaming_extractor_music

- `pip install -r requirements.txt`

- Edit config.json to contain correct paths
