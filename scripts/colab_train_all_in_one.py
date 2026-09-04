# ==============================================================================
# 🧠 ENTRENADOR TODO-EN-UNO DE ACTIVADOR "TESS" PARA GOOGLE COLAB (1-CLICK)
# ==============================================================================
# 100% AUTÓNOMO: No depende de repositorios externos ni paquetes problemáticos.
# Utiliza ONNXRuntime + PyTorch directamente con los modelos de Google Speech Embedding.
#
# INSTRUCCIONES:
# 1. Abre https://colab.research.google.com/ y crea un "Nuevo Cuaderno".
# 2. Menú: Entorno de ejecución -> Cambiar tipo -> Selecciona T4 GPU -> Guardar.
# 3. Pega TODO este código en UNA SOLA CELDA y dale a "Ejecutar" (Play).
# 4. Sube tu archivo 'tess_samples.zip' cuando te lo pida.
# 5. Al terminar, tu navegador descargará automáticamente 'tess.onnx'.
# ==============================================================================

import os
import sys
import zipfile
import glob
import wave
import subprocess
import shutil

print("=" * 70)
print("🚀 [1/6] PREPARANDO ENTORNO EN GOOGLE COLAB...")
print("=" * 70)

# 1. Instalar dependencias estándar de Python
subprocess.run("pip install -q onnx onnxruntime onnxscript torch torchaudio scipy tqdm", shell=True)

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
import onnxruntime as ort

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"✅ Entorno listo. Dispositivo de entrenamiento: {device}")

# 2. Descargar modelos base de extracción de características de openWakeWord
os.makedirs("base_models", exist_ok=True)
melspec_path = "base_models/melspectrogram.onnx"
embed_path = "base_models/embedding_model.onnx"

if not os.path.exists(melspec_path):
    print("Descargando extractor melspectrograma...")
    subprocess.run(f"wget -q https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/melspectrogram.onnx -O {melspec_path}", shell=True)

if not os.path.exists(embed_path):
    print("Descargando extractor speech embedding...")
    subprocess.run(f"wget -q https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/embedding_model.onnx -O {embed_path}", shell=True)

# 3. Motor de extracción autónomo (Pure ONNXRuntime)
class AutonomousFeatureExtractor:
    def __init__(self, melspec_model_file, embed_model_file):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        self.mel_session = ort.InferenceSession(melspec_model_file, sess_options=opts, providers=["CPUExecutionProvider"])
        self.embed_session = ort.InferenceSession(embed_model_file, sess_options=opts, providers=["CPUExecutionProvider"])

    def get_embeddings(self, audio_pcm_16k):
        # Audio a float32 con forma [1, N]
        x = np.array(audio_pcm_16k, dtype=np.float32)
        if len(x.shape) == 1:
            x = x[np.newaxis, :]
        
        # 1. Melspectrograma
        mel_out = self.mel_session.run(None, {"input": x})
        spec = np.squeeze(mel_out[0]) / 10.0 + 2.0  # Normalización estándar Google
        
        # 2. Ventanas deslizantes de 76 frames
        windows = []
        for i in range(0, spec.shape[0] - 76 + 1, 8):
            windows.append(spec[i : i + 76])
        
        if not windows:
            return np.empty((0, 96), dtype=np.float32)
        
        batch = np.expand_dims(np.array(windows), axis=-1).astype(np.float32)
        # 3. Embeddings [N_windows, 96]
        embeddings = self.embed_session.run(None, {"input_1": batch})[0].squeeze()
        if len(embeddings.shape) == 1:
            embeddings = embeddings[np.newaxis, :]
        return embeddings

    def extract_16frame_windows(self, audio_pcm_16k):
        """Extrae ventanas de 16 frames consecutivas [16, 96] para el clasificador."""
        embeddings = self.get_embeddings(audio_pcm_16k)
        windows_16 = []
        for i in range(0, len(embeddings) - 16 + 1, 1):
            windows_16.append(embeddings[i : i + 16])
        return windows_16

