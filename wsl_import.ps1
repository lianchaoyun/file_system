wsl --shutdown
wsl --unregister Ubuntu
wsl --import Ubuntu "E:\game\linux\ubuntu_wsl" E:\game\backup\ubuntu_backup_0.tar
wsl --distribution Ubuntu --user root
wsl -d Ubuntu -u root
pause
