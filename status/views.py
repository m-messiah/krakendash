# Copyright (c) 2013,2014 Donald Talton
# All rights reserved.

# Redistribution and use in source and binary forms,
# with or without modification,
# are permitted provided that the following conditions are met:

# Redistributions of source code must retain the above copyright notice, this
#  list of conditions and the following disclaimer.

# Redistributions in binary form must reproduce the above copyright notice, this
#  list of conditions and the following disclaimer in the documentation and/or
#  other materials provided with the distribution.

# Neither the name of Donald Talton nor the names of its
#  contributors may be used to endorse or promote products derived from
#  this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
# OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from subprocess import check_output
import re
import json

from django.shortcuts import render_to_response
from django.shortcuts import render
from django.shortcuts import redirect
from django.conf import settings
from cephclient import wrapper
import requests
from humanize import filesize


def req(url):
    """
    The main request builder
    """
    headers = {'Accept': 'application/json'}
    timeout = 10
    r = requests.get(url, headers=headers, timeout=timeout)
    response_json = r.text
    return response_json


def home(request):
    """
    Main dashboard, Overall cluster health and status
    """
    ceph = wrapper.CephWrapper(endpoint=settings.CEPH_BASE_URL)

    cresp, cluster_health = ceph.health(body='json')
    sresp, cluster_status = ceph.status(body='json')

    # Monitors
    all_mons = cluster_status['output']['monmap']['mons']
    up_mons = (cluster_status['output']['health']['health']
                             ['health_services'][0]['mons'])
    total_mon_count = len(all_mons)
    mons_ok = 0
    mons_warn = 0
    mons_crit = 0

    for mon in up_mons:
        if mon['health'] == "HEALTH_OK":
            mons_ok += 1
        else:
            mons_warn += 1

    mons_crit = total_mon_count - (mons_ok + mons_warn)

    # Activity
    pgmap = cluster_status['output']['pgmap']
    activities = {}
    if 'read_bytes_sec' in pgmap:
        activities['Read'] = filesize.naturalsize(pgmap.get('read_bytes_sec'))
    if 'write_bytes_sec' in pgmap:
        activities['Write'] = filesize.naturalsize(
            pgmap.get('write_bytes_sec'))
    if 'op_per_sec' in pgmap:
        activities['Ops'] = pgmap.get('op_per_sec')
    if 'recovering_objects_per_sec' in pgmap:
        activities['Recovering Objects'] = pgmap.get(
            'recovering_objects_per_sec')
    if 'recovering_bytes_per_sec' in pgmap:
        activities['Recovery Speed'] = filesize.naturalsize(
            pgmap.get('recovering_bytes_per_sec'))
    if 'recovering_keys_per_sec' in pgmap:
        activities['Recovering Keys'] = pgmap.get('recovering_keys_per_sec')

    # Get a rough estimate of cluster free space. Is this accurate ?
    presp, pg_stat = ceph.pg_stat(body='json')
    bytes_total = cluster_status['output']['pgmap']['bytes_total']
    bytes_used = cluster_status['output']['pgmap']['bytes_used']

    data_avail = str(
        float(filesize.naturalsize(bytes_total).split()[0]) * 1024)
    data_scale = filesize.naturalsize(bytes_total / 1024).split()[1]
    scale = filesize.suffixes['decimal'].index(data_scale) + 1
    data_used = round(float(bytes_used)/pow(1024.0, scale), 1)
    # pgs
    pg_statuses = cluster_status['output']['pgmap']

    pg_ok = 0
    pg_warn = 0
    pg_crit = 0

    # pg states
    pg_warn_status = re.compile("(creating|degraded|replay|splitting|"
                                "scrubbing|repair|recovering|backfill"
                                "|wait-backfill|remapped)")
    pg_crit_status = re.compile("(down|inconsistent|incomplete|stale|peering)")

    for state in pg_statuses['pgs_by_state']:
        if state['state_name'] == "active+clean":
            pg_ok = pg_ok + state['count']

        elif pg_warn_status.search(state['state_name']):
            pg_warn = pg_warn + state['count']

        elif pg_crit_status.search(state['state_name']):
            pg_crit = pg_crit + state['count']

    # pg statuses
    pg_states = dict()

    for state in pg_statuses['pgs_by_state']:
        pg_states[state['state_name']] = state['count']

    # osds
    dresp, osd_dump = ceph.osd_dump(body='json')
    osd_state = osd_dump['output']['osds']

    osds_ok = 0
    osds_warn = 0
    osds_crit = 0

    # Possible states are: exists, up, autoout, new, ???
    osd_up = re.compile("(?=.*exists)(?=.*up)")
    osd_down = re.compile("(?=.*exists)(?=.*autoout)")

    for osd_status in osd_state:
        if osd_up.search(str(osd_status['state'])):
            osds_ok += 1
        elif osd_down.search(str(osd_status['state'])):
            osds_warn += 1
        else:
            osds_crit += 1

    # Users and stats
    buckets_list = json.loads(check_output(["radosgw-admin",
                                            "buckets",
                                            "list"]))
    users_stat = {}
    for bucket in buckets_list:
        try:
            bucket_stat = json.loads(
                check_output(["radosgw-admin",
                              "bucket", "stats",
                              "--bucket={0}".format(escape(bucket))]
                ))
            if bucket_stat["owner"] in users_stat:
                users_stat[
                    bucket_stat["owner"]
                ][bucket] = bucket_stat["usage"]["rgw.main"]
            else:
                users_stat[bucket_stat["owner"]] = {
                    bucket: bucket_stat["usage"]["rgw.main"]}
        except:
            pass
    return render_to_response('dashboard.html', locals())


