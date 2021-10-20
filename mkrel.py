#!/usr/bin/env python3

#
# Analyse files with Essentia and Musly, and provide an API to retrieve similar tracks
#
# Copyright (c) 2021 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import hashlib
import os
import re
import requests
import shutil
import subprocess
import sys


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


def createZip(version):
    info("Creating ZIPs")
    os.chdir('..')
    cmd=["zip", "-r", "%s/%s-all-%s.zip" % (APP_NAME, APP_NAME, version), "%s/essentia" % APP_NAME]
    for f in ["ChangeLog", "config.json", "LICENSE", "%s.py" % APP_NAME, "%s.service" % APP_NAME, "README.md", "scripts"]:
        cmd.append("%s/%s" % (APP_NAME, f))
    for e in os.listdir("%s/lib" % APP_NAME):
        if e.endswith(".py") or e in ["armv7l", "x86-64"]:
            cmd.append("%s/lib/%s" % (APP_NAME, e))
    subprocess.call(cmd, shell=False)
    os.rename("%s/config.json" % APP_NAME, "%s/config-orig.json" % APP_NAME)
    os.rename("%s/config-pi.json" % APP_NAME, "%s/config.json" % APP_NAME)
    cmd=["zip", "-r", "%s/%s-pi-%s.zip" % (APP_NAME, APP_NAME, version)]
    for f in ["ChangeLog", "config.json", "LICENSE", "%s.py" % APP_NAME, "%s.service" % APP_NAME, "README.md"]:
        cmd.append("%s/%s" % (APP_NAME, f))
    for e in os.listdir("%s/lib" % APP_NAME):
        if e.endswith(".py"):
            cmd.append("%s/lib/%s" % (APP_NAME, e))
    cmd.append("%s/lib/armv7l/raspbian-buster/libmusly.so" % APP_NAME)
    subprocess.call(cmd, shell=False)
    os.rename("%s/config.json" % APP_NAME, "%s/config-pi.json" % APP_NAME)
    os.rename("%s/config-orig.json" % APP_NAME, "%s/config.json" % APP_NAME)
    os.chdir(APP_NAME)


version=sys.argv[1]
if version!="test":
    checkVersion(version)
    checkVersionExists(version)
    updateVersion(version)

createZip(version)

if version!="test":
    resetVersion();
