#!/usr/bin/env python3
"""Object Storage upload speedtest through the ocm-proxy Squid server.

Generates a large dummy file (default 4 GB) and uploads it to an OCI Object
Storage bucket as a multipart upload with parallel streams (default 5),
routing all traffic through the HTTP proxy deployed by this stack.

Requires the OCI Python SDK:  pip install oci

Authentication:
  - api_key (default): uses ~/.oci/config (override with --profile)
  - instance_principal: for running on an OCI instance with a dynamic group
    policy (the metadata-service call bypasses the proxy, as it must)

Examples:
    python speedtest_upload.py --proxy http://10.0.1.23:3128 --bucket my-bucket
    python speedtest_upload.py --proxy http://10.0.1.23:3128 --bucket my-bucket \
        --size-gb 1 --parallel 10 --data random --keep-object
"""

import argparse
import os
import sys
import tempfile
import threading
import time

try:
    import oci
except ImportError:
    sys.exit("The OCI Python SDK is required:  pip install oci")

MiB = 1024 * 1024
GiB = 1024 * MiB


def human_rate(bytes_per_sec):
    mib_s = bytes_per_sec / MiB
    mbit_s = bytes_per_sec * 8 / 1_000_000
    return f"{mib_s:.1f} MiB/s ({mbit_s:.0f} Mbit/s)"


def create_dummy_file(path, size_bytes, mode):
    """Create the test file. 'sparse' is near-instant (reads as zeros),
    'random' writes an incompressible repeated 4 MiB random block."""
    print(f"Creating {size_bytes / GiB:.2f} GiB dummy file ({mode}): {path}")
    start = time.monotonic()
    with open(path, "wb") as f:
        if mode == "sparse":
            f.seek(size_bytes - 1)
            f.write(b"\0")
        else:
            block = os.urandom(4 * MiB)
            written = 0
            while written < size_bytes:
                chunk = block[: min(len(block), size_bytes - written)]
                f.write(chunk)
                written += len(chunk)
    print(f"  created in {time.monotonic() - start:.1f}s")


class Progress:
    """Thread-safe progress printer for UploadManager's progress_callback."""

    def __init__(self, total_bytes):
        self.total = total_bytes
        self.done = 0
        self.start = time.monotonic()
        self._last_print = 0.0
        self._lock = threading.Lock()

    def __call__(self, bytes_uploaded):
        with self._lock:
            self.done += bytes_uploaded
            now = time.monotonic()
            if now - self._last_print < 1.0 and self.done < self.total:
                return
            self._last_print = now
            elapsed = max(now - self.start, 1e-6)
            rate = self.done / elapsed
            pct = 100.0 * self.done / self.total
            print(f"\r  {pct:5.1f}%  {self.done / GiB:.2f}/{self.total / GiB:.2f} GiB"
                  f"  avg {human_rate(rate)}   ", end="", flush=True)


def build_client(args):
    if args.auth == "instance_principal":
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        client = oci.object_storage.ObjectStorageClient(
            {"region": signer.region}, signer=signer)
    else:
        config = oci.config.from_file(profile_name=args.profile)
        client = oci.object_storage.ObjectStorageClient(config)

    # Route all Object Storage traffic through the proxy. The SDK uses a
    # requests.Session under the hood, shared by UploadManager's worker
    # threads, so this covers the parallel part uploads too.
    client.base_client.session.proxies = {"http": args.proxy, "https": args.proxy}
    return client


