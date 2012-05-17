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


from condense import util

import os
import re


def handle(_name, cfg, cloud, log, _args):
    if util.get_cfg_option_bool(cfg, "preserve_hostname", False):
        log.debug("Option 'preserve_hostname' is set. Not setting hostname.")
        return True

    (hostname, _fqdn) = util.get_hostname_fqdn(cfg, cloud)
    try:
        old_name = set_hostname(hostname, log)
        if old_name:
            prev_fn = "%s/%s" % (cloud.get_cpath('data'), "previous-hostname")
            util.write_file(prev_fn, "%s\n" % (old_name), 0644)
    except Exception:
        util.logexc(log)
        log.warn("Failed to set hostname to %s", hostname)

    return True


def set_hostname_rh(hostname, log):
    lines = []
    with open('/etc/sysconfig/network', 'r') as fh:
        lines = fh.read().splitlines()
    adjusted_lines = []
    old_hostname = None
    for line in lines:
        mtch = re.match(r"^\s*HOSTNAME\s*=\s*(.*)$", line, re.I)
        if mtch:
            old_hostname = mtch.group(1)
            log.info("Removing old hostname entry - %s", line)
        else:
            adjusted_lines.append(line)
    adjusted_lines.append("HOSTNAME=%s" % (hostname))
    contents = "%s\n" % os.linesep.join(adjusted_lines)
    util.write_file('/etc/sysconfig/network', contents, 0644)
    return old_hostname



def set_hostname_deb(hostname, log):

    def read_hostname(filename, default=None):
        with open(filename, "r") as fp:
            lines = fp.readlines()
            for line in lines:
                hpos = line.find("#")
                if hpos != -1:
                    line = line[0:hpos]
                line = line.rstrip()
                if line:
                    return line
        return default

    old_hostname = read_hostname('/etc/hostname')
    util.write_file("/etc/hostname", "%s\n" % hostname, 0644)
    return old_hostname


def set_hostname(hostname, log):
    util.subp(['hostname', hostname])
    platform = util.determine_platform()
    log.info("Setting hostname on platform: %s", platform)
    old_name = None
    if platform == util.RH_PLATFORM:
        old_name = set_hostname_rh(hostname, log)
    else:
        old_name = set_hostname_deb(hostname, log)
    return old_name
