import os

# Where we write logging to (besides stdout)
log_file_tpl = '/var/log/condense.%s.log'

# Root location of condense output
varlibdir = '/var/lib/condense'
cur_instance_link = os.path.join(varlibdir, "instance")
boot_finished = os.path.join(cur_instance_link, "boot-finished")
seeddir = os.path.join(varlibdir, "seed")

# Where our root config should be
system_config = '/etc/condense/condense.cfg'

# Backup when cfg can't be loaded
cfg_builtin = {
    'datasource_list': ["ConfigDrive", "Ec2"],
}

# TBD
pathmap = {
   "handlers": "/handlers",
   "scripts": "/scripts",
   "sem": "/sem",
   "boothooks": "/boothooks",
   "userdata_raw": "/user-data.txt",
   "userdata": "/user-data.txt.i",
   "obj_pkl": "/obj.pkl",
   "cloud_config": "/cloud-config.txt",
   "data": "/data",
   None: "",
}

# Constants shared
per_instance = "once-per-instance"
per_always = "always"
per_once = "once"

# Lookup modules names
src_mod_tpl = 'condense.sources.%s'
cc_mod_tpl = 'condense.handlers.%s'

# Where any templates are
template_tpl = '/etc/condense/templates/%s.tmpl'

# Template for stages
stage_tpl = "cloud_%s_modules"
