from fastapi import APIRouter
from pydantic import BaseModel, Field
from src.server.kernel_bridge import (
    get_hermes_mcps,
    get_hermes_toolsets,
    get_hermes_skills,
    get_tasks,
    dispatch_hermes_task,
    get_scheduler_and_sentinel_status,
    get_hermes_memory,
    get_hermes_cron_jobs,
    create_hermes_cron_job,
    set_hermes_cron_job_state,
    update_hermes_cron_job,
    delete_hermes_cron_job,
    get_hermes_cron_outputs,
    reload_hermes_slow_worker,
)

router = APIRouter(prefix="/hermes", tags=["Hermes"])


class DispatchRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Texto de la orden para Hermes")
    lane: str = Field(default="slow", pattern="^(slow|fast)$", description="Carril de ejecución ('slow' o 'fast')")


@router.get("/tasks")
def read_tasks():
    """Retorna el listado de tareas activas y recientes del TaskLedger."""
    return get_tasks()


@router.post("/dispatch")
async def dispatch_task(req: DispatchRequest):
    """Despacha una tarea textual directamente hacia Hermes."""
    res = await dispatch_hermes_task(prompt=req.prompt, lane=req.lane)
    return res


@router.get("/status")
def read_autonomy_status():
    """Retorna el estado de los subsistemas autónomos (Scheduler y Sentinel)."""
    return get_scheduler_and_sentinel_status()


@router.get("/mcps")
def read_mcps():
    return get_hermes_mcps()


class MCPServerModel(BaseModel):
    name: str = Field(..., min_length=1, description="Identificador único del servidor MCP")
    command: str = Field(default="", description="Comando ejecutable (uvx, npx, python, etc.)")
    args: list[str] = Field(default_factory=list, description="Argumentos de ejecución")
    url: str = Field(default="", description="URL remota si es protocolo HTTP/SSE")
    enabled: bool = Field(default=True, description="Estado de habilitación del servidor")
    env: dict[str, str] = Field(default_factory=dict, description="Variables de entorno")


@router.post("/mcps")
def create_or_update_mcp(body: MCPServerModel):
    from src.server.kernel_bridge import save_hermes_mcp
    res = save_hermes_mcp(
        name=body.name,
        mcp_config={
            "command": body.command,
            "args": body.args,
            "url": body.url,
            "enabled": body.enabled,
            "env": body.env,
        },
    )
    return res


@router.post("/mcps/{name}/toggle")
def toggle_mcp(name: str):
    from src.server.kernel_bridge import toggle_hermes_mcp
    res = toggle_hermes_mcp(name)
    return res


@router.delete("/mcps/{name}")
def delete_mcp(name: str):
    from src.server.kernel_bridge import remove_hermes_mcp
    res = remove_hermes_mcp(name)
    return res


@router.get("/toolsets")
def read_toolsets():
    return get_hermes_toolsets()


@router.get("/skills")
def read_skills():
    return get_hermes_skills()


@router.get("/memory")
def read_memory():
    return get_hermes_memory()


class CronJobCreateModel(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=12000)
    schedule: str = Field(..., min_length=1, max_length=200)
    name: str = Field(default="", max_length=160)


class CronJobUpdateModel(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    prompt: str | None = Field(default=None, min_length=1, max_length=12000)
    schedule: str | None = Field(default=None, min_length=1, max_length=200)


@router.get("/cron")
def read_cron_jobs():
    return get_hermes_cron_jobs()


@router.post("/cron")
def create_cron_job(body: CronJobCreateModel):
    return create_hermes_cron_job(body.prompt, body.schedule, body.name)


@router.post("/cron/{job_id}/{action}")
def update_cron_job(job_id: str, action: str):
    return set_hermes_cron_job_state(job_id, action)


@router.patch("/cron/{job_id}")
def edit_cron_job(job_id: str, body: CronJobUpdateModel):
    return update_hermes_cron_job(job_id, body.model_dump(exclude_none=True))


@router.delete("/cron/{job_id}")
def delete_cron_job(job_id: str):
    return delete_hermes_cron_job(job_id)


@router.get("/cron/{job_id}/outputs")
def read_cron_outputs(job_id: str):
    return get_hermes_cron_outputs(job_id)


@router.post("/reload-slow")
def reload_slow_worker():
    return reload_hermes_slow_worker()
