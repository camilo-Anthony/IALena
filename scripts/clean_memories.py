"""
scripts/clean_memories.py — Purga memorias alucinadas y restablece USER.md y MEMORY.md limpios.
"""
import os

def clean_memories():
    mem_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "hermes", "memories")
    os.makedirs(mem_dir, exist_ok=True)
    
    user_file = os.path.join(mem_dir, "USER.md")
    memory_file = os.path.join(mem_dir, "MEMORY.md")
    
    clean_user = (
        "Camilo: Desarrollador de JARVIS en Windows 11. Busca autonomía total, robustez y máxima eficiencia. "
        "Trato directo, conciso, profesional y elegante en español. Valora la verificación técnica y evita código inventado.\n"
        "§\n"
        "- [regla_comportamiento] Cuando el usuario pida música genérica sin especificar canción o artista ('pon música', 'reproduce algo'), preguntarle siempre primero por voz qué canción, artista o género desea escuchar antes de abrir YouTube.\n"
        "§\n"
        "- [preferencia_personal] El usuario no usa audífonos; usar siempre respuestas habladas limpias y concisas.\n"
    )
    
    clean_memory = (
        "El usuario opera el sistema JARVIS (ubicado en C:\\Users\\hp\\Documents\\PROYECTOS\\JARVIS) con arquitectura de dos velocidades (Voz Live + Hermes Core).\n"
        "§\n"
        "El usuario cuenta con integración de herramientas de escritorio, terminal PowerShell/Python, navegación web y Blender 3D.\n"
    )
    
    with open(user_file, "w", encoding="utf-8") as f:
        f.write(clean_user)
        
    with open(memory_file, "w", encoding="utf-8") as f:
        f.write(clean_memory)
        
    print("[OK] USER.md y MEMORY.md limpiados con exito. Memorias alucinadas purgadas.")

if __name__ == "__main__":
    clean_memories()
