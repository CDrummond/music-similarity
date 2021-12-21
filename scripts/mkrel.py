#!/usr/bin/env python3

#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021 Craig Drummond <craig.p.drummond@gmail.com>
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


TOP_LEVEL_ITEMS = ["ChangeLog", "config.json", "LICENSE", "%s.py" % APP_NAME, "README.md", "requirements.txt", "lib", "scripts", "docs"]
def createOtherZip(config, others, name):
    if config is not None:
        os.rename("%s/config.json" % APP_NAME, "%s/config-orig.json" % APP_NAME)
        os.rename("%s/%s/config.json" % (APP_NAME, config), "%s/config.json" % APP_NAME)
    cmd=["zip", "-r", "%s/%s-%s-%s.zip" % (APP_NAME, APP_NAME, name, version)]
    for f in TOP_LEVEL_ITEMS:
        cmd.append("%s/%s" % (APP_NAME, f))
    for other in others:
        cmd.append("%s/%s" % (APP_NAME, other))
    subprocess.call(cmd, shell=False)
    if config is not None:
        os.rename("%s/config.json" % APP_NAME, "%s/%s/config.json" % (APP_NAME, config))
        os.rename("%s/config-orig.json" % APP_NAME, "%s/config.json" % APP_NAME)


def createZip(version):
    info("Creating ZIPs")
    if os.path.exists("lib/__pycache__"):
        shutil.rmtree("lib/__pycache__")
    os.chdir('..')
    cmd=["zip", "-r", "%s/%s-all-%s.zip" % (APP_NAME, APP_NAME, version)]
    for f in TOP_LEVEL_ITEMS:
        cmd.append("%s/%s" % (APP_NAME, f))
    for f in ["essentia", "linux"]:
        cmd.append("%s/%s" % (APP_NAME, f))
    for f in ["mingw32", "mingw64", "config.json"]:
        cmd.append("%s/windows/%s" % (APP_NAME, f))
    subprocess.call(cmd, shell=False)
    createOtherZip("linux/armv7l", ["linux/armv7l/libmusly.so", "linux/%s.service" % APP_NAME], "pi")
    createOtherZip("linux/x86-64", ["linux/x86-64/libmusly.so", "linux/%s.service" % APP_NAME, "linux/x86-64/essentia_streaming_extractor_music", "essentia"], "linux-x86-64")
    createOtherZip("windows", ["windows/mingw32/libmusly.dll", "windows/mingw32/libgcc_s_dw2-1.dll", "windows/mingw32/libstdc++-6.dll", "windows/mingw64/libmusly.dll", "windows/mingw64/libgcc_s_seh-1.dll", "windows/mingw64/libstdc++-6.dll", "windows/ffmpeg.exe", "windows/ffprobe.exe", "windows/ffmpeg-LICENSE.txt", "windows/streaming_extractor_music.exe"], "windows")
    os.chdir(APP_NAME)


version=sys.argv[1]
if version!="test" and not version.startswith("alpha") and not version.startswith("beta"):
    checkVersion(version)
    checkVersionExists(version)
    updateVersion(version)

createZip(version)

if version!="test":
    resetVersion();
