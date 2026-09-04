"""
Sincroniza suites de skills seleccionadas desde Hermes-Agent/optional-skills/
hacia el directorio activo de Hermes (~/.hermes/skills/ o %LOCALAPPDATA%/hermes/skills/).
Solo copia carpetas que aún no existen en el destino.
"""
import os
import shutil
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPTIONAL_SKILLS_DIR = os.path.join(PROJECT_ROOT, "Hermes-Agent", "optional-skills")

# Suites a instalar (las que aportan mayor valor para desarrollo e investigación)
TARGET_SUITES = [
    "software-development",
    "devops",
    "web-development",
    "research",
    "autonomous-ai-agents",
    "security",
    "productivity",
    "creative",
    "communication",
    "mcp",
]

def get_hermes_skills_dir():
    """Detecta el directorio de skills activo de Hermes."""
    try:
        sys.path.insert(0, os.path.join(PROJECT_ROOT, "Hermes-Agent"))
        from hermes_constants import get_hermes_home
        home = str(get_hermes_home())
    except Exception:
        local = os.path.join(os.environ.get("LOCALAPPDATA", ""), "hermes")
        home_dir = os.path.join(os.path.expanduser("~"), ".hermes")
        home = local if os.path.isdir(local) else home_dir
    return os.path.join(home, "skills")

def sync_skills():
    dest_dir = get_hermes_skills_dir()
    os.makedirs(dest_dir, exist_ok=True)
    
    existing = set(os.listdir(dest_dir))
    installed = []
    skipped = []
    
    for suite in TARGET_SUITES:
        src = os.path.join(OPTIONAL_SKILLS_DIR, suite)
        if not os.path.isdir(src):
            print(f"  [SKIP] Suite no encontrada: {suite}")
            skipped.append(suite)
            continue
        
        # Cada suite puede tener sub-skills (carpetas con SKILL.md dentro)
        for entry in os.listdir(src):
            entry_path = os.path.join(src, entry)
            if not os.path.isdir(entry_path):
                continue
            
            # Verificar que tiene un archivo SKILL.md o similar
            has_skill_def = any(
                f.lower() in ("skill.md", "skill.yaml", "skill.yml", "config.yaml")
                for f in os.listdir(entry_path)
            )
            
            if not has_skill_def:
                # Es una categoría contenedora, buscar sub-carpetas
                for sub in os.listdir(entry_path):
                    sub_path = os.path.join(entry_path, sub)
                    if os.path.isdir(sub_path):
                        dest_path = os.path.join(dest_dir, sub)
                        if sub not in existing:
                            shutil.copytree(sub_path, dest_path)
                            installed.append(f"{suite}/{entry}/{sub}")
                            existing.add(sub)
                        else:
                            skipped.append(f"{suite}/{entry}/{sub} (ya existe)")
            else:
                dest_path = os.path.join(dest_dir, entry)
                if entry not in existing:
                    shutil.copytree(entry_path, dest_path)
                    installed.append(f"{suite}/{entry}")
                    existing.add(entry)
                else:
                    skipped.append(f"{suite}/{entry} (ya existe)")
    
    print(f"\n{'='*60}")
    print(f"  Skills sincronizadas: {len(installed)}")
    print(f"  Skills omitidas:      {len(skipped)}")
    print(f"  Directorio destino:   {dest_dir}")
    print(f"{'='*60}")
    
    if installed:
        print("\n  INSTALADAS:")
        for s in installed:
            print(f"    + {s}")
    
    if skipped:
        print("\n  OMITIDAS (ya existian o no encontradas):")
        for s in skipped[:10]:
            print(f"    - {s}")
        if len(skipped) > 10:
            print(f"    ... y {len(skipped) - 10} mas")
    
    return installed

if __name__ == "__main__":
    sync_skills()
