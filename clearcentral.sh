#!/usr/bin/bash

echo > /etc/actimetre/central.log
echo > /etc/actimetre/acticentral.lock
echo {} > /etc/actimetre/actiservers.data
echo {} > /etc/actimetre/actimetres.data
chmod 666 *.data *.log
rm -f /etc/actimetre/history/Actim*.hist

ls -lRA

