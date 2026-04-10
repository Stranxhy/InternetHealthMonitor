import socket
import subprocess
import platform
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from network.scanner import scan_network


def get_local_ip():
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)

        if local_ip.startswith("127."):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
            finally:
                s.close()

        return local_ip
    except Exception:
        return "No disponible"


def get_default_gateway():
    system_name = platform.system().lower()

    try:
        if system_name == "windows":
            result = subprocess.run(
                ["ipconfig"],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stdout

            lines = output.splitlines()
            for i, line in enumerate(lines):
                if "Puerta de enlace predeterminada" in line or "Default Gateway" in line:
                    match_same_line = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", line)
                    if match_same_line:
                        return match_same_line.group(1)

                    for j in range(i + 1, min(i + 4, len(lines))):
                        next_line_match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", lines[j])
                        if next_line_match:
                            return next_line_match.group(1)

            return "No disponible"

        result = subprocess.run(
            ["ip", "route"],
            capture_output=True,
            text=True,
            timeout=10
        )
        output = result.stdout
        match = re.search(r"default via ([\d.]+)", output)
        return match.group(1) if match else "No disponible"

    except Exception:
        return "No disponible"


def get_subnet_mask():
    system_name = platform.system().lower()

    try:
        if system_name == "windows":
            result = subprocess.run(
                ["ipconfig"],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stdout

            match = re.search(r"Máscara de subred[ .:]*([\d.]+)", output)
            if not match:
                match = re.search(r"Subnet Mask[ .:]*([\d.]+)", output)

            return match.group(1) if match else "255.255.255.0"

        result = subprocess.run(
            ["ip", "addr"],
            capture_output=True,
            text=True,
            timeout=10
        )
        output = result.stdout
        match = re.search(r"inet\s+\d+\.\d+\.\d+\.\d+/(\d+)", output)
        if not match:
            return "255.255.255.0"

        prefix = int(match.group(1))
        mask = (0xffffffff >> (32 - prefix)) << (32 - prefix)
        return ".".join(str((mask >> i) & 255) for i in [24, 16, 8, 0])

    except Exception:
        return "255.255.255.0"


def ping_host(host, count=4):
    system_name = platform.system().lower()

    if system_name == "windows":
        command = ["ping", "-n", str(count), host]
    else:
        command = ["ping", "-c", str(count), host]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15
        )

        output = result.stdout + result.stderr

        return {
            "host": host,
            "reachable": result.returncode == 0,
            "avg_ms": extract_avg_ping(output, system_name),
            "packet_loss": extract_packet_loss(output, system_name),
            "raw_output": output
        }

    except Exception as e:
        return {
            "host": host,
            "reachable": False,
            "avg_ms": None,
            "packet_loss": None,
            "raw_output": str(e)
        }


def extract_avg_ping(output, system_name):
    try:
        if system_name == "windows":
            patterns = [
                r"Media = (\d+)ms",
                r"Promedio = (\d+)ms",
                r"Average = (\d+)ms",
                r"Mínimo = \d+ms, Máximo = \d+ms, Media = (\d+)ms",
                r"Minimum = \d+ms, Maximum = \d+ms, Average = (\d+)ms"
            ]

            for pattern in patterns:
                match = re.search(pattern, output, re.IGNORECASE)
                if match:
                    return int(match.group(1))
            return None

        match = re.search(r"= [\d.]+/([\d.]+)/[\d.]+/[\d.]+", output)
        return float(match.group(1)) if match else None

    except Exception:
        return None


def extract_packet_loss(output, system_name):
    try:
        if system_name == "windows":
            patterns = [
                r"(\d+)% perdidos",
                r"Lost = \d+ \((\d+)% loss\)",
                r"\((\d+)% loss\)"
            ]

            for pattern in patterns:
                match = re.search(pattern, output, re.IGNORECASE)
                if match:
                    return int(match.group(1))

            generic_match = re.search(r"\((\d+)%", output)
            return int(generic_match.group(1)) if generic_match else None

        match = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
        return float(match.group(1)) if match else None

    except Exception:
        return None


def ping_internet():
    """Prueba múltiples hosts y retorna el mejor resultado alcanzable."""
    hosts = ["8.8.8.8", "1.1.1.1", "google.com"]

    with ThreadPoolExecutor(max_workers=len(hosts)) as executor:
        futures = {executor.submit(ping_host, host): host for host in hosts}
        results = []
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception:
                pass

    reachable = [r for r in results if r["reachable"]]
    if reachable:
        return min(reachable, key=lambda r: r["avg_ms"] if r["avg_ms"] is not None else float("inf"))

    return {"host": "8.8.8.8", "reachable": False, "avg_ms": None, "packet_loss": None, "raw_output": ""}


def classify_connection(avg_ms, packet_loss):
    if avg_ms is None and packet_loss is None:
        return "No fue posible medir el rendimiento."

    if packet_loss is not None and packet_loss > 10:
        return "Conexión inestable por alta pérdida de paquetes."

    if avg_ms is None:
        return "Conexión detectada, pero no fue posible medir la latencia."

    if avg_ms < 50:
        return "Conexión estable."
    if avg_ms < 100:
        return "Conexión aceptable con latencia moderada."
    if avg_ms < 180:
        return "Conexión inestable o con posible congestión."
    return "Latencia alta. La conexión presenta problemas de rendimiento."


def generate_diagnosis(gateway, gateway_result, internet_result, device_count):
    gateway_available = gateway not in [None, "", "No disponible"]

    if gateway_available and not gateway_result["reachable"]:
        return (
            "No hay respuesta del gateway. Posible problema en la red local, "
            "en el hotspot o en el router."
        )

    if gateway_available and gateway_result["reachable"] and not internet_result["reachable"]:
        return (
            "La red local responde correctamente, pero no hay acceso a internet. "
            "El problema parece estar en la salida a internet del hotspot o proveedor."
        )

    if not gateway_available and internet_result["reachable"]:
        return (
            "Hay acceso a internet, pero no fue posible detectar el gateway. "
            "La conexión parece funcional."
        )

    if not internet_result["reachable"]:
        return (
            "No se detectó conexión a internet. Verifica el hotspot, los datos móviles "
            "o la conexión del proveedor."
        )

    quality_text = classify_connection(
        internet_result["avg_ms"],
        internet_result["packet_loss"]
    )

    if device_count <= 1:
        visibility_note = (
            " Se detectaron muy pocos dispositivos visibles; la red podría tener "
            "restricciones de descubrimiento o aislamiento entre clientes."
        )
    else:
        visibility_note = ""

    if gateway_available and gateway_result["reachable"] and internet_result["reachable"]:
        return (
            "La red local y la salida a internet responden correctamente. "
            f"{quality_text}{visibility_note}"
        )

    return f"{quality_text}{visibility_note}"


def _sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def run_analysis_stream():
    """Generador que emite eventos SSE a medida que cada paso del análisis completa."""

    # Paso 1: info de red (rápido, local)
    local_ip = get_local_ip()
    gateway = get_default_gateway()
    subnet_mask = get_subnet_mask()
    yield _sse("network_info", {
        "local_ip": local_ip,
        "gateway": gateway,
        "subnet_mask": subnet_mask
    })

    # Paso 2: tareas paralelas
    gateway_result = {"host": gateway, "reachable": False, "avg_ms": None, "packet_loss": None}
    internet_result = {"host": "8.8.8.8", "reachable": False, "avg_ms": None, "packet_loss": None}
    devices = []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        if gateway != "No disponible":
            futures[executor.submit(ping_host, gateway)] = "gateway"
        futures[executor.submit(ping_internet)] = "internet"
        if local_ip != "No disponible":
            futures[executor.submit(scan_network, local_ip, subnet_mask)] = "scan"

        for future in as_completed(futures):
            task = futures[future]
            try:
                result = future.result()
            except Exception:
                result = None

            if task == "gateway":
                if result:
                    gateway_result = result
                yield _sse("gateway", {
                    "reachable": gateway_result["reachable"],
                    "latency_ms": gateway_result["avg_ms"],
                    "packet_loss": gateway_result["packet_loss"]
                })

            elif task == "internet":
                if result:
                    internet_result = result
                yield _sse("internet", {
                    "reachable": internet_result["reachable"],
                    "latency_ms": internet_result["avg_ms"],
                    "packet_loss": internet_result["packet_loss"]
                })

            elif task == "scan":
                devices = result or []
                yield _sse("scan", {"devices": devices})

    # Paso 3: diagnóstico final
    diagnosis = generate_diagnosis(gateway, gateway_result, internet_result, len(devices))
    yield _sse("done", {"diagnosis": diagnosis})
