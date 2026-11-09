"""Add lifecycle columns without rewriting existing resource metadata or bookmarks."""
from sqlalchemy import inspect,text
from database import engine

def ensure_resource_schema(bind=engine):
    with bind.begin() as connection:
        if not inspect(connection).has_table('wellness_resources'):return
        fields='resource_id,title,publisher,category,summary,url,audience_note,source_checked_on'
        before=connection.execute(text('SELECT '+fields+' FROM wellness_resources ORDER BY resource_id')).all()
        connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"))
        connection.execute(text('ALTER TABLE wellness_resources ADD COLUMN IF NOT EXISTS active boolean NOT NULL DEFAULT true'))
        connection.execute(text('ALTER TABLE wellness_resources ADD COLUMN IF NOT EXISTS revision integer NOT NULL DEFAULT 1'))
        connection.execute(text('ALTER TABLE wellness_resources ADD COLUMN IF NOT EXISTS updated_at timestamptz'))
        columns={c['name']:c for c in inspect(connection).get_columns('wellness_resources')}
        if str(columns['active']['type']).upper()!='BOOLEAN' or str(columns['revision']['type']).upper()!='INTEGER':raise RuntimeError('Unexpected existing resource lifecycle column types; nothing was committed.')
        after=connection.execute(text('SELECT '+fields+' FROM wellness_resources ORDER BY resource_id')).all()
        if before!=after:raise RuntimeError('Existing resource metadata changed unexpectedly; migration rolled back.')
if __name__=='__main__':ensure_resource_schema();print('Resource lifecycle columns confirmed; existing resource metadata retained.')