extractor = AutonomousFeatureExtractor(melspec_path, embed_path)
print("✅ Extractor de características acústicas listo.")

# ==============================================================================
# 2. SUBIDA DE MUESTRAS DE VOZ
# ==============================================================================
print("\n" + "=" * 70)
print("🎙️ [2/6] SUBIDA DE TUS GRABACIONES DE VOZ")
print("=" * 70)

from google.colab import files
os.makedirs("./custom_samples", exist_ok=True)

print("👉 Por favor selecciona 'tess_samples.zip' (o los archivos .wav):")
uploaded = files.upload()

for fn in uploaded.keys():
    if fn.endswith('.zip'):
        with zipfile.ZipFile(fn, 'r') as zf:
            zf.extractall("./custom_samples")
        print(f"📦 Descomprimido: {fn}")
    elif fn.endswith('.wav'):
        shutil.move(fn, os.path.join("./custom_samples", fn))

wav_files = glob.glob("./custom_samples/**/*.wav", recursive=True)
print(f"✅ Total de grabaciones de voz cargadas: {len(wav_files)}")
if not wav_files:
    raise ValueError("❌ No se encontraron archivos .wav. Sube tess_samples.zip e intenta nuevamente.")

# ==============================================================================
# 3. DESCARGA DE NEGATIVOS MASIVOS (ACAV100M - 2000 HORAS DE FONDO)
# ==============================================================================
print("\n" + "=" * 70)
print("📥 [3/6] DESCARGANDO DATASET NEGATIVO (2,000 HORAS DE AUDIO DE FONDO)...")
print("=" * 70)

if not os.path.exists("acav100m_negatives.npy"):
    print("Descargando embeddings de ACAV100M (~120MB)...")
    subprocess.run("wget -q https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/openwakeword_features_ACAV100M_2000_hrs_16bit.npy -O acav100m_negatives.npy", shell=True)

print("✅ Dataset negativo listo.")

# ==============================================================================
# 4. EXTRACCIÓN Y AUMENTO DE DATOS
# ==============================================================================
print("\n" + "=" * 70)
print("⚙️ [4/6] PROCESANDO Y AUMENTANDO MUESTRAS...")
print("=" * 70)

pos_features = []
for wav_p in wav_files:
    with wave.open(wav_p, 'rb') as wf:
        n_ch = wf.getnchannels()
        raw = wf.readframes(wf.getnframes())
        data = np.frombuffer(raw, dtype=np.int16)
        if n_ch > 1: data = data[::n_ch]
    
    # Padding a 2.5s (40000 muestras)
    target_len = 40000
    if len(data) < target_len:
        pad = target_len - len(data)
        data = np.pad(data, (pad // 2, pad - pad // 2), mode='constant')
    else:
        data = data[:target_len]

    # Data Augmentation (variaciones de ganancia, ruido y velocidad)
    for gain in [0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 1.8]:
        aug = np.clip(data * gain, -32768, 32767).astype(np.int16)
        pos_features.extend(extractor.extract_16frame_windows(aug))
        
        # Ruido aditivo
        noise = np.random.normal(0, 0.008 * 32768, len(data)).astype(np.int16)
        pos_features.extend(extractor.extract_16frame_windows(np.clip(aug.astype(np.int32) + noise, -32768, 32767).astype(np.int16)))

    for rate in [0.92, 0.96, 1.04, 1.08]:
        idx = np.round(np.arange(0, len(data), rate)).astype(int)
        idx = idx[idx < len(data)]
        speed_clip = np.pad(data[idx], (0, max(0, len(data) - len(idx))), mode='constant')[:len(data)]
        pos_features.extend(extractor.extract_16frame_windows(speed_clip))

X_pos = np.array(pos_features, dtype=np.float32)
print(f"✅ Muestras positivas extraídas: {len(X_pos)} ventanas de features [16, 96]")

# Cargar negativos balanceados 4:1
acav = np.load("acav100m_negatives.npy", mmap_mode='r')
target_neg = len(X_pos) * 4
neg_idx = np.random.choice(len(acav), target_neg, replace=False)
X_neg = np.array(acav[neg_idx], dtype=np.float32)
print(f"✅ Muestras negativas seleccionadas: {len(X_neg)} ventanas (Ratio 4:1)")

X = np.concatenate([X_pos, X_neg], axis=0)
y = np.concatenate([np.ones((len(X_pos), 1), dtype=np.float32), 
                    np.zeros((len(X_neg), 1), dtype=np.float32)], axis=0)

perm = np.random.permutation(len(X))
X, y = X[perm], y[perm]

split = int(0.85 * len(X))
X_train, X_val = X[:split], X[split:]
y_train, y_val = y[:split], y[split:]

train_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
val_ds = TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val))

