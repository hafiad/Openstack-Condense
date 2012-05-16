#!/bin/bash

echo "Cleaning..."

set -x

sudo rm -rf build/ condense.egg* dist* *.log
sudo rm -rf /usr/local/lib/python2.7/dist-packages/condense*
sudo rm -rf /var/log/condense*.log
sudo rm -rf /var/lib/condense/
sudo rm -rf /etc/condense
sudo rm -rf /etc/init/condense*.conf

