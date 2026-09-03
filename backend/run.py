"""
run.py
======
Local dev entrypoint. Production deployments should instead point a WSGI
server (gunicorn, etc.) at `wr_webapp.app:create_app` rather than running
Flask's built-in dev server.

Usage:
    python run.py
"""
from wr_webapp.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
