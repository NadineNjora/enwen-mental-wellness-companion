"""Explicit additive bootstrap, then one app worker behind the HTTPS proxy."""
import os
import sys
sys.path.insert(0,"/app/backend")
from check_config import validate
if validate(os.environ):
    raise SystemExit("Deployment settings did not pass validation. Run deploy/check_config.py privately before starting.")
from init_db import create_tables
from migrate_mood_scale import upgrade
from database import engine
create_tables()
with engine.begin() as connection:
    upgrade(connection)
os.execvp("uvicorn",["uvicorn","main:app","--host","0.0.0.0","--port","8000","--proxy-headers","--forwarded-allow-ips","*","--no-access-log"])
