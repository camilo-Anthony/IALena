import urllib.request
import json

# Descargar el notebook oficial de openWakeWord
url = 'https://raw.githubusercontent.com/dscripka/openWakeWord/main/notebooks/automatic_model_training.ipynb'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
content = urllib.request.urlopen(req).read().decode('utf-8')
nb = json.loads(content)

# Modificar celda 14 con la configuración de Tess
nb['cells'][14]['source'] = [
    "# Modify values in the config for Tess\n",
    "\n",
    "config[\"target_phrase\"] = [\"tess\"]\n",
    "config[\"model_name\"] = \"tess\"\n",
    "config[\"n_samples\"] = 2000\n",
    "config[\"n_samples_val\"] = 1000\n",
    "config[\"steps\"] = 10000\n",
    "config[\"target_accuracy\"] = 0.7\n",
    "config[\"target_recall\"] = 0.35\n",
    "\n",
    "config[\"background_paths\"] = [\"./audioset_16k\", \"./fma\"]\n",
    "config[\"false_positive_validation_data_path\"] = \"validation_set_features.npy\"\n",
    "config[\"feature_data_files\"] = {\"ACAV100M_sample\": \"openwakeword_features_ACAV100M_2000_hrs_16bit.npy\"}\n",
    "\n",
    "with open(\"my_model.yaml\", \"w\") as file:\n",
    "    documents = yaml.dump(config, file)\n"
]

# Modificar celda 20 (Step 4 de TFLite) para que no falle con onnx_tf
nb['cells'][20]['source'] = [
    "# Step 4: Descargar el modelo ONNX entrenado (tess.onnx)\n",
    "from google.colab import files\n",
    "import os\n",
    "\n",
    "onnx_file = f\"my_custom_model/{config['model_name']}.onnx\"\n",
    "if os.path.exists(onnx_file):\n",
    "    print(f\"🎉 ¡Modelo ONNX entrenado con éxito! ({os.path.getsize(onnx_file)} bytes)\")\n",
    "    print(f\"Descargando {onnx_file}...\")\n",
    "    files.download(onnx_file)\n",
    "else:\n",
    "    print(f\"⚠️ Buscando archivos generados:\")\n",
    "    !ls -la my_custom_model/\n"
]

output_path = 'Entrenar_Tess_Colab.ipynb'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("SUCCESS: Entrenar_Tess_Colab.ipynb actualizado sin el paso obsoleto de TFLite.")