def param(request, key):
    return key in request.GET


def escape(s):
    return s.replace("'", "'\\''").replace("#", "'\\#'").replace("&", "'\\&'")


def ops(request):
    users_list = json.loads(check_output(["radosgw-admin", "metadata",
                                          "list", "user"]))
    users = {}
    for username in users_list:
        users[username] = json.loads(
            check_output(["radosgw-admin", "user", "info",
                          "--uid={0}".format(username)]))
    return render(request, 'ops.html', locals())


def user_custom(request, user, func, argument):
    if func:
        func = func[1:]
    else:
        users = {user: json.loads(
            check_output(["radosgw-admin", "user", "info",
                          "--uid={0}".format(user)]))}
        return render_to_response('ops.html', locals())

    if argument:
        argument = argument[1:]

    if user == "0" and func == "adduser":
        if (param(request, 'newUid') and
                param(request, 'newName') and
                param(request, 'newEmail')):
            uid = request.GET['newUid']
            name = request.GET['newName']
            email = request.GET['newEmail']

            res = check_output(["radosgw-admin", "user", "create",
                                "--uid={0}".format(uid),
                                "--display-name={0}".format(name),
                                "--email={0}".format(email)])
    elif func == "suspend":
        if int(argument) > 0:
            res = check_output(["radosgw-admin", "user", "enable",
                                "--uid={0}".format(escape(user))])
        else:
            res = check_output(["radosgw-admin", "user", "suspend",
                                "--uid={0}".format(escape(user))])
    elif func == "newkey":
        res = check_output(["radosgw-admin", "user", "modify",
                            "--uid={0}".format(escape(user)),
                            "--gen-access-key"])
    elif func == "deletekey":
        res = check_output(["radosgw-admin", "key", "rm",
                            "--uid={0}".format(escape(user)),
                            "--access-key={0}".format(escape(argument))])
    elif func == "customize":
        pass
    return redirect("/krakendash/ops/")


def osd_details(request, osd_num):
    ceph = wrapper.CephWrapper(endpoint=settings.CEPH_BASE_URL)
    osd_num = int(osd_num)

    reponse, osd_dump = ceph.osd_dump(body='json')
    osd_disk_details = filter(
        lambda x: x['osd'] == int(osd_num), osd_dump['output']['osds']
    )[0]

    response, osd_perf = ceph.osd_perf(body='json')
    osd_disk_perf = filter(lambda x: x['id']  ==
            int(osd_num), osd_perf['output']['osd_perf_infos'])[0]

    return render_to_response('osd_details.html', locals())