# vi: ts=4 expandtab
#
#    Common code for the EC2 initialisation scripts in Ubuntu
#    Copyright (C) 2008-2009 Canonical Ltd
#    Copyright (C) 2012 Hewlett-Packard Development Company, L.P.
#
#    Author: Soren Hansen <soren@canonical.com>
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

import errno
import glob
import os
import subprocess
import sys
import traceback

from time import time

import cPickle
import StringIO

import yaml

from condense import data_source
from condense import exceptions as excp
from condense import log as logging
from condense import util
from condense import importer
from condense import user_data as ud

from condense.settings import (system_config, cfg_builtin, cur_instance_link,
                               per_always, varlibdir, pathmap, per_instance,
                               boot_finished, per_once, cc_mod_tpl)

log = logging.getLogger()
parsed_cfgs = {}


class Init:

    def __init__(self, ds_deps=None, sysconfig=system_config):
        if ds_deps != None:
            self.ds_deps = ds_deps
        else:
            self.ds_deps = [data_source.DEP_FILESYSTEM, data_source.DEP_NETWORK]
        self.sysconfig = sysconfig
        self.cfg = None
        self.cfg = self.read_cfg()
        self.builtin_handlers = [
            ['text/cloud-config', self.handle_cloud_config, per_always],
        ]
        self.datasource = None
        self.cloud_config_str = ''
        self.datasource_name = ''

    def handle_cloud_config(self, ctype, filename, payload):

        if ctype == "__begin__":
            self.cloud_config_str = ""
            return

        if ctype == "__end__":
            cloud_config = self.get_ipath("cloud_config")
            util.write_file(cloud_config, self.cloud_config_str, 0600)
            return

        self.cloud_config_str += "\n#%s\n%s" % (filename, payload)

    def consume_userdata(self, frequency=per_instance):

        part_handlers = {}
        for (btype, bhand, bfreq) in self.builtin_handlers:
            i_handler = InternalPartHandler(bhand, [btype], bfreq)
            handler_register(i_handler, part_handlers, frequency)

        def partwalker_callback(ctype, filename, payload):
            handlers = part_handlers.get(ctype, [])
            for handler in handlers:
                handler_handle_part(handler, ctype, filename, payload, frequency)

        ud.walk_userdata(self.get_userdata(), partwalker_callback)

        # give callbacks opportunity to finalize
        called = []
        for (_mtype, mods) in part_handlers.items():
            for mod in mods:
                if mod in called:
                    continue
                handler_call_end(mod, frequency)
                called.append(mod)

    def read_cfg(self):
        if self.cfg:
            return self.cfg
        try:
            conf = util.get_base_cfg(self.sysconfig, cfg_builtin, parsed_cfgs)
        except Exception:
            conf = get_builtin_cfg()
        return conf

    def restore_from_cache(self):
        try:
            # we try to restore from a current link and static path
            # by using the instance link, if purge_cache was called
            # the file wont exist
            cache = get_ipath_cur('obj_pkl')
            with open(cache, "rb") as f:
                data = cPickle.load(f)
            self.datasource = data
            return True
        except Exception:
            return False

    def write_to_cache(self):
        cache = self.get_ipath("obj_pkl")
        try:
            os.makedirs(os.path.dirname(cache))
        except OSError as e:
            if e.errno != errno.EEXIST:
                return False

        with open(cache, "wb") as f:
            cPickle.dump(self.datasource, f)
            f.flush()
            os.chmod(cache, 0400)

    def get_data_source(self):
        if self.datasource is not None:
            return True

        if self.restore_from_cache():
            log.debug("Restored from cached datasource: %s" % self.datasource)
            return True

        cfglist = self.cfg['datasource_list']
        dslist = list_sources(cfglist, self.ds_deps)
        dsnames = [f.__name__ for f in dslist]
        log.debug("Searching for data source in %s" % dsnames)
        for cls in dslist:
            ds = cls.__name__
            try:
                s = cls(sys_cfg=self.cfg)
                log.debug("Checking if %r can provide us the needed data.", ds)
                if s.get_data():
                    self.datasource = s
                    self.datasource_name = ds
                    return True
            except Exception:
                log.warn("Get data of %s raised!", ds)
                util.logexc(log)

        msg = "Did not find data source. Searched classes: %s" % (dsnames)
        log.debug(msg)
        raise excp.DataSourceNotFoundException(msg)

    def set_cur_instance(self):
        try:
            os.unlink(cur_instance_link)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

        iid = self.get_instance_id()
        os.symlink("./instances/%s" % iid, cur_instance_link)
        idir = self.get_ipath()
        dlist = []
        for d in ["handlers", "scripts", "sem"]:
            dlist.append("%s/%s" % (idir, d))

        util.ensure_dirs(dlist)

        ds = "%s: %s\n" % (self.datasource.__class__, str(self.datasource))
        dp = self.get_cpath('data')
        util.write_file("%s/%s" % (idir, 'datasource'), ds)
        util.write_file("%s/%s" % (dp, 'previous-datasource'), ds)
        util.write_file("%s/%s" % (dp, 'previous-instance-id'), "%s\n" % iid)
        return iid

    def get_userdata(self):
        return self.datasource.get_userdata()

    def get_userdata_raw(self):
        return self.datasource.get_userdata_raw()

    def get_instance_id(self):
        return self.datasource.get_instance_id()

    def update_cache(self):
        self.write_to_cache()
        self.store_userdata()

    def store_userdata(self):
        util.write_file(self.get_ipath('userdata_raw'),
            self.datasource.get_userdata_raw(), 0600)
        util.write_file(self.get_ipath('userdata'),
            self.datasource.get_userdata(), 0600)

    def sem_getpath(self, name, freq):
        if freq == 'once-per-instance':
            return("%s/%s" % (self.get_ipath("sem"), name))
        return("%s/%s.%s" % (get_cpath("sem"), name, freq))

    def sem_has_run(self, name, freq):
        if freq == per_always:
            return False
        semfile = self.sem_getpath(name, freq)
        if os.path.exists(semfile):
            return True
        return False

    def sem_acquire(self, name, freq):
        semfile = self.sem_getpath(name, freq)

        try:
            os.makedirs(os.path.dirname(semfile))
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise e

        if os.path.exists(semfile) and freq != per_always:
            return False

        # TODO: race condition?? - probably should use real lock sometime
        try:
            with open(semfile, "w") as f:
                contents = []
                contents.append("%s" % str(time()))
                contents.append("%s" % (os.getpid()))
                contents.append("%s" % (os.getpid()))
                f.write("\n".join(contents))
            log.debug("Acquired file sempahore: %s", semfile)
        except IOError:
            return False

        return True

    def sem_clear(self, name, freq):
        semfile = self.sem_getpath(name, freq)
        try:
            os.unlink(semfile)
            log.debug("Clearing file sempahore: %s", semfile)
        except OSError as e:
            if e.errno != errno.ENOENT:
                return False
        return True

    # acquire lock on 'name' for given 'freq'
    # if that does not exist, then call 'func' with given 'args'
    # if 'clear_on_fail' is True and func throws an exception
    #  then remove the lock (so it would run again)
    def sem_and_run(self, semname, freq, func, args=None, clear_on_fail=False):
        if args is None:
            args = []
        if self.sem_has_run(semname, freq):
            log.debug("%s already ran %s", semname, freq)
            return False
        try:
            if not self.sem_acquire(semname, freq):
                raise Exception("Failed to acquire lock on %s" % semname)
            func(*args)
        except:
            if clear_on_fail:
                self.sem_clear(semname, freq)
            raise

        return True

    # get_ipath : get the instance path for a name in pathmap
    # (/var/lib/cloud/instances/<instance>/name)<name>)
    def get_ipath(self, name=None):
        return("%s/instances/%s%s"
               % (varlibdir, self.get_instance_id(), pathmap[name]))

    def get_locale(self):
        return self.datasource.get_locale()

    def get_hostname(self, fqdn=False):
        return self.datasource.get_hostname(fqdn=fqdn)

    def device_name_to_device(self, name):
        return self.datasource.device_name_to_device(name)

    # I really don't know if this should be here or not, but
    # I needed it in cc_update_hostname, where that code had a valid 'cloud'
    # reference, but did not have a cloudinit handle
    # (ie, no cloudinit.get_cpath())
    def get_cpath(self, name=None):
        return get_cpath(name)



