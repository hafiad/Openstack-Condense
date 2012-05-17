# vi: ts=4 expandtab
#
#    Copyright (C) 2009-2010 Canonical Ltd.
#    Copyright (C) 2012 Hewlett-Packard Development Company, L.P.
#
#    Author: Scott Moser <scott.moser@canonical.com>
#    Author: Juerg Hafliger <juerg.haefliger@hp.com>
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

import errno
import os
import platform
import pprint
import re
import socket
import subprocess
import sys
import traceback
import urllib
import urllib2
import urlparse
import yaml

import condense.log as logging
import condense.settings as settings

from Cheetah.Template import Template

log = logging.getLogger()

DEB_PLATFORM = 'debian'
RH_PLATFORM = 'redhat'
PLATFORM_LOOKUPS = {
    r'fedora': RH_PLATFORM,
    r'redhat': RH_PLATFORM,
    r"ubuntu": DEB_PLATFORM,
}
TMP_TPL = '/etc/cloud/templates/%s.tmpl'


def read_conf(fname):
    try:
        with open(fname, "r") as stream:
            data = stream.read()
            data = data.strip()
            if not data:
                conf = {}
            else:
                conf = yaml.load(data)
            stream.close()
        return conf
    except IOError as e:
        if e.errno == errno.ENOENT:
            return {}
        raise


def get_base_cfg(cfgfile, cfg_builtin=None, parsed_cfgs=None):
    kerncfg = {}
    syscfg = {}
    if parsed_cfgs and cfgfile in parsed_cfgs:
        return(parsed_cfgs[cfgfile])

    syscfg = read_conf_with_confd(cfgfile)

    # kernel parameters override system config
    combined = mergedict(kerncfg, syscfg)

    if cfg_builtin:
        builtin = dict(cfg_builtin)
        fin = mergedict(combined, builtin)
    else:
        fin = combined

    if parsed_cfgs != None:
        parsed_cfgs[cfgfile] = fin
    return(fin)


def get_cfg_option_bool(yobj, key, default=False):
    log.debug("Looking for %s in %s", key, yobj)
    if key not in yobj:
        return default
    val = yobj[key]
    if type(val) is bool:
        return val
    if str(val).lower() in ['true', '1', 'on', 'yes']:
        return True
    return False


def get_cfg_option_str(yobj, key, default=None):
    if key not in yobj:
        return default
    return yobj[key]


def get_cfg_option_list_or_str(yobj, key, default=None):
    """
    Gets the C{key} config option from C{yobj} as a list of strings. If the
    key is present as a single string it will be returned as a list with one
    string arg.

    @param yobj: The configuration object.
    @param key: The configuration key to get.
    @param default: The default to return if key is not found.
    @return: The configuration option as a list of strings or default if key
        is not found.
    """
    if not key in yobj:
        return default
    if yobj[key] is None:
        return []
    if isinstance(yobj[key], list):
        return yobj[key]
    return [yobj[key]]


# get a cfg entry by its path array
# for f['a']['b']: get_cfg_by_path(mycfg,('a','b'))
def get_cfg_by_path(yobj, keyp, default=None):
    cur = yobj
    for tok in keyp:
        if tok not in cur:
            return(default)
        cur = cur[tok]
    return(cur)


def mergedict(src, cand):
    """
    Merge values from C{cand} into C{src}. If C{src} has a key C{cand} will
    not override. Nested dictionaries are merged recursively.
    """
    if isinstance(src, dict) and isinstance(cand, dict):
        for k, v in cand.iteritems():
            if k not in src:
                src[k] = v
            else:
                src[k] = mergedict(src[k], v)
    return src


def determine_platform():
    run_plt = platform.platform()
    for pt, plt in PLATFORM_LOOKUPS.items():
        if re.search(pt, run_plt, re.I):
            return plt
    return None


def log_thing(to_log, header='', logger=None):
    if not to_log:
        return
    if not logger:
        logger = log
    if header:
        if not header.endswith(":"):
            header += ":"
    logger.info("%s\n%s", header, pprint.pformat(to_log, indent=2))


def write_file(filename, content, mode=0644, omode="wb"):
    """
    Writes a file with the given content and sets the file mode as specified.
    Resotres the SELinux context if possible.

    @param filename: The full path of the file to write.
    @param content: The content to write to the file.
    @param mode: The filesystem mode to set on the file.
    @param omode: The open mode used when opening the file (r, rb, a, etc.)
    """
    try:
        os.makedirs(os.path.dirname(filename))
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise e

    log.info("Writing to %s (%o)(%s) - %s bytes", filename, mode, omode, len(content))
    for line in content.splitlines():
        log.info("> %s", line)

    with open(filename, omode) as f:
        f.write(content)
        f.flush()
        if mode is not None:
            os.chmod(filename, mode)


def subp(args, input_=None, allowed_rcs=None):
    if not allowed_rcs:
        allowed_rcs = [0]
    log.info("Running command: `%s` with allowed return codes (%s)",
            " ".join(args), ", ".join([str(rc) for rc in allowed_rcs]))
    sp = subprocess.Popen(args, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, stdin=subprocess.PIPE)
    if input_ is not None:
        out, err = sp.communicate(input_)
    else:
        out, err = sp.communicate()
    if sp.returncode not in allowed_rcs:
        raise subprocess.CalledProcessError(sp.returncode, args)
    return (out, err)


def render_to_file(template, outfile, searchList):
    fn = settings.template_tpl % template
    t = Template(file=fn, searchList=[searchList])
    with open(outfile, 'w') as f:
        f.write(t.respond())


