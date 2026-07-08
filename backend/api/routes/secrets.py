"""Route API pour la gestion des secrets (clés API)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config.secrets import SecretsManager, API_SERVICES, SERVICE_LABELS

router = APIRouter(prefix="/api/v1/secrets", tags=["Secrets"])
secrets_manager = SecretsManager()


class SecretRequest(BaseModel):
    service: str = Field(..., description="Nom du service (scribe_v2, deepseek, etc.)")
    api_key: str = Field(..., min_length=1, description="La clé API")


class SecretResponse(BaseModel):
    service: str
    label: str
    configured: bool


@router.get("/")
async def list_secrets():
    """Liste tous les services et leur état (configuré ou non)."""
    all_secrets = secrets_manager.get_all()
    results = []
    for service_id, label in SERVICE_LABELS.items():
        results.append({
            "service": service_id,
            "label": label,
            "configured": service_id in all_secrets,
        })
    return {"services": results, "configured_count": sum(1 for s in SERVICE_LABELS if secrets_manager.is_configured(s))}


@router.get("/{service}")
async def get_secret_status(service: str):
    """Vérifie si un service a sa clé configurée (sans exposer la clé)."""
    if service not in SERVICE_LABELS:
        raise HTTPException(status_code=404, detail=f"Service inconnu: {service}")
    return {
        "service": service,
        "label": SERVICE_LABELS[service],
        "configured": secrets_manager.is_configured(service),
    }


@router.post("/")
async def set_secret(req: SecretRequest):
    """Définit une clé API pour un service."""
    if req.service not in SERVICE_LABELS:
        raise HTTPException(status_code=404, detail=f"Service inconnu: {req.service}")
    secrets_manager.set(req.service, req.api_key)
    return {"status": "ok", "service": req.service, "label": SERVICE_LABELS[req.service], "configured": True}


@router.delete("/{service}")
async def delete_secret(service: str):
    """Supprime une clé API."""
    if service not in SERVICE_LABELS:
        raise HTTPException(status_code=404, detail=f"Service inconnu: {service}")
    secrets_manager.delete(service)
    return {"status": "ok", "service": service, "configured": False}
