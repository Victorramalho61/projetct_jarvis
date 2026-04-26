import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

import psutil

PORT = int(os.getenv("PORT", "9100"))


def collect_metrics() -> dict:
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    cpu_pct = round(cpu, 1)
    ram_pct = round(ram.percent, 1)
    disk_pct = round(disk.percent, 1)

    if any(v > 90 for v in (cpu_pct, ram_pct, disk_pct)):
        status = "down"
    elif any(v > 80 for v in (cpu_pct, ram_pct, disk_pct)):
        status = "degraded"
    else:
        status = "up"

    return {
        "cpu_pct": cpu_pct,
        "ram_pct": ram_pct,
        "ram_used_gb": round(ram.used / 1e9, 2),
        "ram_total_gb": round(ram.total / 1e9, 2),
        "disk_pct": disk_pct,
        "disk_used_gb": round(disk.used / 1e9, 2),
        "disk_total_gb": round(disk.total / 1e9, 2),
        "status": status,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silencia logs HTTP

    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        try:
            data = collect_metrics()
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            body = json.dumps({"error": str(exc), "status": "unknown"}).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"monitor-agent listening on :{PORT}/metrics", flush=True)
    server.serve_forever()
