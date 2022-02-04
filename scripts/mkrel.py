#!/usr/bin/env python3

#
# Analyse files with Musly, Essentia, and Bliss, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021-2022 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import hashlib, os, re, requests, shutil, subprocess, sys


APP_NAME = "music-similarity"

def info(s):
    print("INFO: %s" %s)


def error(s):
    print("ERROR: %s" % s)
    exit(-1)


def usage():
    print("Usage: %s <major>.<minor>.<patch>" % sys.argv[0])
    exit(-1)


def checkVersion(version):
    try:
        parts=version.split('.')
        major=int(parts[0])
        minor=int(parts[1])
        patch=int(parts[2])
    except:
        error("Invalid version number")


def releaseUrl(version):
    return "https://github.com/CDrummond/%s/releases/download/%s/%s-%s.zip" % (APP_NAME, version, APP_NAME, version)


def checkVersionExists(version):
    url = releaseUrl(version)
    info("Checking %s" % url)
    request = requests.head(url)
    if request.status_code == 200 or request.status_code == 302:
        error("Version already exists")


def updateVersion(version):
    path = os.path.join('lib', 'version.py')
    os.remove(path)
    with open(path, "w") as f:
        f.write("MUSIC_SIMILARITY_VERSION='%s'\n" % version)


def resetVersion():
    subprocess.call(['git', 'checkout', os.path.join('lib', 'version.py')], shell=False)


TOP_LEVEL_ITEMS = ["ChangeLog", "config.json", "INSTALL.md", "LICENSE", "%s.py" % APP_NAME, "README.md", , "requirements.txt", "docs", "lib", "linux", "mac", "scripts", "windows"]

def createZip(version):
    info("Creating ZIPs")
    if os.path.exists("lib/__pycache__"):
        shutil.rmtree("lib/__pycache__")
    os.chdir('..')
    cmd=["zip", "-r", "%s/%s-%s.zip" % (APP_NAME, APP_NAME, version)]
    for f in TOP_LEVEL_ITEMS:
        cmd.append("%s/%s" % (APP_NAME, f))
    subprocess.call(cmd, shell=False)
    os.chdir(APP_NAME)


version=sys.argv[1]
if version!="test" and not version.startswith("alpha") and not version.startswith("beta"):
    checkVersion(version)
    checkVersionExists(version)
    updateVersion(version)

createZip(version)

if version!="test":
    resetVersion();
