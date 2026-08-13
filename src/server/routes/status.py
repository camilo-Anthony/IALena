from fastapi import APIRouter
from src.server.kernel_bridge import get_status, get_capabilities, get_tasks

router = APIRouter(prefix="/status", tags=["Status"])

@router.get("")
def read_status():
    return get_status()

@router.get("/capabilities")
def read_capabilities():
    return get_capabilities()

@router.get("/tasks")
def read_tasks():
    return get_tasks()