class Config():
    cfgfile = None
    cfg = None

    def __init__(self, cfgfile, cloud=None, ds_deps=None):
        if cloud == None:
            self.cloud = Init(ds_deps)
            self.cloud.get_data_source()
        else:
            self.cloud = cloud
        self.cfg = self.get_config_obj(cfgfile)

    def get_config_obj(self, cfgfile):
        try:
            cfg = util.read_conf(cfgfile)
        except Exception:
            log.critical("Failed loading of cloud config '%s'. "
                         "Continuing with empty config" % cfgfile)
            util.logexc(log)
            cfg = None

        if cfg is None:
            cfg = {}

        try:
            ds_cfg = self.cloud.datasource.get_config_obj()
        except Exception:
            ds_cfg = {}

        cfg = util.mergedict(cfg, ds_cfg)
        return util.mergedict(cfg, self.cloud.cfg)

    def handle(self, name, args, freq=None):
        real_name = name.replace("-", "_")
        mod_name = cc_mod_tpl % (real_name)
        log.debug("Importing handler module: %s", mod_name)

        mod = importer.import_module(mod_name)
        def_freq = getattr(mod, "frequency", per_instance)
        handler = getattr(mod, "handle")

        if not freq:
            freq = def_freq

        self.cloud.sem_and_run("config-" + name, freq, handler,
            [name, self.cfg, self.cloud, log, args])


