#!/usr/bin/bash

mkdir /etc/actimetre
mkdir /media/actimetre
mkdir /media/actimetre/Data
mkdir /media/actimetre/Repo
mkdir /var/www/cgi-bin

cp actimetre.conf clear2.sh killjava.sh run.sh /etc/actimetre
cp cgi-bin/acticentral.py /var/www/cgi-bin/acticentral.py
cp html/index.html html/error.html /var/www/html/

cd /media/actimetre
chown www-data:www-data . Data Repo
chmod 777 . Data Repo
rm -f /media/actimetre/Data/*
rm -f /media/actimetre/Repo/*

cd /var/www
chown www-data:www-data html/index.html html/error.html cgi-bin/acticentral.py
chmod 775 html/index.html cgi-bin/acticentral.py

cd /etc/actimetre
chown www-data:www-data .
chmod 777 . *.sh
echo > server.log
echo > central.log
echo > acticentral.lock
echo {} > registry.data
echo {} > actiservers.data
echo {} > actimetres.data
echo {} > self.data
echo {} > meta.data
rm -f acticentral.pid
chmod 666 *.log *.data *.lock *.conf
