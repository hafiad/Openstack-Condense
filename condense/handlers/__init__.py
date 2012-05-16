# vi: ts=4 expandtab
#
#    Copyright (C) 2008-2010 Canonical Ltd.
#    Copyright (C) 2012 Hewlett-Packard Development Company, L.P.
#
#    Author: Chuck Short <chuck.short@canonical.com>
#    Author: Juerg Haefliger <juerg.haefliger@hp.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License version 3, as
#    published by the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import subprocess
import sys
import time
import traceback
import yaml

from condense import (per_instance, per_always, per_once,
                      get_ipath_cur, util)


# reads a cloudconfig module list, returns
# a 2 dimensional array suitable to pass to run_cc_modules
def read_cc_modules(cfg, name):
    if name not in cfg:
        return([])
    module_list = []
    # create 'module_list', an array of arrays
    # where array[0] = config
    #       array[1] = freq
    #       array[2:] = arguemnts
    for item in cfg[name]:
        if isinstance(item, str):
            module_list.append((item,))
        elif isinstance(item, list):
            module_list.append(item)
        else:
            raise TypeError("Failed to read '%s' item in config")
    return(module_list)


def run_cc_modules(cc, module_list, log):
    failures = []
    for cfg_mod in module_list:
        name = cfg_mod[0]
        freq = None
        run_args = []
        if len(cfg_mod) > 1:
            freq = cfg_mod[1]
        if len(cfg_mod) > 2:
            run_args = cfg_mod[2:]

        try:
            log.debug("Handling %s with freq=%s and args=%s" %
                (name, freq, run_args))
            cc.handle(name, run_args, freq=freq)
        except:
            log.warn(traceback.format_exc())
            log.error("Config handling of %s, %s, %s failed" %
                (name, freq, run_args))
            failures.append(name)
    return failures


def run_per_instance(name, func, args, clear_on_fail=False):
    semfile = "%s/%s" % (get_ipath_cur("data"), name)
    if os.path.exists(semfile):
        return

    util.write_file(semfile, str(time.time()))
    try:
        func(*args)
    except:
        if clear_on_fail:
            os.unlink(semfile)
        raise