def main():
    parser = argparse.ArgumentParser(
        description="Upload speedtest to OCI Object Storage via the proxy.")
    parser.add_argument("--proxy", required=True,
                        help="Proxy URL, e.g. http://10.0.1.23:3128")
    parser.add_argument("--bucket", required=True, help="Target bucket name")
    parser.add_argument("--namespace", default=None,
                        help="Object Storage namespace (auto-detected if omitted)")
    parser.add_argument("--size-gb", type=float, default=4.0,
                        help="Dummy file size in GiB (default: 4)")
    parser.add_argument("--parallel", type=int, default=5,
                        help="Number of parallel upload streams (default: 5)")
    parser.add_argument("--part-size-mb", type=int, default=128,
                        help="Multipart part size in MiB (default: 128)")
    parser.add_argument("--object-name", default=None,
                        help="Object name (default: speedtest-<timestamp>.bin)")
    parser.add_argument("--file", default=None,
                        help="Reuse an existing local file instead of generating one")
    parser.add_argument("--data", choices=["sparse", "random"], default="sparse",
                        help="Dummy file content (default: sparse, near-instant to create)")
    parser.add_argument("--auth", choices=["api_key", "instance_principal"],
                        default="api_key", help="Authentication method (default: api_key)")
    parser.add_argument("--profile", default="DEFAULT",
                        help="~/.oci/config profile for api_key auth (default: DEFAULT)")
    parser.add_argument("--keep-object", action="store_true",
                        help="Do not delete the uploaded object afterwards")
    parser.add_argument("--keep-file", action="store_true",
                        help="Do not delete the generated local dummy file afterwards")
    args = parser.parse_args()

    size_bytes = int(args.size_gb * GiB)
    part_size = args.part_size_mb * MiB
    object_name = args.object_name or f"speedtest-{int(time.time())}.bin"

    # Ensure enough parts to keep all parallel streams busy.
    if size_bytes / part_size < args.parallel:
        part_size = max(10 * MiB, size_bytes // (args.parallel * 2))
        print(f"Note: part size reduced to {part_size // MiB} MiB so that "
              f"{args.parallel} streams can run in parallel.")

    generated_file = None
    if args.file:
        file_path = args.file
        size_bytes = os.path.getsize(file_path)
        print(f"Using existing file: {file_path} ({size_bytes / GiB:.2f} GiB)")
    else:
        fd, file_path = tempfile.mkstemp(prefix="oci-speedtest-", suffix=".bin")
        os.close(fd)
        generated_file = file_path
        create_dummy_file(file_path, size_bytes, args.data)

    exit_code = 0
    client = build_client(args)
    try:
        namespace = args.namespace or client.get_namespace().data
        print(f"\nUploading to bucket '{args.bucket}' (namespace '{namespace}') "
              f"as '{object_name}'")
        print(f"  proxy: {args.proxy} | streams: {args.parallel} | "
              f"part size: {part_size // MiB} MiB\n")

        upload_manager = oci.object_storage.UploadManager(
            client,
            allow_parallel_uploads=True,
            parallel_process_count=args.parallel,
        )

        progress = Progress(size_bytes)
        start = time.monotonic()
        response = upload_manager.upload_file(
            namespace,
            args.bucket,
            object_name,
            file_path,
            part_size=part_size,
            progress_callback=progress,
        )
        elapsed = time.monotonic() - start
        print()  # newline after progress line

        head = client.head_object(namespace, args.bucket, object_name)
        remote_size = int(head.headers["Content-Length"])

        print("\n===== RESULT =====")
        print(f"  uploaded:        {size_bytes / GiB:.2f} GiB "
              f"(remote size matches: {remote_size == size_bytes})")
        print(f"  duration:        {elapsed:.1f} s")
        print(f"  avg throughput:  {human_rate(size_bytes / elapsed)}")
        print(f"  streams:         {args.parallel} x {part_size // MiB} MiB parts")
        print(f"  http status:     {response.status}")

        if remote_size != size_bytes:
            print("  WARNING: remote object size does not match the local file!")
            exit_code = 1

        if args.keep_object:
            print(f"  object kept:     {object_name}")
        else:
            client.delete_object(namespace, args.bucket, object_name)
            print("  object deleted from bucket (use --keep-object to keep it)")
    except oci.exceptions.ServiceError as exc:
        print(f"\nOCI service error {exc.status}: {exc.message}", file=sys.stderr)
        exit_code = 1
    except Exception as exc:  # noqa: BLE001 - report proxy/network errors cleanly
        print(f"\nUpload failed: {exc}", file=sys.stderr)
        print("Hint: verify the proxy is reachable and this client is inside the "
              "stack's 'Allowed Client CIDR'.", file=sys.stderr)
        exit_code = 1
    finally:
        if generated_file and not args.keep_file:
            os.remove(generated_file)
            print(f"  local dummy file removed ({generated_file})")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
