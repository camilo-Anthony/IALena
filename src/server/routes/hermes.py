from fastapi import APIRouter
from src.server.kernel_bridge import get_hermes_mcps, get_hermes_toolsets

router = APIRouter(prefix="/hermes", tags=["Hermes"])

@router.get("/mcps")
def read_mcps():
    return get_hermes_mcps()

@router.get("/toolsets")
def read_toolsets():
    return get_hermes_toolsets()
