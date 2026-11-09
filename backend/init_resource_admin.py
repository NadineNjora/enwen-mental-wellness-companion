from migrate_resource_admin import ensure_resource_schema
from database import engine
from resource_admin_models import ResourceCurator,ResourceDraft,ResourceAudit
def create_resource_admin():
    ensure_resource_schema()
    for model in (ResourceCurator,ResourceDraft,ResourceAudit):model.__table__.create(bind=engine,checkfirst=True)
if __name__=='__main__':create_resource_admin();print('Resource curation tables ready. No curator role was assigned and no resource was published or retired.')
