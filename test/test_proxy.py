#!/usr/bin/env python3
"""Validate a deployed Squid proxy (OCI ocm-proxy stack).

Runs a series of checks against the proxy and prints a pass/fail report:

  1. TCP connect        - proxy port is reachable
  2. HTTP via proxy     - plain HTTP request is forwarded
  3. HTTPS via proxy    - CONNECT tunneling works
  4. Anonymity          - no Via / X-Forwarded-For headers leak to the origin
  5. Latency            - round-trip time through the proxy is reported

Uses only the Python standard library.

Usage:
    python test_proxy.py --proxy <proxy-ip>[:port] [--timeout 10]

The proxy may be given as '10.0.0.5', '10.0.0.5:3128' or
'http://10.0.0.5:3128' (port defaults to 3128).

Exit code is 0 if all checks pass, 1 otherwise.
"""

import argparse
import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def parse_proxy(value, default_port=3128):
    """Normalize '<host>', '<host>:<port>' or 'http://<host>:<port>' to
    (host, port, url). Shared convention with speedtest_upload.py."""
    if "//" not in value:
        value = "http://" + value
    parsed = urllib.parse.urlparse(value)
    if not parsed.hostname:
        raise ValueError(f"invalid proxy: {value!r}")
    port = parsed.port or default_port
    return parsed.hostname, port, f"http://{parsed.hostname}:{port}"

HTTP_TEST_URL = "http://neverssl.com/"
HTTPS_TEST_URL = "https://example.com/"
HEADERS_TEST_URL = "https://httpbin.org/headers"

RESULTS = []


def report(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f" - {detail}" if detail else ""))


def make_opener(proxy_url):
    handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    return urllib.request.build_opener(handler)


def check_tcp_connect(host, port, timeout):
    try:
        start = time.monotonic()
        with socket.create_connection((host, port), timeout=timeout):
            elapsed = (time.monotonic() - start) * 1000
        report("TCP connect", True, f"{host}:{port} reachable ({elapsed:.0f} ms)")
        return True
    except OSError as exc:
        report("TCP connect", False, f"{host}:{port} unreachable: {exc}")
        return False


def fetch(opener, url, timeout):
    """Return (status, body, elapsed_ms) or raise."""
    start = time.monotonic()
    with opener.open(url, timeout=timeout) as resp:
        body = resp.read()
        elapsed = (time.monotonic() - start) * 1000
        return resp.status, body, elapsed


def check_http(opener, timeout):
    try:
        status, body, elapsed = fetch(opener, HTTP_TEST_URL, timeout)
        ok = status == 200 and len(body) > 0
        report("HTTP via proxy", ok, f"GET {HTTP_TEST_URL} -> {status} ({elapsed:.0f} ms)")
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            report("HTTP via proxy", False,
                   "403 from proxy - client IP is probably not in the allowed CIDR")
        else:
            report("HTTP via proxy", False, f"HTTP {exc.code}: {exc.reason}")
    except (urllib.error.URLError, OSError) as exc:
        report("HTTP via proxy", False, str(exc))


def check_https(opener, timeout):
    try:
        status, body, elapsed = fetch(opener, HTTPS_TEST_URL, timeout)
        ok = status == 200 and len(body) > 0
        report("HTTPS via proxy (CONNECT)", ok,
               f"GET {HTTPS_TEST_URL} -> {status} ({elapsed:.0f} ms)")
    except urllib.error.HTTPError as exc:
        report("HTTPS via proxy (CONNECT)", False, f"HTTP {exc.code}: {exc.reason}")
    except (urllib.error.URLError, ssl.SSLError, OSError) as exc:
        report("HTTPS via proxy (CONNECT)", False, str(exc))


def check_anonymity(opener, timeout):
    """The stack configures 'via off' and 'forwarded_for delete' in Squid, so
    the origin server must not see Via or X-Forwarded-For headers."""
    try:
        status, body, _ = fetch(opener, HEADERS_TEST_URL, timeout)
        if status != 200:
            report("Anonymity headers", False, f"{HEADERS_TEST_URL} -> {status}")
            return
        headers = json.loads(body).get("headers", {})
        leaked = [h for h in ("Via", "X-Forwarded-For") if h in headers]
        if leaked:
            report("Anonymity headers", False, f"leaked to origin: {', '.join(leaked)}")
        else:
            report("Anonymity headers", True, "no Via / X-Forwarded-For leaked")
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        report("Anonymity headers", False, f"could not verify: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Validate the ocm-proxy Squid server.")
    parser.add_argument("--proxy", required=True,
                        help="Proxy IP/hostname, e.g. 10.0.0.5, 10.0.0.5:3128 "
                             "or http://10.0.0.5:3128 (port defaults to 3128)")
    parser.add_argument("--timeout", type=float, default=10.0,
                        help="Per-request timeout in seconds (default: 10)")
    args = parser.parse_args()

    try:
        host, port, proxy_url = parse_proxy(args.proxy)
    except ValueError as exc:
        parser.error(str(exc))

    print(f"Testing proxy {proxy_url}\n")

    if not check_tcp_connect(host, port, args.timeout):
        print("\nProxy port unreachable - skipping remaining checks.")
        print("Hints: NSG/security list ingress rule, instance iptables, "
              "cloud-init still running, or wrong IP.")
        sys.exit(1)

    opener = make_opener(proxy_url)
    check_http(opener, args.timeout)
    check_https(opener, args.timeout)
    check_anonymity(opener, args.timeout)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = len(RESULTS) - passed
    print(f"\n{passed}/{len(RESULTS)} checks passed.")
    if failed:
        print("Some checks failed. If HTTP/HTTPS fail with 403, verify the client "
              "running this script is inside the 'Allowed Client CIDR' configured "
              "in the stack.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
