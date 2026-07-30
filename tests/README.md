# Proxy validation tests

Two scripts for validating a proxy instance deployed by this stack:

- `test_proxy.py` – functional checks (stdlib only, no packages needed)
- `speedtest_upload.py` – throughput test uploading to Object Storage via the
  proxy (requires the OCI SDK: `pip install -r requirements.txt`)

## test_proxy.py — functional checks

## Usage

```bash
python test_proxy.py --host <proxy-ip> [--port 3128] [--timeout 10]
```

Use the private IP when running from inside the VCN, or the public IP from
outside (only works if your source IP is within the stack's
"Allowed Client CIDR").

## Checks performed

| Check | What it validates |
|---|---|
| TCP connect | Proxy port reachable (NSG, security lists, instance iptables) |
| HTTP via proxy | Squid forwards plain HTTP requests |
| HTTPS via proxy | CONNECT tunneling for TLS works |
| Anonymity headers | `Via` / `X-Forwarded-For` are not leaked to the origin (matches the stack's Squid config) |

Exit code is `0` when all checks pass, `1` otherwise, so the script can be
used in CI or automation.

## Example output

```
Testing proxy http://10.0.1.23:3128

  [PASS] TCP connect - 10.0.1.23:3128 reachable (12 ms)
  [PASS] HTTP via proxy - GET http://neverssl.com/ -> 200 (180 ms)
  [PASS] HTTPS via proxy (CONNECT) - GET https://example.com/ -> 200 (210 ms)
  [PASS] Anonymity headers - no Via / X-Forwarded-For leaked

4/4 checks passed.
```

## Troubleshooting

- **TCP connect fails** – check the NSG ingress rule, the subnet's security
  lists, and that cloud-init has finished (`cloud-init status` on the
  instance). Also confirm you are using the right IP.
- **HTTP/HTTPS fail with 403** – the machine running the test is outside the
  "Allowed Client CIDR" configured in the stack.

## speedtest_upload.py — throughput test

Generates a dummy file (default 4 GiB) and uploads it to an Object Storage
bucket as a multipart upload with parallel streams (default 5). All traffic
is routed through the proxy by injecting it into the OCI SDK's HTTP session.

```bash
pip install -r requirements.txt
python speedtest_upload.py --proxy http://<proxy-ip>:3128 --bucket <bucket-name>
```

Key options (see `--help` for all):

| Option | Default | Description |
|---|---|---|
| `--size-gb` | `4` | Dummy file size in GiB |
| `--parallel` | `5` | Parallel upload streams |
| `--part-size-mb` | `128` | Multipart part size in MiB |
| `--data` | `sparse` | `sparse` (instant to create) or `random` (incompressible) |
| `--auth` | `api_key` | `api_key` (~/.oci/config) or `instance_principal` |
| `--keep-object` | off | Keep the uploaded object instead of deleting it |
| `--file` | – | Reuse an existing local file instead of generating one |

The script prints live progress and a final report with duration and average
throughput (MiB/s and Mbit/s). By default it cleans up after itself: the
uploaded object and the generated local file are deleted when the test ends.

Requirements on the OCI side: the bucket must exist, and the credentials used
need `manage objects` permission on it. When running on an OCI instance you
can use `--auth instance_principal` instead of an API key (the instance must
be in a dynamic group with a matching policy).
