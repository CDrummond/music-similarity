To install as a systemd service:

1. Edit `music-similarity.service` to ensure paths, etc, are correct
2. Copy `music-similarity.service` to `/etc/systemd/system`
3. `sudo systemctl daemon-reload`
4. `sudo systemcrl enable music-similarity`
5. `sudo systemctl start music-similarity`
