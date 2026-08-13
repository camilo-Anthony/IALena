import os
from typing import Optional

def get_masked_env_value(key: str) -> Optional[str]:
    """Obtiene un valor de entorno enmascarado para seguridad."""
    value = os.getenv(key)
    if not value:
        return None
    val = value.strip()
    if len(val) <= 12:
        return "****"
    return f"{val[:8]}...{val[-4:]}"

def mask_sensitive_config(config_dict: dict) -> dict:
    """Enmascara llaves y tokens sensibles en la configuración retornada."""
    masked = config_dict.copy()
    
    # Enmascarar claves de Google/Gemini
    for k in ["GEMINI_API_KEY", "GOOGLE_API_KEY"]:
        if k in masked and masked[k]:
            v = masked[k]
            masked[k] = f"{v[:8]}...{v[-4:]}" if len(v) > 12 else "****"

    # Enmascarar keys de Hermes
    for i in range(1, 30):
        k = f"HERMES_API_KEY_{i}"
        if k in masked and masked[k]:
            v = masked[k]
            masked[k] = f"{v[:8]}...{v[-4:]}" if len(v) > 12 else "****"
            
    return masked