def render_string(template, searchList):
    return Template(template, searchList=[searchList]).respond()


def logexc(logger, lvl=logging.DEBUG):
    if not logger:
        logger = log
    logger.log(lvl, traceback.format_exc())


def read_conf_d(confd):
    # get reverse sorted list (later trumps newer)
    confs = sorted(os.listdir(confd), reverse=True)

    # remove anything not ending in '.cfg'
    confs = [f for f in confs if f.endswith(".cfg")]

    # remove anything not a file
    confs = [f for f in confs if os.path.isfile("%s/%s" % (confd, f))]

    cfg = {}
    for conf in confs:
        cfg = mergedict(cfg, read_conf("%s/%s" % (confd, conf)))

    return(cfg)


def read_conf_with_confd(cfgfile):
    cfg = read_conf(cfgfile)
    confd = False
    if "conf_d" in cfg:
        if cfg['conf_d'] is not None:
            confd = cfg['conf_d']
            if not isinstance(confd, str):
                raise Exception("cfgfile %s contains 'conf_d' "
                                "with non-string" % cfgfile)
    elif os.path.isdir("%s.d" % cfgfile):
        confd = "%s.d" % cfgfile

    if not confd:
        return cfg

    confd_cfg = read_conf_d(confd)
    return mergedict(confd_cfg, cfg)


def ensure_dirs(dirlist, mode=0755):
    fixmodes = []
    for d in dirlist:
        if not os.path.isdir(d):
            try:
                if mode != None:
                    os.makedirs(d)
                else:
                    os.makedirs(d, mode)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
                if mode != None:
                    fixmodes.append(d)
        for d in fixmodes:
            os.chmod(d, mode)


def chownbyname(fname, user=None, group=None):
    uid = -1
    gid = -1
    if user == None and group == None:
        return
    if user:
        import pwd
        uid = pwd.getpwnam(user).pw_uid
    if group:
        import grp
        gid = grp.getgrnam(group).gr_gid

    os.chown(fname, uid, gid)


def readurl(url, data=None, timeout=None):
    openargs = {}
    if timeout != None:
        openargs['timeout'] = timeout

    if data is None:
        req = urllib2.Request(url)
    else:
        encoded = urllib.urlencode(data)
        req = urllib2.Request(url, encoded)

    response = urllib2.urlopen(req, **openargs)
    return(response.read())


# shellify, takes a list of commands
#  for each entry in the list
#    if it is an array, shell protect it (with single ticks)
#    if it is a string, do nothing
def shellify(cmdlist):
    content = "#!/bin/sh\n"
    escaped = "%s%s%s%s" % ("'", '\\', "'", "'")
    for args in cmdlist:
        # if the item is a list, wrap all items in single tick
        # if its not, then just write it directly
        if isinstance(args, list):
            fixed = []
            for f in args:
                fixed.append("'%s'" % str(f).replace("'", escaped))
            content = "%s%s\n" % (content, ' '.join(fixed))
        else:
            content = "%s%s\n" % (content, str(args))
    return content


def dos2unix(string):
    # find first end of line
    pos = string.find('\n')
    if pos <= 0 or string[pos - 1] != '\r':
        return(string)
    return(string.replace('\r\n', '\n'))


def get_hostname_fqdn(cfg, cloud):
    # return the hostname and fqdn from 'cfg'.  If not found in cfg,
    # then fall back to data from cloud
    if "fqdn" in cfg:
        # user specified a fqdn.  Default hostname then is based off that
        fqdn = cfg['fqdn']
        hostname = get_cfg_option_str(cfg, "hostname", fqdn)
    else:
        if "hostname" in cfg and cfg['hostname'].find('.') > 0:
            # user specified hostname, and it had '.' in it
            # be nice to them.  set fqdn and hostname from that
            fqdn = cfg['hostname']
            hostname = fqdn
        else:
            # no fqdn set, get fqdn from cloud.
            # get hostname from cfg if available otherwise cloud
            fqdn = cloud.get_hostname(fqdn=True)
            if "hostname" in cfg:
                hostname = cfg['hostname']
            else:
                hostname = cloud.get_hostname()
    return (hostname, fqdn)


def get_fqdn_from_hosts(hostname, filename="/etc/hosts"):
    # this parses /etc/hosts to get a fqdn.  It should return the same
    # result as 'hostname -f <hostname>' if /etc/hosts.conf
    # did not have did not have 'bind' in the order attribute
    fqdn = None
    try:
        with open(filename, "r") as hfp:
            for line in hfp.readlines():
                hashpos = line.find("#")
                if hashpos >= 0:
                    line = line[0:hashpos]
                toks = line.split()

                # if there there is less than 3 entries (ip, canonical, alias)
                # then ignore this line
                if len(toks) < 3:
                    continue

                if hostname in toks[2:]:
                    fqdn = toks[1]
                    break
            hfp.close()
    except IOError as e:
        if e.errno == errno.ENOENT:
            pass

    return fqdn


def is_resolvable(name):
    """ determine if a url is resolvable, return a boolean """
    try:
        socket.getaddrinfo(name, None)
        return True
    except socket.gaierror:
        return False


def is_resolvable_url(url):
    """ determine if this url is resolvable (existing or ip) """
    return is_resolvable(urlparse.urlparse(url).hostname)


def close_stdin():
    """
    reopen stdin as /dev/null so even subprocesses or other os level things get
    /dev/null as input.
    """
    with open(os.devnull) as fp:
        os.dup2(fp.fileno(), sys.stdin.fileno())
