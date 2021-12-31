Linux
=====

- Install Python3 with package manager (e.g. apt or yum)
- Install dependencies:
  a. via package manager, e.g.:
    Ubuntu/Debian: sudo apt install python3-flask python3-numpy python3-requests python3-scipy python3-mutagen
    RedHat/Fedora: sudo yum install python3-flask python3-numpy python3-requests python3-scipy python3-mutagen
  b. via pip:
    pip install -r requirements.txt
- Edit config.json to contain correct paths


Windows
=======

- Install Python3
- Add location of python.exe to PATH
- Add location of pip (usually located in scripts sub-folder of python install) to PATH
- pip install -r requirements.txt
- Edit config.json to contain correct paths
