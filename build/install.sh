#!/bin/bash
#check if sudo
if [ "$EUID" -ne 0 ] ; then
  echo "Sorry, but you are not root. Use sudo to run"
  exit 1
fi
#copy desktop to /usr/share applications
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
sudo cp $DIR/VideoMerge.desktop /usr/share/applications;
sudo mkdir -p /opt/videomerge;
sudo cp -r $DIR/* /opt/videomerge/;
sudo ln -s /opt/videomerge/VideoMerge.py /usr/bin/videomerge

echo "######################################################################"
echo "#                  Ensure you have installed:                        #"                     
echo "#    debian/ubuntu/mint: python3-pyqt5 ffmpeg                        #"
echo "#    arch &derivates:    python-pyqt5 ffmpeg                         #"
echo "######################################################################"

echo "App installed."
