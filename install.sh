#!/usr/bin/bash

systemctl stop acticentral.timer
systemctl stop acticentral-daily.timer
systemctl stop acticentral-weekly.timer

mkdir /etc/actimetre
mkdir /etc/actimetre/history
mkdir /etc/actimetre/daily
mkdir /etc/actimetre/weekly
mkdir /var/www/cgi-bin
mkdir /var/www/html/images
mkdir /etc/matplotlib
chmod 777 /etc/matplotlib

cp clear*.sh /etc/actimetre
cp cgi-bin/acticentral.py /var/www/cgi-bin/acticentral.py
cp html/*.html html/*.svg /var/www/html/

cd /var/www
chown -R www-data:www-data *
chmod -R 777 *

cd /etc/actimetre
echo > central.log
echo > acticentral.lock
chown -R www-data:www-data . *
chmod -R 777 . *

cp *.service /etc/systemd/system/
cp *.timer /etc/systemd/system/

systemctl daemon-reload
systemctl enable acticentral.timer
systemctl start acticentral.timer
systemctl enable acticentral-daily.timer
systemctl start acticentral-daily.timer
systemctl enable acticentral-weekly.timer
systemctl start acticentral-weekly.timer
