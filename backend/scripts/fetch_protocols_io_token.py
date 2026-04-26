#!/usr/bin/env python3
"""One-shot OAuth helper for protocols.io.

Run this script once to exchange your client_id + client_secret for an
access_token, which is then written to backend/.env automatically.

Usage:
    cd backend
    PROTOCOLS_IO_CLIENT_ID=your_id PROTOCOLS_IO_CLIENT_SECRET=your_secret \
        python scripts/fetch_protocols_io_token.py

Or if you already have backend/.env with the client credentials set:
    python scripts/fetch_protocols_io_token.py

The script will:
  1. Open your browser to the protocols.io authorization page.
  2. Start a local HTTP server on http://localhost:8888 to catch the redirect.
  3. Exchange the authorization code for an access_token + refresh_token.
  4. Write PROTOCOLS_IO_TOKEN=<token> to backend/.env.
"""

from __future__ import annotations

import http.server
import os
import pathlib
import re
import sys
import threading
import time
import urllib.parse
import webbrowser

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REDIRECT_URI = "http://localhost:8888/callback"
AUTH_URL = "https://www.protocols.io/api/v3/oauth/authorize"
TOKEN_URL = "https://www.protocols.io/api/v3/oauth/token"
SCOPE = "readwrite"
ENV_FILE = pathlib.Path(__file__).parent.parent / ".env"

# ---------------------------------------------------------------------------
# Load credentials
# ---------------------------------------------------------------------------

load_dotenv(ENV_FILE, override=True)
CLIENT_ID = os.environ.get("PROTOCOLS_IO_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("PROTOCOLS_IO_CLIENT_SECRET", "").strip()

# region agent log
import json as _json, time as _time
_log_path = pathlib.Path("/Users/janikludwig/Developer/PredictiveBio/.cursor/debug-4e45f2.log")
_log_path.parent.mkdir(parents=True, exist_ok=True)
with open(_log_path, "a") as _lf:
    _lf.write(_json.dumps({"sessionId":"4e45f2","hypothesisId":"H-A/H-B","location":"fetch_protocols_io_token.py:51","message":"credentials loaded after override=True","data":{"client_id_value":CLIENT_ID,"client_id_is_placeholder":CLIENT_ID=="your_client_id_here","env_file_exists":ENV_FILE.exists(),"env_file_path":str(ENV_FILE)},"timestamp":int(_time.time()*1000)}) + "\n")
# endregion agent log

if not CLIENT_ID or not CLIENT_SECRET:
    print(
        "ERROR: PROTOCOLS_IO_CLIENT_ID and PROTOCOLS_IO_CLIENT_SECRET must be set.\n"
        "Either export them as env vars or add them to backend/.env."
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Local callback server — captures the authorization code
# ---------------------------------------------------------------------------

_auth_code: str | None = None
_server_ready = threading.Event()


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        global _auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]

        if code:
            _auth_code = code
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Authorization successful!</h2>"
                b"<p>You can close this tab and return to the terminal.</p>"
                b"</body></html>"
            )
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            error = params.get("error", ["unknown"])[0]
            self.wfile.write(
                f"<html><body><h2>Authorization failed: {error}</h2></body></html>".encode()
            )

    def log_message(self, format: str, *args: object) -> None:
        pass  # suppress access logs


def _start_callback_server() -> http.server.HTTPServer:
    server = http.server.HTTPServer(("localhost", 8888), _CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------


def _build_auth_url() -> str:
    params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "redirect_url": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
    })
    url = f"{AUTH_URL}?{params}"
    # region agent log
    import json as _json, time as _time
    _log_path = pathlib.Path("/Users/janikludwig/Developer/PredictiveBio/.cursor/debug-4e45f2.log")
    with open(_log_path, "a") as _lf:
        _lf.write(_json.dumps({"sessionId":"4e45f2","hypothesisId":"H-B","location":"fetch_protocols_io_token.py:_build_auth_url","message":"auth url built","data":{"client_id_in_url":CLIENT_ID,"redirect_param":"redirect_url","full_url":url},"timestamp":int(_time.time()*1000)}) + "\n")
    # endregion agent log
    return url


def _exchange_code(code: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# .env writer — updates PROTOCOLS_IO_TOKEN in place or appends it
# ---------------------------------------------------------------------------


def _write_token_to_env(access_token: str, refresh_token: str | None) -> None:
    env_path = ENV_FILE

    if env_path.exists():
        content = env_path.read_text()
        if re.search(r"^PROTOCOLS_IO_TOKEN\s*=", content, re.MULTILINE):
            content = re.sub(
                r"^PROTOCOLS_IO_TOKEN\s*=.*$",
                f"PROTOCOLS_IO_TOKEN={access_token}",
                content,
                flags=re.MULTILINE,
            )
        else:
            content = content.rstrip("\n") + f"\nPROTOCOLS_IO_TOKEN={access_token}\n"

        if refresh_token:
            if re.search(r"^PROTOCOLS_IO_REFRESH_TOKEN\s*=", content, re.MULTILINE):
                content = re.sub(
                    r"^PROTOCOLS_IO_REFRESH_TOKEN\s*=.*$",
                    f"PROTOCOLS_IO_REFRESH_TOKEN={refresh_token}",
                    content,
                    flags=re.MULTILINE,
                )
            else:
                content = content.rstrip("\n") + f"\nPROTOCOLS_IO_REFRESH_TOKEN={refresh_token}\n"
    else:
        lines = [f"PROTOCOLS_IO_TOKEN={access_token}\n"]
        if refresh_token:
            lines.append(f"PROTOCOLS_IO_REFRESH_TOKEN={refresh_token}\n")
        content = "".join(lines)

    env_path.write_text(content)
    print(f"\nWritten to {env_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("Starting local OAuth callback server on http://localhost:8888 ...")
    server = _start_callback_server()

    auth_url = _build_auth_url()
    print(f"\nOpening browser to:\n{auth_url}\n")
    print("If the browser does not open automatically, copy the URL above and paste it.")
    webbrowser.open(auth_url)

    print("Waiting for authorization (60s timeout)...")
    deadline = time.time() + 60
    while _auth_code is None and time.time() < deadline:
        time.sleep(0.5)

    server.shutdown()

    if _auth_code is None:
        print("ERROR: Timed out waiting for authorization code. Re-run the script.")
        sys.exit(1)

    print(f"Authorization code received. Exchanging for access token...")
    try:
        token_data = _exchange_code(_auth_code)
    except requests.HTTPError as exc:
        print(f"ERROR: Token exchange failed: {exc}\nResponse: {exc.response.text}")
        sys.exit(1)

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    if not access_token:
        print(f"ERROR: No access_token in response: {token_data}")
        sys.exit(1)

    expires_in = token_data.get("expires_in", "unknown")
    print(f"\nSuccess!")
    print(f"  access_token : {access_token[:20]}...")
    print(f"  refresh_token: {'yes' if refresh_token else 'no'}")
    print(f"  expires_in   : {expires_in}s")

    _write_token_to_env(access_token, refresh_token)
    print("\nDone. Restart the backend server to pick up the new token.")


if __name__ == "__main__":
    main()
