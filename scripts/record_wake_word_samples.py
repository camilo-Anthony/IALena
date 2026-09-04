"""
record_wake_word_samples.py — Asistente interactivo para grabar tu voz y entrenar tu propio Wake Word.

Graba muestras de audio en formato estándar (16kHz, 16-bit, Mono) para alimentar
el entrenamiento del modelo personalizado en Google Colab o localmente.
"""
import os
import sys
import time
import wave
import zipfile

try:
    import pyaudio
except ImportError:
    print("[Error] PyAudio no está instalado en el entorno actual.")
    print("Ejecuta: pip install pyaudio")
    sys.exit(1)

RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK = 1024
DURATION_SECONDS = 2.0  # Duración de cada grabación

def record_sample(p: pyaudio.PyAudio, output_path: str, duration: float = 2.0):
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    print("  🎤 GRABANDO... ¡Di tu palabra clave ahora!")
    frames = []
    num_chunks = int(RATE / CHUNK * duration)
    
    for _ in range(num_chunks):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    print("  ✅ Muestra capturada.")

    # Guardar en archivo WAV
    with wave.open(output_path, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

def main():
    print("=" * 65)
    print("  🎙️  GRABADOR DE MUESTRAS DE VOZ PARA TU PROPIO ACTIVADOR")
    print("=" * 65)
    print("Este asistente te guiará para grabar varias muestras de tu voz")
    print("diciendo la palabra de activación deseada (por ejemplo: 'Tess').\n")

    wake_word = input("👉 ¿Cuál es tu palabra de activación? (ej: tess): ").strip()
    if not wake_word:
        wake_word = "tess"

    sanitized_name = "".join(c for c in wake_word.lower() if c.isalnum() or c in ("_", "-"))

    total_samples_input = input("👉 ¿Cuántas muestras deseas grabar? (Recomendado: 15-20, default 15): ").strip()
    try:
        total_samples = int(total_samples_input)
    except ValueError:
        total_samples = 15

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    samples_dir = os.path.join(project_root, "models", "custom_wake_word", sanitized_name)
    os.makedirs(samples_dir, exist_ok=True)

    print(f"\n📁 Las grabaciones se guardarán en:\n   {samples_dir}\n")
    print("💡 CONSEJOS PARA UN ENTRENAMIENTO PERFECTO:")
    print("   1. Graba algunas muestras cerca del micrófono y otras a media distancia.")
    print("   2. Varía ligeramente la entonación y la velocidad al pronunciar.")
    print("   3. Mantén silencio antes de presionar ENTER.\n")

    p = pyaudio.PyAudio()

    try:
        for i in range(1, total_samples + 1):
            sample_file = os.path.join(samples_dir, f"{sanitized_name}_{i:02d}.wav")
            print("-" * 50)
            input(f"[{i}/{total_samples}] Presiona ENTER y di '{wake_word}' inmediatamente...")
            record_sample(p, sample_file, duration=DURATION_SECONDS)
            time.sleep(0.3)
    finally:
        p.terminate()

    # Comprimir en archivo ZIP para fácil subida a Google Colab
    zip_path = os.path.join(project_root, "models", f"{sanitized_name}_samples.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(samples_dir):
            for file in files:
                if file.endswith(".wav"):
                    zf.write(os.path.join(root, file), arcname=file)

    print("\n" + "=" * 65)
    print("  🎉 ¡GRABACIÓN COMPLETADA CON ÉXITO!")
    print("=" * 65)
    print(f"Se grabaron {total_samples} muestras de tu voz.")
    print(f"\n📦 Archivo ZIP listo para entrenar:")
    print(f"   {zip_path}\n")
    print("🚀 SIGUIENTE PASO:")
    print("1. Abre el Google Colab oficial de openWakeWord:")
    print("   https://colab.research.google.com/github/dscripka/openWakeWord/blob/main/notebooks/openwakeword_custom_model_training.ipynb")
    print(f"2. En la celda de configuración, escribe: '{wake_word}'")
    print(f"3. Sube el archivo '{sanitized_name}_samples.zip' cuando el notebook te lo solicite.")
    print(f"4. Ejecuta el entrenamiento (~30 min con GPU gratis).")
    print(f"5. Coloca el archivo '{sanitized_name}.onnx' generado dentro de la carpeta 'models/'.")
    print(f"6. En tu archivo .env configura: WAKE_WORD_MODEL={sanitized_name}")
    print("=" * 65)

if __name__ == "__main__":
    main()
