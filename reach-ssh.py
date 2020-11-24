import re
import os
import csv
import paramiko
# import logging

# logging.basicConfig()
# logging.getLogger("paramiko").setLevel(logging.INFO)

IP = ''
Port = ''
Username = ''
Password = ''
TTL = 15

with open('servers.csv', newline='') as csvfile:
    count = 1
    reader = csv.DictReader(csvfile)
    rows = []
    for row in reader:
        rows.append(row)
        print(f'{count}. {row["ServerName"]} - {row["IPAddress"]}')
        count += 1
    print('\nChoose server number or enter -1 to enter IP: ', end='')
    choice = int(input())
    IP = rows[choice - 1]['IPAddress']
    Port = rows[choice - 1]['Port']
    Username = rows[choice - 1]['Username']
    Password = rows[choice - 1]['Password']

    if choice == -1:
        print('Enter IP Address: ', end='')
        IP = input()
        Port = 22
        print('Enter username: ', end='')
        Username = input()
        print('Enter password: ', end='')
        Password = input()
        
print('\nDrag IP targets file: ', end='')
targetPath = input()
if targetPath == '': targetPath = 'IP_List.txt'

print(f'\nConnecting to {IP} as {Username}...\n')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(IP, username=Username, password=Password)

with open(targetPath, newline='') as targets:
    reachCSV = open(os.path.join('.', 'reports', f'{os.path.splitext(targets.name)[0]}_{IP}.csv'), 'w', newline='')
    writer = csv.writer(reachCSV)
    writer.writerow(["IP Address", "Ping Status", "Traceroute Status", "Traceroute Output"])
    for line in targets.readlines():
        line = line.strip()
        reachStatus = 'Reachable'
        pingStatus = 'Success'
        print(f'Pinging {line}\t: ', end='')
        chan = client.get_transport().open_session()
        chan.exec_command(f'ping -c1 -w1 {line}')
        if chan.recv_exit_status() == 1:
            print('Not Reachable, starting traceroute...')
            pingStatus = 'Failure'
        else:
            print('Reachable, starting traceroute...')
        stdin, stdout, stderr = client.exec_command(f'traceroute -w1 -nm {TTL} {line}')
        traceOut = ''
        for lin in stdout: traceOut +=  lin
        if not re.search(f'([0-9]+  {line}  [+-]?([0-9]*[.])?[0-9]+ ms)', traceOut, re.IGNORECASE):
            reachStatus = 'Not Reachable'
        writer.writerow([line, pingStatus, reachStatus, traceOut])
        
client.close()