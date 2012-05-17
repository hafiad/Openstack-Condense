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

import email
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase

STARTS_WITH_MAPPINGS = {
    '#cloud-config': 'text/cloud-config',
}


# if 'text' is compressed return decompressed otherwise return it
def _decomp_str(text):
    import StringIO
    import gzip
    try:
        uncomp = gzip.GzipFile(None, "rb", 1, StringIO.StringIO(text)).read()
        return uncomp
    except:
        return text


def _multi_part_count(outermsg, newcount=None):
    """
    Return the number of attachments to this MIMEMultipart by looking
    at its 'Number-Attachments' header.
    """
    nfield = 'Number-Attachments'
    if nfield not in outermsg:
        outermsg[nfield] = "0"

    if newcount != None:
        outermsg.replace_header(nfield, str(newcount))

    return int(outermsg.get('Number-Attachments', 0))


def _attach_part(outermsg, part):
    """
    Attach an part to an outer message. outermsg must be a MIMEMultipart.
    Modifies a header in outermsg to keep track of number of attachments.
    """
    cur = _multi_part_count(outermsg)
    if not part.get_filename(None):
        part.add_header('Content-Disposition', 'attachment',
            filename='part-%03d' % (cur + 1))
    outermsg.attach(part)
    _multi_part_count(outermsg, cur + 1)


def _type_from_startswith(payload, default=None):
    # slist is sorted longest first
    slist = sorted(STARTS_WITH_MAPPINGS.keys(), key=lambda e: 0 - len(e))
    for sstr in slist:
        if payload.startswith(sstr):
            return STARTS_WITH_MAPPINGS[sstr]
    return default


def _process(msg, appendmsg=None):
    if appendmsg == None:
        appendmsg = MIMEMultipart()

    for part in msg.walk():

        # multipart/* are just containers
        if part.get_content_maintype() == 'multipart':
            continue

        ctype = None
        ctype_orig = part.get_content_type()
        payload = part.get_payload(decode=True)

        if ctype_orig == "text/plain":
            ctype = _type_from_startswith(payload)

        if ctype is None:
            ctype = ctype_orig

        if 'Content-Type' in msg:
            msg.replace_header('Content-Type', ctype)
        else:
            msg['Content-Type'] = ctype

        _attach_part(appendmsg, part)


def _message_from_string(data, headers=None):
    if headers is None:
        headers = {}
    if "mime-version:" in data[0:4096].lower():
        msg = email.message_from_string(data)
        for (key, val) in headers.items():
            if key in msg:
                msg.replace_header(key, val)
            else:
                msg[key] = val
    else:
        mtype = headers.get("Content-Type", "text/plain")
        maintype, subtype = mtype.split("/", 1)
        msg = MIMEBase(maintype, subtype, *headers)
        msg.set_payload(data)

    return msg


def preprocess_userdata(data):
    newmsg = MIMEMultipart()
    _process(_message_from_string(_decomp_str(data)), newmsg)
    return newmsg.as_string()


# callback is a function that will be called with (data, content_type,
# filename, payload)
def walk_userdata(istr, callback):

    partnum = 0
    for part in _message_from_string(istr).walk():

        # multipart/* are just containers
        if part.get_content_maintype() == 'multipart':
            continue

        ctype = part.get_content_type()
        if ctype is None:
            ctype = 'application/octet-stream'

        filename = part.get_filename()
        if not filename:
            filename = 'part-%03d' % partnum

        callback(ctype, filename, part.get_payload(decode=True))
        partnum = partnum + 1
