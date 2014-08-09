#!/usr/bin/env bash
screen -dmS api ceph-rest-api -c /etc/ceph/ceph.conf --cluster ceph -i admin
