import argparse
import re
import os
import csv
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor, wait
import time


def ping(IPp):
    pingStatus = "Reachable"
    ping_command = ""
    if not args.use_timeout:
        if os.name == "nt":
            ping_command = f"ping -n {args.count} -w {args.timeout} {IPp}"
        else:
            ping_command = f"ping -c {args.count} -w {args.timeout} {IPp}"
    else:
        ping_command = f"timeout {args.timeout} ping -c {args.count} {IPp}"
    ping_command_out = subprocess.run(ping_command.split(" "), stdout=subprocess.PIPE, text=True)
    if ping_command_out.returncode == 0:
        print(f"{IPp}\t is pinging from \t{IP}", end="")
    else:
        print(f"{IPp}\t is not pinging from \t{IP}", end="")
        pingStatus = "Not Reachable"
    return pingStatus


def traceroute(TTL, IPp):
    if args.traceroute:
        print(f"Starting traceroute to {IPp}\t from {IP}...")
    reachStatus = "Reachable"
    if os.name == "nt":
        trace_command_out = subprocess.run(f"tracert -d -w 1 -h {TTL} {IPp}", stdout=subprocess.PIPE, text=True)
    else:
        trace_command_out = subprocess.run(
            f"traceroute -I -n -N 32 -q 1 -w 1 -m {TTL} {IPp}".split(" "), stdout=subprocess.PIPE, text=True
        )
    traceOut = trace_command_out.stdout
    if len(re.findall(f"{IPp}  ", traceOut)) < 1 and os.name != 'nt':
        reachStatus = "Not Reachable"
    elif len(re.findall(f"{IPp}", traceOut)) < 2 and os.name == 'nt':
        reachStatus = "Not Reachable"
    return [reachStatus, traceOut]


def getReachability(writer, IPp):
    global ipcount
    if not args.ping ^ args.traceroute:
        pingStatus = ping(IPp)
        if not args.always_trace and pingStatus == "Reachable":
            reachStatus, traceOut = ["NA", "NA"]
            print()
        else:
            print(", starting traceroute...")
            reachStatus, traceOut = traceroute(args.TTL, IPp)
        writer.writerow([IPp, pingStatus, reachStatus, traceOut])
    elif args.traceroute:
        reachStatus, traceOut = traceroute(args.TTL, IPp)
        writer.writerow([IPp, reachStatus, traceOut])
    else:
        pingStatus = ping(IPp)
        print()
        writer.writerow([IPp, pingStatus])
    ipcount += 1


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
                print(
                    f"\n\n{round(currDur)}s have elapsed. {ipcount} IPs completed, speed {round(ipcount/round(currDur), 3)} IPs/sec.\n\n"
                )


IP = "localhost"
Port = ""
Username = ""
Password = ""
ipcount = 0

# =====================================================================================================

parser = argparse.ArgumentParser(description="Generate a reachability report for a list of IPs (using ping and traceroute).")
parser.add_argument("-p", "--ping", help="only check reachability through ping", action="store_true", default=False)
parser.add_argument(
    "-t",
    "--traceroute",
    help="only check reachability through traceroute",
    action="store_true",
    default=False,
)
parser.add_argument("--TTL", help="maximum hops for traceroute", type=int, choices=range(10, 50, 5), default=20)
parser.add_argument("-w", "--timeout", help="timeout for ping", type=float, default=1)
parser.add_argument("-c", "--count", help="ping count", type=int, default=1)
parser.add_argument("--use-timeout", help="use timeout binary for ping (only linux)", action="store_true", default=False)
parser.add_argument("-z", "--always-trace", help="always get traceroute", action="store_true", default=False)
args = parser.parse_args()

# =====================================================================================================

print("\nDrag IP targets file: ", end="")
targetPath = input()
if targetPath == "":
    targetPath = "IP_List.txt"

timeStart = time.perf_counter()

with open(targetPath, newline="") as targets:
    with open(os.path.join(".", "reports", f"{os.path.splitext(targets.name)[0]}_{IP}.csv"), "w", newline="") as reachCSV:
        writer = csv.writer(reachCSV)
        if not args.ping ^ args.traceroute:
            writer.writerow(["IP Address", "Ping Status", "Traceroute Status", "Traceroute Output"])
        elif args.traceroute:
            writer.writerow(["IP Address", "Traceroute Status", "Traceroute Output"])
        else:
            writer.writerow(["IP Address", "Ping Status"])

        threading.Thread(target=timeCounter).start()

        with ThreadPoolExecutor(max_workers=100) as executor:
            result_futures = list(
                map(
                    lambda line: executor.submit(getReachability, writer, line.strip()),
                    targets.readlines(),
                )
            )
            wait(result_futures, timeout=None, return_when="ALL_COMPLETED")

timerStop = True
timeEnd = time.perf_counter()
sec = timeEnd - timeStart
input("Ping/Traceroute completed in {:.0f}s...\n".format(round(sec, 2)))
