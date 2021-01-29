import argparse
import re
import os
import csv
import threading
from concurrent.futures import ThreadPoolExecutor, wait
import time
from paramiko import transport, SSHClient, AutoAddPolicy

# import logging

# logging.basicConfig()
# logging.getLogger("paramiko").setLevel(logging.INFO)


def ping(client, IPp):
    pingStatus = "Reachable"
    chan = client.get_transport().open_session()
    if not args.use_timeout:
        ping_command = f"ping -c {args.count} -w {args.timeout} {IPp}"
    else:
        ping_command = f"timeout {args.timeout} ping -c {args.count} {IPp}"
    chan.exec_command(ping_command)
    if chan.recv_exit_status() == 0:
        print(f"{IPp}\t is pinging from \t{IP}", end='')
    else:
        print(f"{IPp}\t is not pinging from \t{IP}", end='')
        pingStatus = "Not Reachable"
    return pingStatus


def traceroute(client, TTL, IPp):
    if args.traceroute:
        print(f"Starting traceroute to {IPp}\t from {IP}...")
    reachStatus = "Reachable"
    _, stdout, _ = client.exec_command(f"traceroute -n -N 32 -q 1 -w 1 -m {TTL} {IPp}")
    traceOut = ""
    for lin in stdout:
        traceOut += lin
    if len(re.findall(f'{IPp}  ', traceOut)) < 1:
        reachStatus = "Not Reachable"
    return [reachStatus, traceOut]


def getReachability(ssh_client, writer, IPp):
    global ipcount
    ipcount += 1
    if not args.ping ^ args.traceroute:
        pingStatus = ping(client, IPp)
        if args.trace_on_ping and pingStatus == "Reachable":
            reachStatus, traceOut = ["NA", "NA"]
            print()
        else:
            print(", starting traceroute...")
            reachStatus, traceOut = traceroute(client, args.TTL, IPp)
        writer.writerow([IPp, pingStatus, reachStatus, traceOut])
    elif args.traceroute:
        reachStatus, traceOut = traceroute(client, args.TTL, IPp)
        writer.writerow([IPp, reachStatus, traceOut])
    else:
        pingStatus = ping(client, IPp)
        print()
        writer.writerow([IPp, pingStatus])

timerStop = False

def timeCounter():
    global timerStop
    global ipcount
    while True:
        if timerStop:
            break
        for i in range(5):
            if timerStop:
                break
            time.sleep(1)
            if i == 4:
                currDur = time.perf_counter() - timeStart
                print(f"\n\n{round(currDur)}s have elapsed. {ipcount} IPs completed, speed {round(ipcount/round(currDur), 3)} IPs/sec.\n\n")

IP = ""
Port = ""
Username = ""
Password = ""
ipcount = 0

# =====================================================================================================

parser = argparse.ArgumentParser(
    description="Generate a reachability report for a list of IPs (using ping and traceroute) from any server over SSH."
)
parser.add_argument(
    "-p", "--ping", help="only check reachability through ping", action="store_true", default=False
)
parser.add_argument(
    "-t",
    "--traceroute",
    help="only check reachability through traceroute",
    action="store_true",
    default=False,
)
parser.add_argument(
    "--TTL", help="maximum hops for traceroute", type=int, choices=range(10, 50, 5), default=20
)
parser.add_argument(
    "-w", "--timeout", help="timeout for ping", type=float, default=6
)
parser.add_argument(
    "-c", "--count", help="ping count", type=int, default=3
)
parser.add_argument(
    "--use-timeout", help="use timeout binary for ping", action="store_true", default=False
)
parser.add_argument("-z", "--trace-on-ping", help="get traceroute only if ping fails", action="store_true", default=False)
args = parser.parse_args()

# =====================================================================================================

with open("servers.csv", newline="") as csvfile:
    count = 1
    reader = csv.DictReader(csvfile)
    rows = []
    for row in reader:
        rows.append(row)
        print(f'{count}. {row["ServerName"]} - {row["IPAddress"]}')
        count += 1
    print("\nChoose server number or enter -1 to enter IP: ", end="")
    choice = int(input())
    IP = rows[choice - 1]["IPAddress"]
    Port = rows[choice - 1]["Port"]
    Username = rows[choice - 1]["Username"]
    Password = rows[choice - 1]["Password"]

    if choice == -1:
        print("Enter IP Address: ", end="")
        IP = input()
        Port = 22
        print("Enter username: ", end="")
        Username = input()
        print("Enter password: ", end="")
        Password = input()

print("\nDrag IP targets file: ", end="")
targetPath = input()
if targetPath == "":
    targetPath = "IP_List.txt"

print(f"\nConnecting to {IP} as {Username}...\n")

with SSHClient() as client:
    client.set_missing_host_key_policy(AutoAddPolicy())
    client.connect(IP, username=Username, password=Password)

    timeStart = time.perf_counter()

    with open(targetPath, newline="") as targets:
        with open(os.path.join(".", "reports", f"{os.path.splitext(targets.name)[0]}_{IP}.csv"),"w",newline="") as reachCSV:
            writer = csv.writer(reachCSV)
            if not args.ping ^ args.traceroute:
                writer.writerow(["IP Address", "Ping Status", "Traceroute Status", "Traceroute Output"])
            elif args.traceroute:
                writer.writerow(["IP Address", "Traceroute Status", "Traceroute Output"])
            else:
                writer.writerow(["IP Address", "Ping Status"])

            threading.Thread(target=timeCounter).start()

            with ThreadPoolExecutor(max_workers=5) as executor:
                result_futures = list(
                    map(
                        lambda line: executor.submit(getReachability, client, writer, line.strip()),
                        targets.readlines(),
                    )
                )
                wait(result_futures, timeout=None, return_when='ALL_COMPLETED')

timerStop = True
timeEnd = time.perf_counter()
sec = timeEnd - timeStart
input("Ping/Traceroute completed in {:.0f}s...\n".format(round(sec, 2)))