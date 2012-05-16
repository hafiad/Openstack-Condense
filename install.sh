#!/bin/bash

LOG_FN="install.log"

echo "Installing.."

set -x

sudo python setup.py install 2>&1 > $LOG_FN

echo "Check log in '$LOG_FN' for results"

