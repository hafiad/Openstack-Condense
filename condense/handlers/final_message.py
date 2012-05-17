# vi: ts=4 expandtab
#
#    Copyright (C) 2011 Canonical Ltd.
#    Copyright (C) 2012 Hewlett-Packard Development Company, L.P.
#
#    Author: Scott Moser <scott.moser@canonical.com>
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

import sys
import time

from condense import (per_always, boot_finished)
from condense import util
frequency = per_always


def handle(_name, cfg, _cloud, log, args):
    if len(args) != 0:
        msg_in = str(args[0])
    else:
        msg_in = util.get_cfg_option_str(cfg, "final_message", "Finished at $TIMESTAMP. Up $UPTIME seconds")

    uptime = "na"
    try:
        with open("/proc/uptime", 'r') as fh:
            uptime_tmp = fh.read().split(" ")[0]
            uptime_tmp = uptime_tmp.strip()
            if uptime_tmp:
                uptime = uptime_tmp
    except IOError as e:
        log.warn("Unable to open /proc/uptime")

    try:
        ts = time.strftime("%a, %d %b %Y %H:%M:%S %z", time.gmtime())
    except:
        ts = "na"

    try:
        subs = {'UPTIME': uptime, 'TIMESTAMP': ts}
        log.info(util.render_string(msg_in, subs))
    except Exception as e:
        log.warn("Failed to render string: %s" % e)

    with open(boot_finished, "wb") as fp:
        fp.write(uptime + ":" + ts + "\n")
