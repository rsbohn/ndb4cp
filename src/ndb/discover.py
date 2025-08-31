from __future__ import annotations

import json
import re
import urllib.request
import gzip
import base64
from urllib.error import URLError, HTTPError
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
import socket


@dataclass
class DeviceInfo:
    uid: str
    hostname: Optional[str]
    ip_address: Optional[str]
    board: Optional[str]
    mcu: Optional[str]
    circuitpython: Optional[str]
    web_api_version: Optional[int]

    def to_record(self, *, seed: str, label: Optional[str] = None) -> Dict[str, Any]:
        rec: Dict[str, Any] = {
            "uid": self.uid,
            "hostname": self.hostname,
            "ip_address": self.ip_address,
            "board": self.board,
            "mcu": self.mcu,
            "circuitpython": self.circuitpython,
            "web_api_version": self.web_api_version,
            "source": "web_device_info",
            "seed": seed,
        }
        if label:
            rec["label"] = label
        return rec


def _strip_tags(text: str) -> str:
    # Replace tags with newlines to preserve line structure
    no_tags = re.sub(r"<[^>]+>", "\n", text)
    # Normalize Windows line endings
    no_tags = no_tags.replace("\r\n", "\n")
    # Collapse excessive blank lines
    no_tags = re.sub(r"\n{3,}", "\n\n", no_tags)
    return no_tags


def parse_device_info(text: str) -> Optional[DeviceInfo]:
    t = _strip_tags(text)
    patterns = {
        "board": re.compile(r"Board:\s*(.+)"),
        "mcu": re.compile(r"MCU:\s*(.+)"),
        "circuitpython": re.compile(r"CircuitPython:\s*([^\n]+)"),
        "ip": re.compile(r"IP:\s*([^\s\n]+)"),
        "hostname": re.compile(r"Hostname:\s*([^\s\n]+)"),
        "uid": re.compile(r"UID:\s*([A-Za-z0-9_-]+)"),
        "web_api_version": re.compile(r"Web API Version:\s*(\d+)"),
    }

    def find(name: str) -> Optional[str]:
        m = patterns[name].search(t)
        return m.group(1).strip() if m else None

    uid = find("uid")
    if not uid:
        return None
    hostname = find("hostname")
    ip = find("ip")
    board = find("board")
    mcu = find("mcu")
    cp = find("circuitpython")
    wav = find("web_api_version")
    wav_i = int(wav) if wav and wav.isdigit() else None

    return DeviceInfo(
        uid=uid,
        hostname=hostname,
        ip_address=ip,
        board=board,
        mcu=mcu,
        circuitpython=cp,
        web_api_version=wav_i,
    )


def parse_version_json(text: str) -> Optional[DeviceInfo]:
    try:
        obj = json.loads(text)
    except Exception:
        return None

    def pick(*keys):
        for k in keys:
            v = obj.get(k)
            if v is not None and v != "":
                return v
        return None

    uid = pick("uid", "UID", "device_uid")
    hostname = pick("hostname", "host", "HostName", "device_name")
    ip = pick("ip", "IP", "ip_address")
    board = pick("board", "Board", "board_name")
    mcu = pick("mcu", "MCU", "chip", "cpu")
    cp = pick("circuitpython", "CircuitPython", "version", "circuitpython_version")
    wav = pick("web_api_version", "WebAPIVersion", "web_api")
    try:
        wav_i = int(wav) if wav is not None else None
    except Exception:
        wav_i = None

    if not uid:
        return None
    return DeviceInfo(
        uid=uid,
        hostname=hostname,
        ip_address=ip,
        board=board,
        mcu=mcu,
        circuitpython=cp,
        web_api_version=wav_i,
    )


def _http_get(url: str, timeout: float, *, password: Optional[str] = None) -> Optional[str]:
    headers = {"User-Agent": "ndb/0.1"}
    if password:
        token = base64.b64encode(f":{password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            enc = resp.headers.get("Content-Encoding", "").lower()
            if "gzip" in enc:
                try:
                    data = gzip.decompress(data)
                except Exception:
                    pass
            return data.decode("utf-8", errors="replace")
    except (URLError, HTTPError, TimeoutError, Exception):
        return None


def _normalize_host(host: str) -> str:
    # Accept 192.168.0.10, 192.168.0.10:80, or http://192.168.0.10
    h = host
    if h.startswith("http://"):
        h = h[len("http://") :]
    if h.startswith("https://"):
        h = h[len("https://") :]
    if ":" not in h:
        h = f"{h}:80"
    return h


def fetch_device_info(host: str, timeout: float = 3.0, retries: int = 0, password: Optional[str] = None) -> Optional[DeviceInfo]:
    """Fetch and parse device info from /cp/version.json on the host."""
    host_port = _normalize_host(host)
    url = f"http://{host_port}/cp/version.json"
    attempts = max(1, 1 + int(retries))
    for _ in range(attempts):
        raw = _http_get(url, timeout, password=password)
        if not raw:
            continue
        info = parse_version_json(raw)
        if info:
            if not info.ip_address:
                info.ip_address = host_port.split(":", 1)[0]
            return info
    return None


def fetch_raw(host: str, timeout: float = 3.0, retries: int = 0, password: Optional[str] = None):
    """Return (url, body) for /cp/version.json if reachable, else (None, None)."""
    host_port = _normalize_host(host)
    url = f"http://{host_port}/cp/version.json"
    attempts = max(1, 1 + int(retries))
    for _ in range(attempts):
        raw = _http_get(url, timeout, password=password)
        if raw:
            return url, raw
    return None, None


def mdns_scan(*, duration: float = 3.0, service_types: Optional[List[str]] = None) -> List[Tuple[str, int, str]]:
    """Scan the local network via mDNS and return (ip, port, name) tuples.

    Requires the `zeroconf` package to be installed.
    """
    try:
        from zeroconf import Zeroconf, ServiceBrowser
    except Exception as e:
        raise RuntimeError("mdns_scan requires the 'zeroconf' package. Install with: uv add zeroconf") from e

    svc_types = service_types or [
        "_circuitpython._tcp.local.",
        "_http._tcp.local.",
    ]

    results: List[Tuple[str, int, str]] = []

    def b2ip(b: bytes) -> str:
        try:
            if len(b) == 16:
                return socket.inet_ntop(socket.AF_INET6, b)
            return socket.inet_ntop(socket.AF_INET, b)
        except Exception:
            return ""

    class _Listener:
        def __init__(self, zc: "Zeroconf"):
            self.zc = zc
            self.seen = set()

        def add_service(self, zc, service_type, name):
            info = zc.get_service_info(service_type, name, timeout=int(duration * 1000))
            if not info:
                return
            for addr in getattr(info, "addresses", []) or []:
                ip = b2ip(addr)
                if not ip:
                    continue
                key = (ip, info.port, name)
                if key not in self.seen:
                    self.seen.add(key)
                    results.append(key)

    import time
    zc = Zeroconf()
    try:
        listener = _Listener(zc)
        browsers = [ServiceBrowser(zc, t, listener) for t in svc_types]
        time.sleep(max(0.1, duration))
    finally:
        zc.close()
    return results
