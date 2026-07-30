# Ubuntu Proxy Server for OCI 

This OCI Resource Management stack provisions an **Ubuntu compute instance with a preconfigured Squid
proxy server** into an existing VCN/subnet, using OCI Resource Manager (ORM).

## Deploy to Oracle Cloud

Sign in to your OCI tenancy and click the button below to create the stack
directly from this repository:

[![Deploy to Oracle Cloud](images/deploy-to-oracle-cloud.svg)](https://cloud.oracle.com/resourcemanager/stacks/create?zipUrl=https://github.com/RichardORCL/oci-proxy/archive/refs/heads/main.zip)

After logging in you land on the Resource Manager "Create stack" page with
this repository preloaded; just fill in the variables, then run **Plan** and
**Apply**.

## What gets created

| Resource | Purpose |
|---|---|
| Compute instance (Ubuntu 24.04 or 22.04) | Runs the Squid proxy, installed via cloud-init |
| Network Security Group + rules | Allows proxy traffic (default TCP 3128) from the allowed CIDR, all egress |

The VCN and subnet are **not** created – you select existing ones in the
stack UI.

## Stack UI options (schema.yaml)

- **Placement** – compartment and availability domain for the instance
- **Network** – network compartment, VCN, subnet, and public IP toggle
- **Instance Configuration** – shape (with OCPU/memory sliders for Flex
  shapes), boot volume size, Ubuntu version, SSH public key
- **Proxy Configuration** – listen port and allowed client CIDR

## Proxy details

Cloud-init installs Squid and writes `/etc/squid/conf.d/proxy.conf`:

- Listens on the configured port (default `3128`)
- Only clients from the configured CIDR may connect; everything else is denied
- Caching disabled, `Via`/`X-Forwarded-For` headers suppressed
- The port is also opened in the instance's local iptables rules (Oracle
  Ubuntu images only allow SSH by default) and in the attached NSG

After apply, the **Application Information** tab shows the ready-to-use proxy
URLs (private and public).

Test from an allowed client:

```bash
curl -x http://<proxy-ip>:3128 https://example.com
```

## Deploying as a Resource Manager stack

There are two ways to deploy this stack:

### Option 1: Deploy to Oracle Cloud button (easiest)

Click the **Deploy to Oracle Cloud** button at the top of this page. After
signing in to your tenancy, the Resource Manager "Create stack" page opens
with this repository preloaded. Fill in the form (compartment, VCN/subnet,
shape, SSH key, proxy settings), then run **Plan** and **Apply**.

### Option 2: Manual zip upload

1. Download [`ocm-proxy-stack.zip`](https://github.com/RichardORCL/oci-proxy/raw/main/ocm-proxy-stack.zip)
   from this repository (it contains only the Terraform files, cloud-init
   template, and schema).
2. In the OCI Console: **Developer Services → Resource Manager → Stacks →
   Create stack**, choose **My configuration → .Zip file** and upload the zip.
3. Fill in the form (compartment, VCN/subnet, shape, SSH key, proxy settings).
4. Run **Plan**, review, then **Apply**.

If you modify the Terraform files, rebuild the zip with:

```powershell
Compress-Archive -Path *.tf, cloud-init.yaml.tftpl, schema.yaml -DestinationPath ocm-proxy-stack.zip -Force
```

## Testing the proxy

The [`test`](test/) folder contains two Python scripts to validate a
deployed proxy. Both take the proxy address via `--proxy`, given as
`10.0.0.5`, `10.0.0.5:3128` or `http://10.0.0.5:3128` (port defaults
to 3128). Run them from a machine inside the stack's "Allowed Client CIDR".

### test_proxy.py – functional validation

Checks that the proxy works correctly. Uses only the Python standard
library, so nothing needs to be installed:

```bash
python test/test_proxy.py --proxy <proxy-ip>
```

It verifies that the proxy port is reachable (NSG, security lists and
instance firewall), that plain HTTP requests are forwarded, that HTTPS
tunneling (CONNECT) works, and that no `Via` / `X-Forwarded-For` headers
leak to the origin server. Exit code 0 means all checks passed.

### speedtest_upload.py – throughput test

Measures upload bandwidth through the proxy by uploading a dummy file
(default 4 GiB) to an OCI Object Storage bucket as a multipart upload with
parallel streams (default 5). Requires the OCI Python SDK
(`pip install -r test/requirements.txt`) and credentials with write access
to the bucket:

```bash
python test/speedtest_upload.py --proxy <proxy-ip> --bucket <bucket-name>
```

It prints live progress and a final report with duration and average
throughput (MiB/s and Mbit/s), then cleans up the uploaded object and the
local dummy file. File size, stream count, part size and authentication
method (API key or instance principal) are configurable; see `--help`.

Full documentation for both scripts is in [`test/README.md`](test/README.md).

## Notes

- If the subnet uses security lists that block the proxy port, allow it there
  too, or rely solely on the NSG by keeping the security lists permissive
  between the proxy and its clients.
- Cloud-init takes a minute or two after the instance becomes RUNNING before
  the proxy answers.
- SSH access: `ssh ubuntu@<ip>` with the key you provided.
