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

from time import sleep

from condense import (util, per_instance)
frequency = per_instance


def handle(_name, cfg, cloud, log, args):

    if len(args) != 0:
        ph_cfg = util.read_conf(args[0])
    else:
        if not 'phone_home' in cfg:
            return
        ph_cfg = cfg['phone_home']

    if 'url' not in ph_cfg:
        log.warn("No 'url' token in phone_home")
        return

    url = ph_cfg['url']
    post_list = ph_cfg.get('post', 'all')
    tries = ph_cfg.get('tries', 10)
    try:
        tries = int(tries)
    except:
        log.warn("Tries is not an integer. using 10")
        tries = 10

    if post_list == "all":
        post_list = ['pub_key_dsa', 'pub_key_rsa',
                     'pub_key_ecdsa', 'instance_id',
                     'hostname']

    all_keys = {}
    all_keys['instance_id'] = cloud.get_instance_id()
    all_keys['hostname'] = cloud.get_hostname()

    pubkeys = {
        'pub_key_dsa': '/etc/ssh/ssh_host_dsa_key.pub',
        'pub_key_rsa': '/etc/ssh/ssh_host_rsa_key.pub',
        'pub_key_ecdsa': '/etc/ssh/ssh_host_ecdsa_key.pub',
    }

    for n, path in pubkeys.iteritems():
        try:
            with open(path, "rb") as fp:
                all_keys[n] = fp.read()
        except:
            log.warn("%s: failed to open" % path)

    submit_keys = {}
    for k in post_list:
        if k in all_keys:
            submit_keys[k] = all_keys[k]
        else:
            submit_keys[k] = "N/A"
            log.warn("Requested key %s from 'post' list not available")

    url = util.render_string(url, {'INSTANCE_ID': all_keys['instance_id']})
    last_e = None
    for i in range(0, tries):
        try:
            util.readurl(url, submit_keys)
            log.debug("Succeeded submit to %s on try %i" % (url, i + 1))
            return
        except Exception as e:
            log.warn("Failed to post to %s on try %i" % (url, i + 1))
            last_e = e
        sleep(3)

    log.warn("Failed to post to %s in %i tries," % (url, tries))
    if last_e is not None:
        raise last_e