train_loader = DataLoader(train_ds, batch_size=128, shuffle=True)
val_loader = DataLoader(val_ds, batch_size=256, shuffle=False)

# ==============================================================================
# 5. RED NEURONAL Y ENTRENAMIENTO
# ==============================================================================
print("\n" + "=" * 70)
print("🧠 [5/6] ENTRENANDO RED NEURONAL EN GPU...")
print("=" * 70)

class WakeWordNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Flatten(),
            nn.Linear(16 * 96, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.35),
            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(0.25),
            nn.Linear(64, 32),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        return self.net(x)

model = WakeWordNet().to(device)
criterion = nn.BCELoss()
optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=60)

epochs = 60
best_val_acc = 0.0
best_weights = None

for epoch in range(1, epochs + 1):
    model.train()
    train_loss, train_corr, train_tot = 0.0, 0, 0
    for bx, by in train_loader:
        bx, by = bx.to(device), by.to(device)
        optimizer.zero_grad()
        out = model(bx)
        loss = criterion(out, by)
        loss.backward()
        optimizer.step()
        train_loss += loss.item() * len(bx)
        train_corr += ((out >= 0.5) == (by >= 0.5)).sum().item()
        train_tot += len(bx)

    scheduler.step()

    # Validación
    model.eval()
    val_corr, val_tot = 0, 0
    fp, fn = 0, 0
    with torch.no_grad():
        for bx, by in val_loader:
            bx, by = bx.to(device), by.to(device)
            out = model(bx)
            p = (out >= 0.5).float()
            val_corr += (p == by).sum().item()
            val_tot += len(bx)
            fp += ((p == 1) & (by == 0)).sum().item()
            fn += ((p == 0) & (by == 1)).sum().item()

    val_acc = (val_corr / val_tot) * 100.0
    if val_acc > best_val_acc:
        best_val_acc = val_acc
        best_weights = {k: v.clone() for k, v in model.state_dict().items()}

    if epoch % 10 == 0 or epoch == epochs:
        print(f"  Época [{epoch:02d}/{epochs}] — Train: {(train_corr/train_tot)*100:.1f}% | Val: {val_acc:.2f}% (FP={fp}, FN={fn})")

if best_weights:
    model.load_state_dict(best_weights)

# ==============================================================================
# 6. EXPORTACIÓN ONNX Y DESCARGA AUTOMÁTICA
# ==============================================================================
print("\n" + "=" * 70)
print("💾 [6/6] EXPORTANDO A ONNX Y DESCARGANDO...")
print("=" * 70)

model.eval().to("cpu")
dummy_input = torch.randn(1, 16, 96, dtype=torch.float32)

torch.onnx.export(
    model,
    dummy_input,
    "tess.onnx",
    input_names=["input"],
    output_names=["output"],
    dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
    opset_version=14,
    dynamo=False,
)

file_size = os.path.getsize("tess.onnx")
print(f"🎉 ¡Modelo 'tess.onnx' exportado exitosamente! ({file_size} bytes)")

# Descarga automática al navegador
files.download("tess.onnx")
print("📥 Descarga iniciada en tu navegador. Guarda el archivo en tu carpeta JARVIS/models/tess.onnx.")
