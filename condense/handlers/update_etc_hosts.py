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

from condense import (util, per_always)
frequency = per_always


def handle(_name, cfg, cloud, log, _args):
    (hostname, fqdn) = util.get_hostname_fqdn(cfg, cloud)
    manage_hosts = str(util.get_cfg_option_str(cfg, "manage_etc_hosts", 'False'))
    manage_hosts = manage_hosts.lower().strip()
    if manage_hosts in ["true", "template"]:
        # render from template file
        try:
            if not hostname:
                log.warn("manage_etc_hosts was set, but no hostname found")
                return
            tmpl_fn = 'hosts-%s' % (util.determine_platform())
            util.render_to_file(tmpl_fn, '/etc/hosts',
                                {'hostname': hostname, 'fqdn': fqdn})
        except Exception:
            log.warn("Failed to update /etc/hosts")
            raise
    else:
        if manage_hosts not in ["false"]:
            log.warn("Unknown value for manage_etc_hosts.  Assuming False.")
        else:
            log.debug("Not managing /etc/hosts")
