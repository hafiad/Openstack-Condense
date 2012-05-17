import os

# Main program name (used in directory creations)
root_name = 'condense'

# Where we write logging to (besides stdout)
log_file_tpl = os.path.join('/var/log/', root_name + '.%s.log')

# Root location of condense output
varlibdir = os.path.join('/var/lib/', root_name)
cur_instance_link = os.path.join(varlibdir, "instance")
boot_finished = os.path.join(cur_instance_link, "boot-finished")

# Where our root config should be
system_config = os.path.join('/etc/', root_name, root_name + '.cfg')

# Backup when cfg can't be loaded
cfg_builtin = {
    'datasource_list': ["ec2"],
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
src_mod_tpl = root_name + '.sources.%s'
cc_mod_tpl = root_name + '.handlers.%s'

# Where any templates are
template_tpl = os.path.join('/etc/', root_name, 'templates', '%s.tmpl')

# Template for stages
stage_tpl = "cloud_%s_modules"
