import ipaddress
import socket
import subprocess
import platform
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_PING_HOSTS = 512  # redes mayores a /23 solo usan ARP


def ping(ip):
    system_name = platform.system().lower()

    if system_name == "windows":
        command = ["ping", "-n", "1", "-w", "150", str(ip)]
    else:
        command = ["ping", "-c", "1", "-W", "1", str(ip)]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False


def resolve_hostname(ip):
    try:
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(2)
        try:
            return socket.gethostbyaddr(str(ip))[0]
        finally:
            socket.setdefaulttimeout(old_timeout)
    except Exception:
        return "Desconocido"


def get_all_hosts(local_ip, subnet_mask):
    try:
        network = ipaddress.IPv4Network(f"{local_ip}/{subnet_mask}", strict=False)
        return list(network.hosts())
    except Exception:
        return []


def read_arp_table():
    system_name = platform.system().lower()
    arp_devices = []

    try:
        if system_name == "windows":
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stdout

            ip_matches = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3})", output)
            for ip in ip_matches:
                arp_devices.append(ip)

        else:
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stdout
            ip_matches = re.findall(r"\((\d{1,3}(?:\.\d{1,3}){3})\)", output)
            for ip in ip_matches:
                arp_devices.append(ip)

    except Exception:
        pass

    return list(dict.fromkeys(arp_devices))


def scan_with_ping(hosts, max_workers=64):
    active_ips = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(ping, ip): ip for ip in hosts}

        for future in as_completed(future_map):
            ip = future_map[future]
            try:
                if future.result():
                    active_ips.append(str(ip))
            except Exception:
                pass

    return active_ips


def scan_network(local_ip, subnet_mask):
    hosts = get_all_hosts(local_ip, subnet_mask)

    # Redes grandes (> /23): solo ARP para no bloquear demasiado tiempo
    if len(hosts) <= MAX_PING_HOSTS:
        ping_active_ips = scan_with_ping(hosts)
    else:
        ping_active_ips = []

    arp_ips = read_arp_table()

    combined_ips = set(ping_active_ips) | set(arp_ips)

    valid_ips = []
    try:
        network = ipaddress.IPv4Network(f"{local_ip}/{subnet_mask}", strict=False)
        for ip in combined_ips:
            try:
                if ipaddress.IPv4Address(ip) in network:
                    valid_ips.append(ip)
            except Exception:
                pass
    except Exception:
        valid_ips = list(combined_ips)

    sorted_ips = sorted(valid_ips, key=lambda x: tuple(map(int, x.split("."))))

    hostname_map = {}
    with ThreadPoolExecutor(max_workers=32) as executor:
        future_map = {executor.submit(resolve_hostname, ip): ip for ip in sorted_ips}
        for future in as_completed(future_map):
            ip = future_map[future]
            try:
                hostname_map[ip] = future.result(timeout=3)
            except Exception:
                hostname_map[ip] = "Desconocido"

    return [{"ip": ip, "hostname": hostname_map.get(ip, "Desconocido")} for ip in sorted_ips]
