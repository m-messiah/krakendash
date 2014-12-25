from rest_framework.decorators import api_view
from rest_framework.reverse import reverse
from rest_framework.response import Response
from django.conf import settings
from cephclient import wrapper
from humanize import filesize
from collections import Counter
import json
import re
import os

"""
API Endpoint that grabs the cluster data
"""
#get_data = wrapper.CephWrapper(endpoint=settings.CEPH_BASE_URL)

get_data = wrapper.CephWrapper(endpoint=settings.CEPH_BASE_URL)

"""
Master API view that has all sublinks
"""
@api_view(['GET'])
def api(request, format=None):
    return Response({"clusters-url": reverse("clusters", request=request),
                    "health-url": reverse("cluster-health", request=request),
                    "status-url": reverse("cluster-status", request=request)})

"""
Master clusters view that just has hyperlinks to the subviews for now
"""
@api_view(['GET'])
def clusters(request, format=None):
    return Response({"health-url": reverse("cluster-health", request=request),
                    "status-url": reverse("cluster-status", request=request)})

"""
Get Health data about the cluster
"""
@api_view(['GET'])
def health(request, format=None):
    health_response, cluster_health = get_data.health(body='json')
    return Response(cluster_health)

"""
Get Status data about the cluster
"""
@api_view(['GET'])
def status(request, format=None):
    status_response, cluster_status = get_data.status(body='json')
    return Response(cluster_status)

"""
Get overview of the cluster
"""
@api_view(['GET'])
def overview(request, format=None):
    buckets_list = json.loads(os.popen("radosgw-admin buckets list").read())
    users_stat = {}
    for bucket in buckets_list:
        bucket_stat = json.loads(
            os.popen("radosgw-admin bucket stats --bucket='{0}'"
                     .format(bucket)
            ).read())
        if bucket_stat["owner"] in users_stat:
            users_stat[bucket_stat["owner"]][bucket] = bucket_stat
        else:
            users_stat[bucket_stat["owner"]] = {bucket: bucket_stat}

    #External Ceph REST API calls
    status_response, cluster_status = get_data.status(body='json')
    health_response, cluster_health = get_data.health(body='json')
    pg_response, pg_stat = get_data.pg_stat(body='json')
    osd_response, osd_dump = get_data.osd_dump(body='json')
    osd_perf_response, osd_perf = get_data.osd_perf(body='json')
    #General Health status lookup
    health_lookup = {'HEALTH_OK':"OK", 'HEALTH_WARN':"WARN"}
    # pg states lookups
    pg_warn_status = re.compile("(creating|degraded|replay|splitting|scrubbing|repair|recovering|backfill|wait-backfill|remapped)")
    pg_crit_status = re.compile("(down|inconsistent|incomplete|stale|peering)")
    pg_ok_status = re.compile("(active+clean)")
    pg_health_lookup = lambda x: "ok" if pg_ok_status.search(x) else "warn" if pg_warn_status.search(x) else "crit" if pg_warn_status.search(x)    else "na"
    #osd states lookups
    osd_up = re.compile("(?=.*exists)(?=.*up)")
    osd_down = re.compile("(?=.*exists)(?=.*autoout)")
    osd_health_lookup = lambda x: "ok" if osd_up.search(str(x)) else "warn" if osd_down.search(str(x)) else "crit"

    #pg activities lookups
    pg_activities_lookup = {'read_bytes_sec':"Read", 'write_bytes_sec':"write", 'op_per_sec': "Ops", 
        'recovering_objects_per_sec': "Recovering Objects", 'recovering_bytes_per_sec': 'Recovery Speed',
        'recovering_keys_per_sec': 'Recovering Keys'}
    #for testing since I have no activity
    #pg_activities_lookup = {'read_bytes_sec':"Read", 'bytes_total' : "Bytes", 'degraded_objects' : "Degraded"}


    #mon status data
    mons_status = filter(lambda x: x['health'] in health_lookup, 
        cluster_status['output']['health']['health']['health_services'][0]['mons'])
    mon_count = len(cluster_status['output']['monmap']['mons'])

    #pg status data
    pg_status = cluster_status['output']['pgmap']['pgs_by_state']

    #osd status data
    osd_status = osd_dump['output']['osds']

    #pg activities data
    pg_activities = cluster_status['output']['pgmap']


    #usage data
    usage_bytes_used = cluster_status['output']['pgmap']['bytes_used']
    usage_bytes_total = cluster_status['output']['pgmap']['bytes_total']
    usage_data_total = filesize.naturalsize(usage_bytes_total, binary=True).split()[0]
    usage_data_scale = filesize.naturalsize(usage_bytes_total).split()[1]
    response = {'health':{
                    'clusterHealth': {
                        'status': cluster_health['output']['overall_status'],
                        'statusDescription': (lambda x, y: "CRIT" if x not in y else y[x]
                            )(cluster_health['output']['overall_status'], health_lookup)
                    }
                },
                'status':{
                    'mons': dict(({'ok':0,'warn':0,'crit':mon_count-len(mons_status)}).items() + 
                                Counter(map(lambda x: health_lookup[x['health']].lower(), mons_status)).items())
                    ,
                    'pgs': dict(({'ok':0,'warn':0,'crit':0}).items() + 
                            reduce(lambda y,z: y.update(z) if y else {},
                                map(lambda x: {pg_health_lookup(x['state_name']).lower(): x['count']}, pg_status)).items())
                    ,
                    'osds': dict(({'ok':0,'warn':0,'crit':mon_count-len(mons_status)}).items() +
                                Counter(map(lambda x: osd_health_lookup(x['state']).lower(), osd_status)).items())
                },
                'usage':{
                    'clusterBytesUsed':usage_bytes_used,
                    'clusterBytesAvail':usage_bytes_total-usage_bytes_used,
                    'clusterBytesTotal':usage_bytes_total,
                    'clusterDataUsed': round(float(usage_bytes_used)/pow(1024, 
                        filesize.suffixes['decimal'].index(usage_data_scale)+1), 1),
                    'clusterDataAvail':round(float(usage_bytes_total-usage_bytes_used)/pow(1024, 
                        filesize.suffixes['decimal'].index(usage_data_scale)+1), 1),
                    'clusterDataTotal': usage_data_total,
                    'clusterDataScale': usage_data_scale

                },
                'activities':reduce(lambda y, z: dict(y.items()+z.items()), 
                    map(lambda x: {x: pg_activities.get(x)} if x in pg_activities else {},pg_activities_lookup)),
                'pg_states': reduce(lambda y, z: dict(y.items()+z.items()),
                    map(lambda x: {x['state_name']:x['count']}, pg_status)),
                'osd_states': Counter(map(lambda x: '+'.join(x['state']), osd_status)),
                'users': users_stat
            }

    return Response(response)
