#!/usr/bin/bash

cp clear*.sh /etc/actimetre
cp cgi-bin/acticentral.py /var/www/cgi-bin/acticentral.py
cp html/*.html html/*.svg /var/www/html/

cd /var/www
chown www-data:www-data html html/images html/*.html cgi-bin/acticentral.py
chmod 775 html/index.html cgi-bin/acticentral.py
chmod 777 html html/images

cd /etc/actimetre
chown www-data:www-data . *
chmod 777 . *.sh history

echo > central.log
echo > acticentral.lock
rm -f acticentral.pid
chmod 666 *.log *.data *.lock

sudo systemctl stop acticentral.timer
cp acticentral.service /etc/systemd/system/
cp acticentral.timer /etc/systemd/system/

sudo systemctl enable acticentral.timer
sudo systemctl start acticentral.timer
