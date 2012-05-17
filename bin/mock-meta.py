#!/usr/bin/python

import functools
import httplib
import logging
import sys
import string
import random
import yaml

from optparse import OptionParser

from BaseHTTPServer import (HTTPServer, BaseHTTPRequestHandler)

log = logging.getLogger('meta-server')

from IPy import IP

# Constants
EC2_VERSIONS = [
    '1.0',
    '2007-01-19',
    '2007-03-01',
    '2007-08-29',
    '2007-10-10',
    '2007-12-15',
    '2008-02-01',
    '2008-09-01',
    '2009-04-04',
    'latest',
]

BLOCK_DEVS = [
    'ami',
    'root',
    'ephemeral0',
]

DEV_MAPPINGS = {
    'ephemeral0': 'vdb',
    # ??
    'root': 'vda',
    # ??
    'ami': 'vda', 
}

META_CAPABILITIES = [
    'aki-id',
    'ami-id',
    'ami-launch-index',
    'ami-manifest-path',
    'ari-id',
    'block-device-mapping/',
    'hostname',
    'instance-action',
    'instance-id',
    'instance-type',
    'local-hostname',
    'local-ipv4',
    'placement/',
    'public-hostname',
    'public-ipv4',
    'reservation-id',
    'security-groups'
]

PLACEMENT_CAPABILITIES = {
    'availability-zone': 'us-east',
}

INSTANCE_IP = IP('10.0.0.1')
INSTANCE_INDEX = 0
ID_CHARS = [c for c in (string.ascii_uppercase + string.digits)]


def yamlify(data):
    formatted = yaml.dump(data,
        line_break="\n",
        indent=4,
        explicit_start=True,
        explicit_end=True,
        default_flow_style=False)
    return formatted


def format_text(text):
    if not len(text):
        return "<<"
    lines = text.splitlines()
    nlines = []
    for line in lines:
        nlines.append("<< %s" % line)
    return "\n".join(nlines)


def id_generator(size=6, lower=False):
    txt = ''.join(random.choice(ID_CHARS) for x in range(size))
    if lower:
        return txt.lower()
    else:
        return txt


class MetaDataHandler(object):

    def __init__(self, opts):
        self.opts = opts
        self.instances = {}

    def get_data(self, params, who):
        if not params:
            return "\n".join(META_CAPABILITIES)
        action = params[0]
        action = action.lower()
        if action == 'instance-id':
            return 'i-%s' % (id_generator(lower=True))
        elif action == 'ami-launch-index':
            return "%s" % INSTANCE_INDEX
        elif action == 'aki-id':
            return 'aki-%s' % (id_generator(lower=True))
        elif action == 'ami-id':
            return 'ami-%s' % (id_generator(lower=True))
        elif action == 'ari-id':
            return 'ari-%s' % (id_generator(lower=True))
        elif action == 'block-device-mapping':
            nparams = params[1:]
            if not nparams:
                return "\n".join(BLOCK_DEVS)
            else:
                return "%s" % (DEV_MAPPINGS.get(nparams[0].strip(), ''))
        elif action in ['hostname', 'local-hostname', 'public-hostname']:
            return "%s" % (who)
        elif action == 'instance-type':
            return 'm1.small'
        elif action == 'security-groups':
            return 'default'
        elif action in ['local-ipv4', 'public-ipv4']:
            return "%s" % (INSTANCE_IP)
        elif action == 'reservation-id':
            return "r-%s" % (id_generator(lower=True))
        elif action == 'placement':
            nparams = params[1:]
            if not nparams:
                return "\n".join(PLACEMENT_CAPABILITIES.keys())
            else:
                return "%s" % (PLACEMENT_CAPABILITIES.get(nparams[0].strip(), ''))
        else:
            return ''

class UserDataHandler(object):

    def __init__(self, opts):
        self.opts = opts

    def _get_user_blob(self, **kwargs):
        blob_mp = {}
        blob_mp['hostname'] = kwargs.get('who', '')
        lines = []
        lines.append("#cloud-config")
        lines.append(yamlify(blob_mp))
        blob = "\n".join(lines)
        return blob.strip()

    def get_data(self, params, who):
        if not params:
            return self._get_user_blob(who=who)
        return ''


# Seem to need to use globals since can't pass 
# data into the request handlers instances...
# Puke!
meta_fetcher = None
user_fetcher = None


class Ec2Handler(BaseHTTPRequestHandler):

    def _get_versions(self):
        return "\n".join(EC2_VERSIONS)

    def log_message(self, format, *args):
        msg = "%s - %s" % (self.address_string(), format % (args))
        log.info(msg)

    def _find_method(self, path):
        # Puke! (globals)
        global meta_fetcher
        global user_fetcher
        func_mapping = {
            'user-data': user_fetcher.get_data,
            'meta-data': meta_fetcher.get_data,
        }
        segments = [piece for piece in path.split('/') if len(piece)]
        if not segments:
            return self._get_versions
        date = segments[0].strip().lower()
        if date not in EC2_VERSIONS:
            raise RuntimeError("Unknown date format %r" % date)
        look_name = segments[1].lower()
        if look_name not in func_mapping:
            raise RuntimeError("Unknown requested data %r" % look_name)
        base_func = func_mapping[look_name]
        who = self.address_string()
        return functools.partial(base_func, params=segments[2:], who=who)

    def _do_response(self):
        who = self.client_address
        log.info("Got a call from %s for path %s", who, self.path)
        try:
            func = self._find_method(self.path)
            log.info("Calling into func %s to get your data.", func)
            data = func()
            if not data:
                data = ''
            self.send_response(httplib.OK)
            self.send_header("Content-Type", "binary/octet-stream")
            self.send_header("Content-Length", len(data))
            log.info("Sending data (len=%s):\n%s", len(data), format_text(data))
            self.end_headers()
            self.wfile.write(data)
        except RuntimeError as e:
            log.exception("Error somewhere in the server.")
            self.send_error(httplib.INTERNAL_SERVER_ERROR, message=str(e))
        except IOError as e:
            log.exception("Error finding result data.")
            self.send_error(httplib.NOT_FOUND, message=str(e))

    def do_GET(self):
        self._do_response()

    def do_POST(self):
        self._do_response()


def setup_logging(log_level, format='%(levelname)s: @%(name)s : %(message)s'):
    root_logger = logging.getLogger()
    console_logger = logging.StreamHandler(sys.stdout)
    console_logger.setFormatter(logging.Formatter(format))
    root_logger.addHandler(console_logger)
    root_logger.setLevel(log_level)


def extract_opts():
    parser = OptionParser()
    parser.add_option("-p", "--port", dest="port", action="store", type=int, default=80,
                  help="port from which to serve traffic (default: %default)", metavar="PORT")
    (options, args) = parser.parse_args()
    out = dict()
    out['extra'] = args
    out['port'] = options.port
    return out


def setup_fetchers(opts):
    global meta_fetcher
    global user_fetcher
    meta_fetcher = MetaDataHandler(opts)
    user_fetcher = UserDataHandler(opts)


def run_server():
    # Using global here since it doesn't seem like we 
    # can pass opts into a request handler constructor...
    opts = extract_opts()
    setup_logging(logging.DEBUG)
    setup_fetchers(opts)
    log.info("CLI opts: %s", opts)
    server = HTTPServer(('0.0.0.0', opts['port']), Ec2Handler)
    sa = server.socket.getsockname()
    log.info("Serving server on %s using port %s ...", sa[0], sa[1])
    server.serve_forever()


if __name__ == '__main__':
    run_server()