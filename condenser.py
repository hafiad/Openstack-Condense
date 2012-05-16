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

import os
import subprocess
import sys
import time
import traceback

from optparse import OptionParser

from condense.exceptions import DataSourceNotFoundException
from condense import (get_base_cfg, get_builtin_cfg, initfs, 
                      get_cpath,  get_ipath_cur,
                      Init, Config)
from condense.handlers import (read_cc_modules, run_cc_modules)
from condense.data_source import (DEP_FILESYSTEM, DEP_NETWORK)

from condense import log
from condense import logging
from condense import netinfo
from condense import util


def warn(wstr):
    sys.stderr.write("WARN: %s\n" % wstr)
    sys.stderr.flush()


def fatality(msg='', rc=0, do_die=True):
    if msg:
        if rc != 0:
            log.warn(msg)
        else:
            log.info(msg)
    if do_die:
        sys.exit(rc)


VALID_OPTIONS = ['start', 'final', 'config']


def extract_opts():
    parser = OptionParser()
    parser.add_option("-a", "--action", dest="action", action="store",
                  help="action to take, one of (%s)" % (", ".join(VALID_OPTIONS)),
                  metavar="ACTION", default="")
    parser.add_option("-f", "--file", dest="test_file", action="store",
                  help="file to use instead of fetched config (for testing)", metavar="FILE")
    parser.add_option("-v", "--verbose",
        action="append_const",
        const=1,
        dest="verbosity",
        default=[1],
        help="increase the verbosity level")
    (options, args) = parser.parse_args()
    out = dict()
    out['action'] = options.action or ''
    out['test_file'] = options.test_file
    out['verbosity'] = len(options.verbosity)
    out['extra'] = args
    return out


def verify_opts(opts):
    action = opts['action']
    action = action.lower().strip()
    if not action in VALID_OPTIONS:
        raise RuntimeError("Action must be one of (%s)" % (", ".join(VALID_OPTIONS)))
    return opts


def get_now():
    now = time.strftime("%a, %d %b %Y %H:%M:%S %z", time.gmtime())
    return now


def form_stage_name(part):
    return "cloud_%s_modules" % (part)


def main_start(app_name, uptime, test_file, **kwargs):
    cfg_path = test_file
    deps = (DEP_FILESYSTEM, DEP_NETWORK)
    try:
        log.info("Base config loading from: %s", (cfg_path))
        cfg = get_base_cfg(cfg_path)
    except Exception as e:
        log.exception("Failed to get base config. Falling back to builtin.")
        cfg = get_builtin_cfg()

    log.debug("Using config %s", cfg)
    try:
        initfs()
    except Exception as e:
        log.warn("Failed to init the filesystem, likely bad things to come: %s" % (e))

    stop_files = [get_ipath_cur("obj_pkl")]
    for fn in stop_files:
        try:
            with open(fn, "r") as fp:
                pass
        except:
            continue
        fatality("No need for start to run due to existence of %r" % (fn))

    log.info("%s starting: %s.", app_name, get_now())
    log.info("System has been up %s seconds.", uptime)

    init_deps = deps
    log.info("Dependencies are: %s", init_deps)
    log.info("Network info is: \n%s", netinfo.debug_info())

    cloud = Init(ds_deps=init_deps)
    log.info("Full config is %s", cloud.cfg)
    try:
        cloud.get_data_source()
    except DataSourceNotFoundException as e:
        fatality("No data found: %s" % e, rc=1)

    # set this as the current instance
    iid = cloud.set_cur_instance()
    log.info("Current instance is: %r", str(iid))

    # store the metadata
    cloud.update_cache()
    log.info("Found data source: %r" % cloud.datasource)
    
    # run the initial modules
    cfg_path = get_ipath_cur("cloud_config")
    cc = Config(cfg_path, cloud)
    module_list = read_cc_modules(cc.cfg, form_stage_name('init'))
    failures = run_cc_modules(cc, module_list, log)
    fail_count = len(failures)
    if fail_count:
        fatality("Errors running modules: [%s]" % (failures), rc=len(failures))

    # send the start next stage event
    cc_ready = ['initctl', 'emit', 'condense-config']
    log.debug("Emitting command %s", " ".join(cc_ready))
    subprocess.Popen(cc_ready).communicate()


def main_continue(action, app_name, uptime, **kwargs):
    cfg_path = get_ipath_cur("cloud_config")
    cloud = Init(ds_deps=[])  # ds_deps=[], get only cached
    try:
        cloud.get_data_source()
    except DataSourceNotFoundException as e:
        # there was no datasource found, theres nothing to do
        fatality("No datasource found: %s" % e)

    log.info("Full config is %s", cloud.cfg)
    log.info("Found data source: %r" % cloud.datasource)
    cc = Config(cfg_path, cloud)

    # run the stages modules
    log.info("%s starting stage %s: %s", app_name, action, get_now())
    log.info("System has been up %s seconds.", uptime)
    module_list = read_cc_modules(cc.cfg, form_stage_name(action))
    failures = run_cc_modules(cc, module_list, log)
    if len(failures):
        fatality("Errors running modules [%s]: %s" % (action, failures), rc=len(failures))


def setup_logging(opts):
    if opts['verbosity'] > 1:
        logging.setupLogging(logging.DEBUG)
    else:
        logging.setupLogging(logging.INFO)


ACTION_FUNCS = {
    'start': main_start,
    'final': main_continue,
    'config': main_continue,
}


def main():

    me = os.path.basename(sys.argv[0])
    opts = verify_opts(extract_opts())
    if not os.geteuid() == 0:
        fatality('%s must be run as root!' % (me), rc=1)

    print("Extracted cli opts %s" % (opts))
    util.close_stdin()

    uptime = '??'
    try:
        with open("/proc/uptime", 'r') as uptimef:
            uptime = uptimef.read().split(" ")[0]
    except IOError:
        warn("Unable to open /proc/uptime")
        uptime = "na"

    setup_logging(opts)
    opts['uptime'] = uptime
    opts['app_name'] = me
    start_time = time.time()
    log.info("Starting action %r" % (opts['action']))
    func = ACTION_FUNCS[opts['action']]
    func(**opts)
    end_time = time.time()
    log.info("Took %s seconds to finish action %r" % (end_time - start_time, opts['action']))


if __name__ == '__main__':
    try:
        main()
        fatality()
    except Exception as e:
        fatality("Broke due to: %s" % e, rc=1, do_die=False)
        traceback.print_exc(file=sys.stderr)
        fatality(rc=1)
