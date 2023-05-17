#!/usr/bin/bash

./killjava.sh
echo > /etc/actimetre/server.log
echo > /etc/actimetre/central.log
echo > /etc/actimetre/acticentral.lock
rm -f /media/actimetre/Data/*
rm -f /media/actimetre/Repo/*
echo {} > /etc/actimetre/registry.data
echo {} > /etc/actimetre/actiservers.data
echo {} > /etc/actimetre/actimetres.data
echo {} > /etc/actimetre/self.data
echo {} > /etc/actimetre/meta.data
rm -f /etc/actimetre/acticentral.pid
