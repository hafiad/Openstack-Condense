# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#
#    Copyright 2011 OpenStack LLC.
#    All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import logging
import sys

from logging.handlers import SysLogHandler
from logging.handlers import WatchedFileHandler

from condense import settings

# A list of things we want to replicate from logging levels
CRITICAL = logging.CRITICAL
FATAL = logging.FATAL
ERROR = logging.ERROR
WARNING = logging.WARNING
WARN = logging.WARN
INFO = logging.INFO
DEBUG = logging.DEBUG
NOTSET = logging.NOTSET

# Methods
debug = logging.debug
info = logging.info
warning = logging.warning
warn = logging.warn
error = logging.error
exception = logging.exception
critical = logging.critical
log = logging.log

# Classes
root = logging.root
Formatter = logging.Formatter

# Handlers
Handler = logging.Handler
StreamHandler = logging.StreamHandler
WatchedFileHandler = WatchedFileHandler
FileHandler = logging.FileHandler
SysLogHandler = SysLogHandler


def setupLogging(log_level, format='%(levelname)s: @%(name)s : %(message)s'):
    root_logger = getLogger()
    console_logger = StreamHandler(sys.stdout)
    console_logger.setFormatter(Formatter(format))
    root_logger.addHandler(console_logger)
    file_logger = FileHandler(settings.log_file)
    file_logger.setFormatter(Formatter(format))
    root_logger.addHandler(file_logger)
    root_logger.setLevel(log_level)


def getLogger(name='condense'):
    return logging.getLogger(name)
