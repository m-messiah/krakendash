#!/usr/bin/env bash
screen -dmS django python krakendash/manage.py runserver 0.0.0.0:8000 || scl enable python27 'python krakendash/manage.py runserver 0.0.0.0:8000' > kraken.log 2>&1 &
