from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from authentication import router as authentication_router
from database import engine
from registration import router as registration_router
from moods import router as moods_router
from journals import router as journals_router
from contacts_invitations import router as contact_invitations_router
from resources import router as resources_router
from ai_chat import router as chat_router
from chat_history import router as chat_history_router
from safety_screen import router as safety_router
from safety_alerts import router as safety_alert_router

app = FastAPI(title="ENWEN API")
app.include_router(registration_router)
app.include_router(authentication_router)
app.include_router(moods_router)
app.include_router(journals_router)
app.include_router(contact_invitations_router)
app.include_router(resources_router)
app.include_router(chat_router)
app.include_router(chat_history_router)
app.include_router(safety_router)
app.include_router(safety_alert_router)

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, error: RequestValidationError):
    # Do not echo submitted passwords or other input in validation errors.
    details = [
        {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
        for item in error.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": details})


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/health/db")
def database_health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database connection unavailable.",
        ) from None

    return {"database": "connected"}
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(FRONTEND_DIR / "sw.js", media_type="application/javascript",
        headers={"Cache-Control":"no-cache", "Service-Worker-Allowed":"/"})


@app.get("/manifest.webmanifest", include_in_schema=False)
def app_manifest():
    return FileResponse(FRONTEND_DIR / "manifest.webmanifest", media_type="application/manifest+json",
        headers={"Cache-Control":"no-cache"})


@app.get("/static/register.html", include_in_schema=False)
def registration_page():
    return FileResponse(
        FRONTEND_DIR / "register.html",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/static/contact-response.html", include_in_schema=False)
def invitation_page_alias():
    # Keep earlier tutorial links working with the user's chosen filename.
    return FileResponse(
        FRONTEND_DIR / "contacts_response.html",
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )

app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="static",
)


@app.get("/", include_in_schema=False)
def frontend_home():
    return FileResponse(
        FRONTEND_DIR / "index.html",
        headers={"Cache-Control": "no-store"},
    )
