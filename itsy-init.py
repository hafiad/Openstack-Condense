#!/usr/bin/python
# vi: ts=4 expandtab
#
#    Copyright (C) 2009-2010 Canonical Ltd.
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

import errno
import os
import subprocess
import sys
import time
import traceback

import cloudinit
import cloudinit.CloudConfig as CC
import cloudinit.DataSource as ds
import cloudinit.netinfo as netinfo
import cloudinit.util as util


def warn(wstr):
    sys.stderr.write("WARN: %s\n" % wstr)
    sys.stderr.flush()


def debug(dstr):
    sys.stderr.write("DEBUG: %s\n" % dstr)
    sys.stderr.flush()


def info(istr):
    sys.stderr.write("INFO: %s\n" % istr)
    sys.stderr.flush()


def fatality(msg, rc=0):
    msg_printer_func = info
    if rc != 0:
        msg_printer_func = warn
    if msg:
        msg_printer_func(msg)
    msg_printer_func("Goodbye! (%s)" % (rc))
    sys.exit(rc)


def main():
    util.close_stdin()

    cmds = ("start", "start-local")
    deps = {"start": (ds.DEP_FILESYSTEM, ds.DEP_NETWORK),
            "start-local": (ds.DEP_FILESYSTEM, )}

    cmd = ""
    if len(sys.argv) > 1:
        cmd = sys.argv[1]

    cfg_path = None
    if len(sys.argv) > 2:
        # this is really for debugging only
        # but you can invoke on development system with ./config/cloud.cfg
        cfg_path = sys.argv[2]

    if not cmd in cmds:
        fatality("Bad command %s. Use one of [%s] please." % (cmd, ", ".join(cmds)), rc=1)

    now = time.strftime("%a, %d %b %Y %H:%M:%S %z", time.gmtime())
    try:
        uptimef = open("/proc/uptime")
        uptime = uptimef.read().split(" ")[0]
        uptimef.close()
    except IOError as e:
        warn("Unable to open /proc/uptime")
        uptime = "na"
    
    try:
        debug("Base config loading from: %s" % (cfg_path))
        cfg = cloudinit.get_base_cfg(cfg_path)
    except Exception as e:
        warn("Failed to get base config. Falling back to builtin due to: %s" % e)
        cfg = cloudinit.get_builtin_cfg()

    debug("Using config %s" % (cfg))
    try:
        (outfmt, errfmt) = CC.get_output_cfg(cfg, "init")
        if outfmt:
            debug("Redirecting stdout output to %s" % (outfmt))
        if errfmt:
            debug("Redirecting stderr err to %s" % (errfmt))
        if outfmt or errfmt:
            CC.redirect_output(outfmt, errfmt)
    except Exception as e:
        warn("Failed to get and set output config: %s" % e)

    cloudinit.logging_set_from_cfg(cfg)
    log = cloudinit.log
    
    try:
        cloudinit.initfs()
    except Exception as e:
        warn("Failed to initfs, likely bad things to come: %s" % (e))

    nonet_path = "%s/%s" % (cloudinit.get_cpath("data"), "no-net")
    if cmd == "start":

        stop_files = (cloudinit.get_ipath_cur("obj_pkl"), nonet_path)
        # if starting as the network start, there are cases
        # where everything is already done for us, and it makes
        # most sense to exit early and silently
        for f in stop_files:
            try:
                fp = open(f, "r")
                fp.close()
            except:
                continue
            fatality("No need for cloud-init start to run (%s)" % (f))

    elif cmd == "start-local":
        # cache is not instance specific, so it has to be purged
        # but we want 'start' to benefit from a cache if
        # a previous start-local populated one
        manclean = util.get_cfg_option_bool(cfg, 'manual_cache_clean', False)
        if manclean:
            log.debug("Not purging cache, manual_cache_clean = True")
        cloudinit.purge_cache(not manclean)

        try:
            os.unlink(nonet_path)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

    log.info("Cloud-init %r running: %s. System has been up %s seconds.", cmd, now, uptime)
    init_deps = deps.get(cmd, [])
    log.info("Dependencies are: %s", init_deps)
    log.info("Network info is: \n%s", netinfo.debug_info())

    cloud = cloudinit.CloudInit(ds_deps=init_deps)
    log.info("Full cloud init config is %s", cloud.cfg)
    try:
        cloud.get_data_source()
    except cloudinit.DataSourceNotFoundException as e:
        fatality("No data found: %s" % e, rc=1)

    # set this as the current instance
    iid = cloud.set_cur_instance()
    log.info("Current instance is: %r", str(iid))

    # store the metadata
    cloud.update_cache()

    log.info("Found data source: %r" % cloud.datasource)

    # parse the user data (ec2-run-userdata.py)
    try:
        ran = cloud.sem_and_run("consume_userdata", cloudinit.per_instance,
            cloud.consume_userdata, [cloudinit.per_instance], False)
        if not ran:
            cloud.consume_userdata(cloudinit.per_always)
    except:
        warn("Consuming user data failed!")
        raise

    cfg_path = cloudinit.get_ipath_cur("cloud_config")
    cc = CC.CloudConfig(cfg_path, cloud)

    # if the output config changed, update output and err
    try:
        outfmt_orig = outfmt
        errfmt_orig = errfmt
        (outfmt, errfmt) = CC.get_output_cfg(cc.cfg, "init")
        if outfmt_orig != outfmt or errfmt_orig != errfmt:
            warn("stdout, stderr changing to (%s,%s)" % (outfmt, errfmt))
            CC.redirect_output(outfmt, errfmt)
    except Exception as e:
        warn("Failed to get and set output config: %s" % e)
        traceback.print_exc(file=sys.stderr)

    module_list = CC.read_cc_modules(cc.cfg, "cloud_init_modules")
    failures = []
    if len(module_list):
        failures = CC.run_cc_modules(cc, module_list, log)
    else:
        fatality("No cloud init modules to run")

    fail_count = len(failures)
    if fail_count:
        fatality("There were %s module failures" % (fail_count), rc=fail_count)

    # send the cloud-config ready event
    cc_path = cloudinit.get_ipath_cur('cloud_config')
    cc_ready = cc.cfg.get("cc_ready_cmd",
        ['initctl', 'emit', 'cloud-config',
         '%s=%s' % (cloudinit.cfg_env_name, cc_path)])
    if cc_ready:
        if isinstance(cc_ready, str):
            cc_ready = ['sh', '-c', cc_ready]
        log.debug("Firing cc ready command %s", " ".join(cc_ready))
        subprocess.Popen(cc_ready).communicate()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        fatality("Broke due to: %s" % e, rc=1)
