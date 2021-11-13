# spotifyd-server

A simple website to restart and update [spotifyd](https://github.com/Spotifyd/spotifyd).
Convenient restarting (and cache removal)is required if multiple Spotify-Accounts want to 
vonnect to spotifyd.

  - Made for Raspberry Pi 1.
  - Not made well, requires some tweaking if others want to use this code.
 
 ## Setup : Hardware
 
  - Raspberry Pi 1 with USB sound card
 
## Setup: Software

preparatory commands:
``` bash
mkdir ~/.spotifyd_cache
cd ~ && git clone https://github.com/TheBigFatTony/spotifyd-server.git

sudo apt install git python3-dev python3-pip python3-requests python3-wget
sudo pip3 install uwsgi
```


allow user to run reboot/shutdown:
``` bash
sudo visudo
# add this line to the end:
# pi raspberrypi =NOPASSWD: /usr/bin/systemctl poweroff,/usr/bin/systemctl halt,/usr/bin/systemctl reboot
```



~/.asoundrc:  (get dev id using aplay-l)
```
pcm.!default {
    type hw
    card 1
}

ctl.!default {
    type hw           
    card 1
}
```



  - ~/.config/spotifyd/spotifyd.conf
```
[global]
device_name = "spotipy"
initial_volume = "90"
bitrate = 160

backend = "alsa"
device = "plughw:1,0"

cache_path = "/home/pi/.spotifyd_cache"
device_type = "speaker"
```



  - ~/.config/systemd/user/spotifyd.service
```
[Unit]
Description=A spotify playing daemon
Documentation=https://github.com/Spotifyd/spotifyd
Wants=sound.target
After=sound.target
Wants=network-online.target
After=network-online.target

[Service]
ExecStart=/home/pi/spotifyd --no-daemon --config-path=/home/pi/.config/spotifyd/spotifyd.conf
Restart=always
RestartSec=12

[Install]
WantedBy=default.target
```


  - ~/.config/systemd/user/spotifyd_server.service
```
[Unit]
Description=Spotifyd-Website
Documentation=https://github.com/TheBigFatTony/spotifyd-server
Wants=network-online.target
After=network-online.target

[Service]
ExecStart=uwsgi --http :9090 --wsgi-file /home/pi/spotifyd-server/SpotifydServer.py
Restart=always
RestartSec=12

[Install]
WantedBy=default.target
```


useful commands:
```
# reload systemd
sudo systemctl daemon-reload

# enable a service
systemctl --user enable {service}.service

# restart a service
systemctl --user restart {service}.service

# see logs of a service
journalctl --user-unit {service}.service -f
```