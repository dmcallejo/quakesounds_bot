# quakesounds_bot
Telegram bot to send inline Quake Sounds.

[![Build Status](https://travis-ci.org/dmcallejo/quakesounds_bot.svg?branch=master)](https://travis-ci.org/dmcallejo/quakesounds_bot) [![Docker Automated build](https://img.shields.io/docker/automated/dmcallejo/quakesounds_bot.svg)](https://hub.docker.com/r/dmcallejo/quakesounds_bot/) [![Docker Build Status](https://img.shields.io/docker/build/dmcallejo/quakesounds_bot.svg)](https://hub.docker.com/r/dmcallejo/quakesounds_bot/) [![Docker Pulls](https://img.shields.io/docker/pulls/dmcallejo/quakesounds_bot.svg)](https://hub.docker.com/r/dmcallejo/quakesounds_bot)

All audios must be encoded using ffmpeg with these parameters:
```
ffmpeg -i $INPUT -map_metadata -1 -ac 1 -map 0:a -codec:a libopus -b:a 128k -vbr off -ar 48000 $OUTPUT
```
