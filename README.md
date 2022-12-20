# VideoMerge
Version 1.0.2

![Download](https://github.com/kanehekili/VideoMerge/releases/download/1.0.2/videomerge1.0.2.tar)

UI Tool to merge different videos using ffmpeg
Supports the (fast) merge of homogenius streams as well as (slower) reencoding different file formats. 

## Features
VideoMerge tends to have a very simple interface, It detects the best way to concat mp2,mp4,mkv,webm and more containers into one video. 

![Screenshot](https://github.com/kanehekili/VideoMerge/blob/main/Merge1.png)

Using settings (the cog icon), reencoding can be forced (takes longer) and the rotational infos may be ignored. Used as fallback, if the "automatic" merge doesn't deliver the results expected.  

Different rotated videos will be made "homogenious", see the limitations for more infos. 

### Prerequisites
* python3
* ffmpeg
* python3-pyqt5 on Debian and derivatives

#### Set GTK Theme for this QT application
If you are running a DE with GTK/Gnome (as opposed to LXQT or KDE) you need to tweak your system:
(Arch users may have to install qt5-styleplugins from AUR)

`sudo nano /etc/environment`

add the following line:

`QT_QPA_PLATFORMTHEME=gtk2`

and logout/login (or reboot)


## Limitations
Currently VideoMerge will not merge Portrait and Landscape Video - use the settings to turn rotational recognition off. 
On reencoding, all videos needs to have the same resolution, size and framespeed (fps). Currently the first video in the list will be the "reference" for all videos in the list. 

## Issues
Merging videos is complex, since there are many variations. If you encounter a problem, post parts of the videos to a website where I can download them. 

## Installation

### How to install with a terminal
* Install dependencies (see prerequisites)
* Download the videocut*.tar from the download link (see above)
* Extract it to a location that suits you.
* Open a terminal to execute the install.sh file inside the folder with sudo like `sudo ./install.sh`
* The app will be installed in /opt/videomerge with a link to /usr/bin. 
* The app should be appear in a menu or "Actvities"
* In the terminal can be started via `videomerge`
* python qt5 and ffmpeg are required
* you may now remove that download directory.
* logs can be found in the user home ".config/VideoMerge" folder


### Arch Linux
 TODO

### Ubuntu and Debian
 TODO

## Changes
20.12.2022
* Path fixes

18.12.2022
* Rotational recognition 

10.12.2022
* Initial release







