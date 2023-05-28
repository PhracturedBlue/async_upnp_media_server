# Media Server
A UPnp/DLNA media server written using async python.

Based on the HomeAssistant DLNA module: async_upnp_client [https://github.com/StevenLooman/async_upnp_client]
and https://github.com/shaolo1/VideoServer.git

This is currently an audio-only media server that has the scpecific capability to extract and serve audio
from video files (i.e. clicking a video file will only transmit the 1st audio track).  It is meant more as a
demonstration of capabilities than a production-ready media server.

Note that as of 2023-05-28, there are outstanding patches against async_upnp_client to support server requirements.
Instead use this branch with the integrated patches: https://github.com/PhracturedBlue/async_upnp_client/tree/server

## To Install
pip install -r requirements.txt

Download ffmpeg and ffprobe binaries into the base directory: https://ffmpeg.org/download.html

## Running
python3 server.py --host <host ip address> --media <space-separated-paths to media directories to host>

## Development
pip install pylint mypy

Run:
  pylint server.py media_server
  mypy --disallow-untyped-defs server.py media_server
