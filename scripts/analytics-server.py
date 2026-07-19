#!/usr/bin/env python3
"""Mini Analytics Server para Polaris - cuenta visitas por página"""
import json
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DATA_FILE = os.path.expanduser("~/workspace/public/analytics-data.json")

class AnalyticsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/analytics/track":
            # Track a page view
            params = parse_qs(parsed.query)
            page = params.get("page", ["unknown"])[0]
            ref = params.get("ref", ["direct"])[0]
            
            data = self._load_data()
            today = datetime.now().strftime("%Y-%m-%d")
            
            if today not in data:
                data[today] = {"pages": {}, "total": 0, "referrers": {}}
            
            data[today]["total"] += 1
            data[today]["pages"][page] = data[today]["pages"].get(page, 0) + 1
            data[today]["referrers"][ref] = data[today]["referrers"].get(ref, 0) + 1
            
            self._save_data(data)
            self._send_json({"ok": True})
            
        elif path == "/analytics/stats":
            data = self._load_data()
            self._send_json(data)
            
        elif path == "/analytics/today":
            data = self._load_data()
            today = datetime.now().strftime("%Y-%m-%d")
            self._send_json(data.get(today, {"pages": {}, "total": 0, "referrers": {}}))
            
        else:
            self._send_json({"error": "not found"}, 404)
    
    def _load_data(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                return json.load(f)
        return {}
    
    def _save_data(self, data):
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    
    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        pass  # Silent

if __name__ == "__main__":
    port = 8099
    server = HTTPServer(("0.0.0.0", port), AnalyticsHandler)
    print(f"📊 Analytics server running on port {port}")
    print(f"   Track:  http://localhost:{port}/analytics/track?page=/")
    print(f"   Stats:  http://localhost:{port}/analytics/stats")
    print(f"   Today:  http://localhost:{port}/analytics/today")
    server.serve_forever()