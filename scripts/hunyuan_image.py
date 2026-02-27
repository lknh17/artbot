#!/usr/bin/env python3
"""
腾讯混元3.0图片生成
API: aiart.tencentcloudapi.com / SubmitTextToImageProJob + QueryTextToImageProJob
"""

import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

def _get_secret_id() -> str:
    return os.environ.get("HUNYUAN_SECRET_ID", "")


def _get_secret_key() -> str:
    return os.environ.get("HUNYUAN_SECRET_KEY", "")
REGION = "ap-guangzhou"
ENDPOINT = "aiart.tencentcloudapi.com"
SERVICE = "aiart"
VERSION = "2022-12-29"
SUBMIT_ACTION = "SubmitTextToImageProJob"
POLL_ACTION = "QueryTextToImageProJob"
POLL_INTERVAL = 3
MAX_WAIT = 120


def sign_tc3(action, payload_str, timestamp):
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
    # Follow TencentCloud SDK's TC3 signing behavior: sign only content-type and host.
    # (X-TC-Action is sent, but not included in SignedHeaders.)
    ct = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{ct}\nhost:{ENDPOINT}\n"
    signed_headers = "content-type;host"
    hashed_payload = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    canonical_request = f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"

    credential_scope = f"{date}/{SERVICE}/tc3_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n{hashed_canonical}"

    def _hmac(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_key = _get_secret_key()
    secret_id = _get_secret_id()

    secret_date = _hmac(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = hmac.new(secret_date, SERVICE.encode("utf-8"), hashlib.sha256).digest()
    secret_signing = hmac.new(secret_service, b"tc3_request", hashlib.sha256).digest()
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    return (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )


def call_api(action, payload):
    payload_str = json.dumps(payload)
    timestamp = int(time.time())
    auth = sign_tc3(action, payload_str, timestamp)

    headers = {
        "Authorization": auth,
        "Content-Type": "application/json; charset=utf-8",
        "Host": ENDPOINT,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": VERSION,
        "X-TC-Region": REGION,
    }

    req = urllib.request.Request(
        f"https://{ENDPOINT}/", data=payload_str.encode("utf-8"),
        headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"API Error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


def submit_job(prompt, resolution="1024:1024"):
    payload = {
        "Prompt": prompt,
        "Resolution": resolution,
        "LogoAdd": 0,
        "Revise": 1,  # 开启 prompt 改写，提升效果
    }
    result = call_api(SUBMIT_ACTION, payload)
    resp = result.get("Response", {})
    if "Error" in resp:
        print(f"Submit error: {json.dumps(resp['Error'], ensure_ascii=False)}", file=sys.stderr)
        sys.exit(1)
    job_id = resp.get("JobId")
    if not job_id:
        print(f"No JobId: {json.dumps(resp)}", file=sys.stderr)
        sys.exit(1)
    return job_id


def poll_job(job_id):
    waited = 0
    while waited < MAX_WAIT:
        time.sleep(POLL_INTERVAL)
        waited += POLL_INTERVAL
        result = call_api(POLL_ACTION, {"JobId": job_id})
        resp = result.get("Response", {})
        if "Error" in resp:
            print(f"Poll error: {json.dumps(resp['Error'], ensure_ascii=False)}", file=sys.stderr)
            sys.exit(1)
        status = resp.get("JobStatusCode")
        if status == "5":  # completed
            urls = resp.get("ResultImage", [])
            if urls:
                return urls[0]
            details = resp.get("ResultDetails", [])
            if details and details[0].get("Url"):
                return details[0]["Url"]
            print(f"Done but no URL: {json.dumps(resp)}", file=sys.stderr)
            sys.exit(1)
        elif status in ("-1", "6"):
            print(f"Job failed: {json.dumps(resp, ensure_ascii=False)}", file=sys.stderr)
            sys.exit(1)
        print(f"  waiting... ({waited}s, status={status})", file=sys.stderr)
    print("Timeout", file=sys.stderr)
    sys.exit(1)


def download(url, path, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=120) as resp:
                with open(path, "wb") as f:
                    f.write(resp.read())
            return
        except Exception as e:
            print(f"  Download attempt {attempt+1} failed: {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(3)
            else:
                result = subprocess.run(["curl", "-sL", "-o", path, "--max-time", "120", url],
                                       capture_output=True, timeout=130)
                if result.returncode != 0:
                    raise Exception(f"Download failed after {retries} retries")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 hunyuan_image.py \"prompt\" [output_path] [resolution]")
        sys.exit(1)

    prompt = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "cover.jpg"
    resolution = sys.argv[3] if len(sys.argv) > 3 else "1024:1024"

    print(f"[混元3.0] Generating: {prompt[:60]}...", file=sys.stderr)
    job_id = submit_job(prompt, resolution)
    print(f"Job: {job_id}", file=sys.stderr)

    url = poll_job(job_id)
    print(f"URL: {url[:80]}...", file=sys.stderr)

    download(url, output)
    print(f"Saved: {output}", file=sys.stderr)
    print(json.dumps({"success": True, "url": url, "path": output}))


if __name__ == "__main__":
    main()
