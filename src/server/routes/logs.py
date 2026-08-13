from fastapi import APIRouter
from src.server.kernel_bridge import get_logs

router = APIRouter(prefix="/logs", tags=["Logs"])

@router.get("")
def read_logs(n: int = 100):
    """Retorna los últimos n eventos del buffer de logs del kernel."""
    entries = get_logs(n)
    return {"logs": entries, "count": len(entries)}