def initfs():
    subds = ['scripts/per-instance', 'scripts/per-once', 'scripts/per-boot',
             'seed', 'instances', 'handlers', 'sem', 'data']
    dlist = []
    for subd in subds:
        dlist.append("%s/%s" % (varlibdir, subd))
    util.ensure_dirs(dlist)


def purge_cache(rmcur=True):
    rmlist = [boot_finished]
    if rmcur:
        rmlist.append(cur_instance_link)
    for f in rmlist:
        try:
            os.unlink(f)
        except OSError as e:
            if e.errno == errno.ENOENT:
                continue
            return False
        except:
            return False
    return True


# get_ipath_cur: get the current instance path for an item
def get_ipath_cur(name=None):
    return("%s/%s%s" % (varlibdir, "instance", pathmap[name]))


# get_cpath : get the "clouddir" (/var/lib/cloud/<name>)
# for a name in dirmap
def get_cpath(name=None):
    return("%s%s" % (varlibdir, pathmap[name]))


def get_base_cfg(cfg_path=None):
    if cfg_path is None:
        cfg_path = system_config
    return util.get_base_cfg(cfg_path, cfg_builtin, parsed_cfgs)


def get_builtin_cfg():
    return dict(cfg_builtin)


def list_sources(cfg_list, depends):
    return data_source.list_sources(cfg_list, depends)


def handler_register(mod, part_handlers,  frequency):
    for mtype in mod.list_types():
        if mtype not in part_handlers:
            part_handlers[mtype] = []
        part_handlers[mtype].append(mod)
    handler_call_begin(mod, frequency)


def handler_call_begin(mod, frequency):
    handler_handle_part(mod, "__begin__", None, None, frequency)


def handler_call_end(mod, frequency):
    handler_handle_part(mod, "__end__", None, None, frequency)


def handler_handle_part(mod, ctype, filename, payload, frequency):
    modfreq = getattr(mod, "frequency", per_instance)
    if not (modfreq == per_always or
            (frequency == per_instance and modfreq == per_instance)):
        return
    try:
        mod.handle_part(ctype, filename, payload)
    except:
        util.logexc(log)


class InternalPartHandler:

    def __init__(self, handler, mtypes, frequency):
        self.handler = handler
        self.mtypes = mtypes
        self.frequency = frequency

    def list_types(self):
        return self.mtypes

    def handle_part(self, ctype, filename, payload):
        return self.handler(ctype, filename, payload)
