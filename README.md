# VideoMerge
Version 1.0.1

![Download](https://github.com/kanehekili/VideoMerge/releases/download/1.0.1/videomerge1.0.1.tar)

UI Tool to merge different videos using ffmpeg
Supports the (fast) merge of homogenius streams as well as (slower) reencoding different file formats. 

##Features
VideoMerge tends to have a very simple interface, It detects the best way to concat mp2,mp4,mkv,webm and more containers into one video. 

![Screenshot](https://github.com/kanehekili/VideoMerge/blob/main/Merge.png)

Different rotated videos will be made "homogenious", see the limitations for more infos. 


##Limitations
Currently VideoMerge will not merge Portrait and Landscape Video - it simply makes no sense. 
On reencoding, all videos needs to have the same resolution, size and framespeed (fps). Curerntly the first video in the list will be the "reference" for all videos in the list. 

##Issues
Merging videos is complex, since there are many variations. If you encounter a problem, post parts of the videos to a website where I can download them. 

##Installation
todo

#Arch Linux
get it from AUR

#Ubuntu and Debian
ppa 

##Changes
10.12.2022
* Initial release

18.10.2022
* Rotational recognition 






