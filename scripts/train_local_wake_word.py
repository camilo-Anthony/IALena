"""
train_local_wake_word.py — Entrenador local con negativos REALES del micrófono.

Fase 1: Graba ~30s de ambiente real (ventilador, respiración, eco de tu cuarto).
Fase 2: Combina esos negativos reales + sintéticos contra tus muestras de "Tess".
Fase 3: Entrena y exporta a ONNX compatible con openWakeWord.

Esto elimina falsos positivos porque el modelo aprende qué es tu ruido ambiental real.
"""
import os
import sys
import glob
import wave
import struct
import zipfile
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Forzar flush en todos los prints para ver output en tiempo real
import functools
print = functools.partial(print, flush=True)


# ─── Utilidades de audio ───────────────────────────────────────────────

def load_wav_padded(path: str, target_length: int = 40000) -> np.ndarray:
    with wave.open(path, 'rb') as wf:
        n_channels = wf.getnchannels()
        raw_data = wf.readframes(wf.getnframes())

    data = np.frombuffer(raw_data, dtype=np.int16)
    if n_channels > 1:
        data = data[::n_channels]

    if len(data) < target_length:
        pad_total = target_length - len(data)
        pad_left = pad_total // 2
        pad_right = pad_total - pad_left
        data = np.pad(data, (pad_left, pad_right), mode='constant')
    elif len(data) > target_length:
        data = data[:target_length]

    return data


def augment_audio(audio: np.ndarray) -> list[np.ndarray]:
    """Genera variaciones de un clip de audio."""
    augmented = [audio.copy()]

    # Ganancias
    augmented.append(np.clip(audio * 0.5, -32768, 32767).astype(np.int16))
    augmented.append(np.clip(audio * 0.7, -32768, 32767).astype(np.int16))
    augmented.append(np.clip(audio * 1.3, -32768, 32767).astype(np.int16))
    augmented.append(np.clip(audio * 1.6, -32768, 32767).astype(np.int16))

    # Ruido aditivo suave
    for noise_level in [0.005, 0.01, 0.02]:
        noise = np.random.normal(0, noise_level * 32768, len(audio)).astype(np.int16)
        augmented.append(np.clip(audio + noise, -32768, 32767).astype(np.int16))

    # Variaciones de velocidad
    for rate in [0.90, 0.95, 1.05, 1.10]:
        idx = np.round(np.arange(0, len(audio), rate)).astype(int)
        idx = idx[idx < len(audio)]
        if len(idx) < len(audio):
            aug = np.pad(audio[idx], (0, len(audio) - len(idx)), mode='constant')
        else:
            aug = audio[idx][:len(audio)]
        augmented.append(aug)

    return augmented


def extract_features(audio: np.ndarray, preprocessor) -> list[np.ndarray]:
    """Extrae ventanas de features [16, 96] usando el preprocesador de openWakeWord."""
    chunk_samples = 1280
    features = []
    preprocessor.reset()

    for i in range(0, len(audio) - chunk_samples + 1, chunk_samples):
        chunk = audio[i:i + chunk_samples].astype(np.int16)
        preprocessor(chunk)
        feat = preprocessor.get_features(16)
        if feat is not None and feat.shape == (1, 16, 96):
            features.append(feat[0].copy())

    return features


# ─── Captura de audio ambiente ─────────────────────────────────────────

def record_ambient_noise(duration_seconds: int = 30) -> np.ndarray:
    """
    Graba audio ambiente real del micrófono para usar como negativos.
    Retorna un array int16 de PCM a 16kHz mono.
    """
    try:
        import pyaudio
    except ImportError:
        print("[WARN] pyaudio no disponible, intentando con sounddevice...")
        return _record_with_sounddevice(duration_seconds)

    RATE = 16000
    CHUNK = 1024
    pa = pyaudio.PyAudio()

    # Buscar el dispositivo de entrada predeterminado
    default_device = None
    try:
        info = pa.get_default_input_device_info()
        default_device = info['index']
        print(f"[MIC] Usando: {info['name']}")
    except Exception:
        print("[MIC] Usando dispositivo predeterminado del sistema")

    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=RATE,
        input=True,
        input_device_index=default_device,
        frames_per_buffer=CHUNK,
    )

    print(f"\n{'=' * 50}")
    print(f"  🎙️  GRABANDO {duration_seconds}s DE RUIDO AMBIENTE")
    print(f"  ⚠️  NO hables. Quédate en silencio normal.")
    print(f"  (ventilador, teclado, respiración = OK)")
    print(f"{'=' * 50}\n")

    frames = []
    total_chunks = int(RATE / CHUNK * duration_seconds)
    for i in range(total_chunks):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        # Progreso cada 5 segundos
        elapsed = (i + 1) * CHUNK / RATE
        if int(elapsed) % 5 == 0 and int(elapsed) > 0 and (i * CHUNK / RATE) % 5 < (CHUNK / RATE):
            print(f"  ⏱️  {int(elapsed)}s / {duration_seconds}s grabados...")

    stream.stop_stream()
    stream.close()
    pa.terminate()

    raw_bytes = b''.join(frames)
    audio = np.frombuffer(raw_bytes, dtype=np.int16)
    print(f"[OK] Captura ambiente completada: {len(audio)} muestras ({len(audio)/RATE:.1f}s)")
    return audio


