"""Private PostgreSQL archives. Restore only into a different, empty database.

Credentials are supplied in subprocess environment, never command arguments.
No restore command drops a table or database or uses pg_restore --clean.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime,timezone
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
from dotenv import dotenv_values

def executable(name):
    candidate=shutil.which(name)
    if candidate:return candidate
    windows=Path('C:/Program Files/PostgreSQL/18/bin')/(name+'.exe')
    if windows.is_file():return str(windows)
    raise RuntimeError('Install matching PostgreSQL client tools or add them to PATH.')

def settings():
    data=dotenv_values(ROOT/'backend'/'.env')
    env=os.environ.copy()
    for source,target in (('DB_HOST','PGHOST'),('DB_PORT','PGPORT'),('DB_USER','PGUSER'),('DB_PASSWORD','PGPASSWORD')):
        if not data.get(source):raise RuntimeError('Private database settings are incomplete.')
        env[target]=data[source]
    env['PGCONNECT_TIMEOUT']='5'
    return data,env

def invoke(arguments,env):
    result=subprocess.run(arguments,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
    if result.returncode:raise RuntimeError('PostgreSQL operation failed. Nothing was automatically retried; private diagnostic output was withheld.')
    return result.stdout

def verify(path):
    if not path.is_file() or not path.with_suffix('.sha256').is_file():raise RuntimeError('Archive or checksum sidecar is missing.')
    expected=path.with_suffix('.sha256').read_text().strip()
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise RuntimeError('Archive checksum does not match. Do not restore it.')
    invoke([executable('pg_restore'),'--list',str(path)],os.environ.copy())
    return True

def backup():
    data,env=settings();folder=ROOT/'private-data'/'backups';folder.mkdir(parents=True,exist_ok=True)
    name='enwen-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    partial=folder/(name+'.partial');archive=folder/(name+'.dump')
    invoke([executable('pg_dump'),'--format=custom','--no-owner','--no-acl','--file',str(partial),'--dbname',data['DB_NAME']],env)
    partial.rename(archive)
    archive.with_suffix('.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'\n')
    verify(archive)
    print('Private archive created and integrity checked:',archive)
    print('It contains private student data. Keep it outside Git and shared folders; use encrypted storage for long-term retention.')

def restore(path,target):
    import psycopg
    data,env=settings();verify(path)
    if target==data['DB_NAME'] or not re.fullmatch(r'enwen_recovery_[a-z0-9_]{1,40}',target):raise RuntimeError('Restore requires a different database named enwen_recovery_... . The working database is protected.')
    with psycopg.connect(host=data['DB_HOST'],port=data['DB_PORT'],user=data['DB_USER'],password=data['DB_PASSWORD'],dbname=target,connect_timeout=5) as connection:
        occupied=connection.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r','p','v','m','S','f')").fetchone()[0]
        if occupied:raise RuntimeError('Recovery database is not empty. No restore was attempted.')
    if input('Type RESTORE '+target+' to restore into this empty recovery database: ').strip()!='RESTORE '+target:
        print('Cancelled. Nothing restored.');return
    invoke([executable('pg_restore'),'--exit-on-error','--single-transaction','--no-owner','--no-acl','--dbname',target,str(path)],env)
    print('Archive restored into the separate recovery database. Application checks are still required; the working database was not changed.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('backup','verify','restore'));parser.add_argument('--archive',type=Path);parser.add_argument('--target-database');args=parser.parse_args()
    try:
        if args.action=='backup':backup()
        elif args.action=='verify':verify(args.archive or Path('missing'));print('Archive checksum and PostgreSQL archive directory verified. Restore not performed.')
        elif not args.archive or not args.target_database:raise RuntimeError('Supply --archive and --target-database for a separate, empty recovery database.')
        else:restore(args.archive,args.target_database)
    except (RuntimeError,subprocess.SubprocessError,OSError) as error:
        print(str(error));raise SystemExit(1)
