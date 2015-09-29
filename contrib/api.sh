#!/usr/bin/env bash
screen -dmS api sudo ceph-rest-api -c /etc/ceph/ceph.conf --cluster ceph -i admin