def _record_with_sounddevice(duration_seconds: int) -> np.ndarray:
    """Fallback usando sounddevice si pyaudio no está disponible."""
    import sounddevice as sd
    RATE = 16000
    print(f"\n{'=' * 50}")
    print(f"  🎙️  GRABANDO {duration_seconds}s DE RUIDO AMBIENTE")
    print(f"  ⚠️  NO hables. Quédate en silencio normal.")
    print(f"{'=' * 50}\n")

    audio = sd.rec(int(duration_seconds * RATE), samplerate=RATE, channels=1, dtype='int16')
    sd.wait()
    print(f"[OK] Captura ambiente completada: {len(audio)} muestras ({len(audio)/RATE:.1f}s)")
    return audio.flatten()


def save_ambient_wav(audio: np.ndarray, path: str) -> None:
    """Guarda el audio ambiente como .wav para futuros re-entrenamientos."""
    RATE = 16000
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(audio.tobytes())


# ─── Entrenamiento principal ───────────────────────────────────────────

def main():
    print("=" * 65)
    print("  [TRAINER] ENTRENADOR LOCAL v2 — CON NEGATIVOS REALES DEL MIC")
    print("=" * 65)

    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import TensorDataset, DataLoader

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_dir = os.path.join(project_root, "models")
    wake_word = "tess"

    samples_dir = os.path.join(models_dir, "custom_wake_word", wake_word)
    zip_file = os.path.join(models_dir, f"{wake_word}_samples.zip")

    if os.path.exists(zip_file) and not os.path.exists(samples_dir):
        print(f"[INFO] Descomprimiendo {zip_file}...")
        os.makedirs(samples_dir, exist_ok=True)
        with zipfile.ZipFile(zip_file, 'r') as zf:
            zf.extractall(samples_dir)

    wav_files = glob.glob(os.path.join(samples_dir, "*.wav"))
    if not wav_files:
        wav_files = glob.glob(os.path.join(models_dir, "*.wav"))
    if not wav_files:
        print(f"[ERROR] No se encontraron grabaciones en {samples_dir}.")
        return

    print(f"[OK] Se encontraron {len(wav_files)} muestras de voz para '{wake_word}'.")

    # ─── Fase 0: Captura de ambiente real ──────────────────────────────
    ambient_wav_path = os.path.join(models_dir, "custom_wake_word", "ambient_noise.wav")

    # Reusar grabación previa automáticamente si existe y es reciente
    reuse_ambient = False
    if os.path.exists(ambient_wav_path):
        file_size = os.path.getsize(ambient_wav_path)
        if file_size > 100000:  # > ~3 segundos
            # Reusar si fue grabado hace menos de 24 horas
            import time as _time
            age_hours = (_time.time() - os.path.getmtime(ambient_wav_path)) / 3600
            if age_hours < 24:
                reuse_ambient = True
                print(f"[INFO] Reusando grabación ambiente reciente ({file_size} bytes, {age_hours:.1f}h).")
            else:
                print(f"[INFO] Grabación ambiente antigua ({age_hours:.0f}h). Grabando nueva...")

    if reuse_ambient:
        ambient_audio = load_wav_padded(ambient_wav_path, target_length=16000 * 30)
    else:
        print("\n[PASO 1/4] Capturando audio ambiente de tu habitación...")
        ambient_audio = record_ambient_noise(duration_seconds=30)
        # Guardar para futuros re-entrenamientos
        os.makedirs(os.path.dirname(ambient_wav_path), exist_ok=True)
        save_ambient_wav(ambient_audio, ambient_wav_path)
        print(f"[OK] Ambiente guardado en {ambient_wav_path} para futuros usos.\n")

    # ─── Fase 1: Preprocesador ─────────────────────────────────────────
    print("[PASO 2/4] Inicializando preprocesador de openWakeWord...")
    import openwakeword
    # Intentar descargar modelos pero no bloquear si falla
    try:
        openwakeword.utils.download_models()
    except Exception as e:
        print(f"[WARN] Descarga de modelos omitida: {e}")

    import openwakeword.model
    test_model = openwakeword.model.Model(wakeword_models=["hey_jarvis"])
    preprocessor = test_model.preprocessor

    # ─── Fase 2: Features Positivos ───────────────────────────────────
    print("[PASO 3/4] Extrayendo características...")

    # 2a. Positivos: tus grabaciones + augmentations
    print("  ► Procesando muestras positivas (voz real)...")
    pos_features = []
    for wav_path in wav_files:
        padded_audio = load_wav_padded(wav_path, target_length=40000)
        for clip in augment_audio(padded_audio):
            pos_features.extend(extract_features(clip, preprocessor))

    print(f"  [OK] Muestras positivas: {len(pos_features)} ventanas")

    # ─── Fase 3: Features Negativos (REALES + sintéticos) ─────────────
    print("  ► Procesando muestras negativas (ambiente real + sintéticas)...")
    neg_features = []

    # 3a. NEGATIVOS REALES del micrófono (los más importantes)
    # Segmentar en clips de 2.5s con overlap de 1s
    ambient_len = len(ambient_audio)
    clip_len = 40000  # 2.5s a 16kHz
    step = 16000  # 1s de avance
    ambient_clip_count = 0
    for start in range(0, ambient_len - clip_len + 1, step):
        clip = ambient_audio[start:start + clip_len]
        neg_features.extend(extract_features(clip, preprocessor))
        # Augmentar los clips reales también
        noise = np.random.normal(0, 0.005 * 32768, len(clip)).astype(np.int16)
        noisy_clip = np.clip(clip.astype(np.int32) + noise, -32768, 32767).astype(np.int16)
        neg_features.extend(extract_features(noisy_clip, preprocessor))
        ambient_clip_count += 1

    print(f"    - Clips ambiente real: {ambient_clip_count} (x2 con augmentation)")

    # 3b. Silencios puros
    for duration_s in [2, 3, 5]:
        silence = np.zeros(16000 * duration_s, dtype=np.int16)
        neg_features.extend(extract_features(silence, preprocessor))

    # 3c. Ruidos gaussianos de varias intensidades
    for std in [0.001, 0.003, 0.008, 0.015, 0.03, 0.06, 0.10, 0.15]:
        noise = (np.random.normal(0, std, 16000 * 4) * 32768).clip(-32768, 32767).astype(np.int16)
        neg_features.extend(extract_features(noise, preprocessor))

    # 3d. Tonos armónicos (emula voz humana genérica, música, TV)
    t = np.linspace(0, 3, 16000 * 3)
    for base_freq in [100, 150, 200, 300, 500, 800, 1200, 2000, 3500]:
        harmonic = (0.4 * np.sin(2 * np.pi * base_freq * t) +
                    0.25 * np.sin(2 * np.pi * 2 * base_freq * t) +
                    0.15 * np.sin(2 * np.pi * 3 * base_freq * t)) * 0.15 * 32768
        neg_features.extend(extract_features(harmonic.astype(np.int16), preprocessor))

    # 3e. Ruido modulado (respiración, clicks, aire acondicionado)
    for mod_rate in [0.5, 1.0, 2.0, 4.0, 8.0]:
        mod = 0.5 + 0.5 * np.sin(2 * np.pi * mod_rate * t)
        carrier = np.random.normal(0, 0.04, len(t)) * mod * 32768
        neg_features.extend(extract_features(carrier.astype(np.int16), preprocessor))

    # 3f. Impulsos y clicks (teclado, mouse)
    for _ in range(5):
        clicks = np.zeros(16000 * 3, dtype=np.float64)
        n_clicks = np.random.randint(5, 20)
        for _ in range(n_clicks):
            pos = np.random.randint(0, len(clicks))
            width = np.random.randint(50, 300)
            amplitude = np.random.uniform(0.05, 0.3) * 32768
            clicks[pos:pos + width] = amplitude * np.random.choice([-1, 1])
        neg_features.extend(extract_features(clicks.astype(np.int16), preprocessor))

    # 3g. Muestras de VOZ HUMANA REAL (Conversaciones, podcasts, TV - otras palabras)
    val_feat_path = os.path.join(models_dir, "validation_set_features.npy")
    if os.path.exists(val_feat_path):
        print("  ► Cargando dataset de VOZ HUMANA REAL (otras palabras) para negativos...")
        speech_raw = np.load(val_feat_path, mmap_mode='r')
        n_speech_frames = len(speech_raw)
        # Extraer ventanas de 16 frames de habla real
        target_speech_neg = max(len(pos_features) * 4, 25000)
        speech_indices = np.random.randint(0, n_speech_frames - 16, target_speech_neg)
        for idx in speech_indices:
            neg_features.append(speech_raw[idx : idx + 16].copy())
        print(f"  [OK] Ventanas de habla humana real añadidas como negativo: {len(speech_indices)}")

    # Balancear negativos 5:1 contra positivos para máxima robustez
    target_neg = len(pos_features) * 5
    while len(neg_features) < target_neg:
        # Mezclar ambiente real con ruido aleatorio
        seg_start = np.random.randint(0, max(1, ambient_len - clip_len))
        seg = ambient_audio[seg_start:seg_start + clip_len].copy()
        noise = (np.random.normal(0, np.random.uniform(0.002, 0.04), len(seg)) * 32768).astype(np.int16)
        mixed = np.clip(seg.astype(np.int32) + noise, -32768, 32767).astype(np.int16)
        neg_features.extend(extract_features(mixed, preprocessor))

    print(f"  [OK] Total muestras negativas: {len(neg_features)} ventanas")
    print(f"  [OK] Ratio neg/pos: {len(neg_features)/max(1, len(pos_features)):.1f}:1")

    # ─── Fase 4: Entrenar red neuronal ─────────────────────────────────
    print("\n[PASO 4/4] Entrenando red neuronal...")

    X_pos = np.array(pos_features, dtype=np.float32)
    y_pos = np.ones((len(X_pos), 1), dtype=np.float32)

    X_neg = np.array(neg_features[:target_neg], dtype=np.float32)
    y_neg = np.zeros((len(X_neg), 1), dtype=np.float32)

    X = np.concatenate([X_pos, X_neg], axis=0)
    y = np.concatenate([y_pos, y_neg], axis=0)

    perm = np.random.permutation(len(X))
    X = X[perm]
    y = y[perm]

    # Split train/val 85/15
    split_idx = int(len(X) * 0.85)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    train_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
    val_ds = TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val))
    train_dl = DataLoader(train_ds, batch_size=64, shuffle=True)
    val_dl = DataLoader(val_ds, batch_size=128, shuffle=False)

    print(f"  Dataset: {len(X_train)} train + {len(X_val)} val")

    # Red más profunda con regularización agresiva
    class WakeWordClassifier(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Flatten(),
                nn.Linear(16 * 96, 128),
                nn.BatchNorm1d(128),
                nn.ReLU(),
                nn.Dropout(0.4),
                nn.Linear(128, 64),
                nn.BatchNorm1d(64),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(64, 32),
                nn.BatchNorm1d(32),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(32, 1),
                nn.Sigmoid()
            )

        def forward(self, x):
            return self.net(x)

    model = WakeWordClassifier()
    criterion = nn.BCELoss()
    optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=5e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=60)

    best_val_acc = 0.0
    best_state = None
    epochs = 60

    for epoch in range(1, epochs + 1):
        # Train
        model.train()
        total_loss, correct, total = 0.0, 0, 0
        for batch_X, batch_y in train_dl:
            optimizer.zero_grad()
            preds = model(batch_X)
            loss = criterion(preds, batch_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(batch_X)
            correct += ((preds >= 0.5) == (batch_y >= 0.5)).sum().item()
            total += len(batch_X)

        train_acc = (correct / total) * 100.0
        train_loss = total_loss / total

        # Validation
        model.eval()
        val_correct, val_total = 0, 0
        val_fp, val_fn = 0, 0
        with torch.no_grad():
            for batch_X, batch_y in val_dl:
                preds = model(batch_X)
                predicted = (preds >= 0.5).float()
                actual = (batch_y >= 0.5).float()
                val_correct += (predicted == actual).sum().item()
                val_total += len(batch_X)
                # Falsos positivos: predijo 1 pero era 0
                val_fp += ((predicted == 1) & (actual == 0)).sum().item()
                # Falsos negativos: predijo 0 pero era 1
                val_fn += ((predicted == 0) & (actual == 1)).sum().item()

        val_acc = (val_correct / val_total) * 100.0
        scheduler.step()

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

        if epoch % 10 == 0 or epoch == epochs:
            print(f"  Época [{epoch:02d}/{epochs}] — Train: {train_acc:.1f}% (loss={train_loss:.4f}) | "
                  f"Val: {val_acc:.1f}% (FP={val_fp}, FN={val_fn})")

    # Restaurar mejor modelo
    if best_state is not None:
        model.load_state_dict(best_state)
        print(f"\n  [BEST] Mejor validación: {best_val_acc:.2f}%")

    # ─── Exportar a ONNX ──────────────────────────────────────────────
    output_onnx_path = os.path.join(models_dir, f"{wake_word}.onnx")
    print(f"\n[EXPORT] Exportando modelo a {output_onnx_path}...")
    model.eval()
    dummy_input = torch.randn(1, 16, 96, dtype=torch.float32)

    torch.onnx.export(
        model,
        dummy_input,
        output_onnx_path,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
        opset_version=14,
        dynamo=False,
    )

    file_size = os.path.getsize(output_onnx_path)
    print(f"[SUCCESS] ¡Modelo '{wake_word}.onnx' generado! ({file_size} bytes)")

    # ─── Test rápido de validación ─────────────────────────────────────
    print(f"\n{'=' * 50}")
    print("  VALIDACIÓN RÁPIDA")
    print(f"{'=' * 50}")

    import onnxruntime as ort
    session = ort.InferenceSession(output_onnx_path)

    in_name = session.get_inputs()[0].name

    # Test 1: Silencio puro
    silence_feat = np.zeros((1, 16, 96), dtype=np.float32)
    silence_score = session.run(None, {in_name: silence_feat})[0][0][0]
    status1 = "✅" if silence_score < 0.1 else "⚠️"
    print(f"  {status1} Silencio puro:     score = {silence_score:.4f}")

    # Test 2: Ruido gaussiano
    noise_feat = np.random.randn(1, 16, 96).astype(np.float32) * 0.1
    noise_score = session.run(None, {in_name: noise_feat})[0][0][0]
    status2 = "✅" if noise_score < 0.1 else "⚠️"
    print(f"  {status2} Ruido gaussiano:   score = {noise_score:.4f}")

    # Test 3: Features de ambiente real
    if len(neg_features) > 0:
        amb_feat = neg_features[0][np.newaxis, :, :].astype(np.float32)
        amb_score = session.run(None, {in_name: amb_feat})[0][0][0]
        status3 = "✅" if amb_score < 0.2 else "⚠️"
        print(f"  {status3} Ambiente real mic: score = {amb_score:.4f}")

    # Test 4: Features de tu voz 'Tess'
    if len(pos_features) > 0:
        pos_feat = pos_features[0][np.newaxis, :, :].astype(np.float32)
        pos_score = session.run(None, {in_name: pos_feat})[0][0][0]
        status4 = "✅" if pos_score > 0.7 else "⚠️"
        print(f"  {status4} Tu voz 'Tess':           score = {pos_score:.4f}")

    # Test 5: Features de otras conversaciones humanas (Adversarial)
    if os.path.exists(val_feat_path):
        val_speech = np.load(val_feat_path, mmap_mode='r')
        test_samples = [val_speech[i:i+16][np.newaxis, :, :] for i in range(100, 1100, 100)]
        scores = [session.run(None, {in_name: s.astype(np.float32)})[0][0][0] for s in test_samples]
        avg_speech_score = float(np.mean(scores))
        max_speech_score = float(np.max(scores))
        status5 = "✅" if max_speech_score < 0.2 else "⚠️"
        print(f"  {status5} Otras conversaciones:    max = {max_speech_score:.4f} (promedio = {avg_speech_score:.4f})")

    print(f"\n{'=' * 50}")
    print("  LISTO — Reinicia JARVIS para usar el nuevo modelo.")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    main()
