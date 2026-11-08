"""Validate deployment settings without printing credentials or contacting hosts."""
import ipaddress
import os
import re
from pathlib import Path

def validate(values):
    errors=[]
    domain=values.get("APP_DOMAIN","").strip()
    if not re.fullmatch(r"(?=.{1,253}$)[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?",domain) or "." not in domain or domain.lower().endswith((".invalid",".example",".test",".local",".localhost")):
        errors.append("Provide an owned public DNS hostname for APP_DOMAIN.")
    try:ipaddress.ip_address(domain);errors.append("APP_DOMAIN must be a DNS hostname, not an IP address.")
    except ValueError:pass
    for name,length in (("DB_PASSWORD",24),("JWT_SECRET",64)):
        value=values.get(name,"")
        if len(value)<length or "REPLACE" in value.upper():errors.append(f"{name} needs a fresh random value of at least {length} characters.")
    for name in ("DB_NAME","DB_USER"):
        if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}",values.get(name,"")):errors.append(f"Set a simple lowercase {name}.")
    if values.get("LIVE_SMS_ENABLED","false").lower()=="true":errors.append("SMS is on hold; keep LIVE_SMS_ENABLED=false.")
    return errors

if __name__=="__main__":
    from dotenv import dotenv_values
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument("--env",type=Path,default=Path(__file__).with_name(".env.production"));args=parser.parse_args()
    if not args.env.is_file():raise SystemExit("No production settings file yet. Copy deploy/.env.example to deploy/.env.production on the chosen server; fill it privately.")
    errors=validate(dotenv_values(args.env))
    if errors:raise SystemExit("Deployment not ready:\n"+"\n".join(errors))
    print("Settings checks pass. Domain ownership/DNS, server resources, TLS and real-device behaviour still need verification. No deployment started.")
