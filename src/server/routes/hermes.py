import subprocess
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel, Field
from src.server.kernel_bridge import (
    get_hermes_mcps,
    get_hermes_toolsets,
    get_tasks,
    dispatch_hermes_task,
    get_scheduler_and_sentinel_status,
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
    """Retorna la lista de skills instaladas en Hermes-Agent/skills."""
    root_dir = Path(__file__).resolve().parents[3]
    skills_dir = root_dir / "Hermes-Agent" / "skills"
    if not skills_dir.exists():
        return {"skills": []}
    skills = []
    for skill_path in sorted(skills_dir.iterdir()):
        if skill_path.is_dir() and not skill_path.name.startswith((".", "_")):
            readme_path = skill_path / "SKILL.md"
            desc = ""
            if readme_path.exists():
                try:
                    content = readme_path.read_text(encoding="utf-8")
                    for line in content.splitlines():
                        if line.startswith("description:"):
                            desc = line.split("description:", 1)[1].strip().strip('"').strip("'")
                            break
                    if not desc:
                        for line in content.splitlines():
                            if line.startswith("# "):
                                desc = line[2:].strip()
                                break
                except Exception:
                    pass
            skills.append({
                "name": skill_path.name,
                "description": desc or "Habilidad especializada de Hermes Agent",
            })
    return {"skills": skills}


@router.post("/launch")
def launch_hermes():
    return {"status": "ok", "message": "Hermes cockpit is integrated"}

