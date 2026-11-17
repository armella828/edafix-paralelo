import csv
import importlib
import re
import shutil
import subprocess
import sys
import time
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import classifier

app = FastAPI(
    title="EDAFix API",
    description="Backend para analisis edafologico: clasificacion individual y benchmark del cluster",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = PROJECT_ROOT / "data" / "samples"
BENCHMARK_CSV_PATH = PROJECT_ROOT / "data" / "resultados_benchmark.csv"
USER_UPLOAD_PATH = SAMPLES_DIR / "user_upload.bin"
CLUSTER_SLOT_PATH = SAMPLES_DIR / "soil_0000.bin"

CONTAINER_NAME = "edafix-master"
DOCKER_TIMEOUT_SECONDS = 900
RESIZE_SIZE = (512, 512)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


class ClusterParams(BaseModel):
    num_images: int = Field(..., ge=1, le=10000, description="Numero de imagenes a clasificar (ej. 500 o 1000)")
    omp_threads: int = Field(..., ge=1, le=8, description="Hilos OpenMP (1, 2 u 4)")


def is_docker_cluster_ready() -> bool:
    """Verifica si Docker esta instalado y el contenedor edafix-master esta corriendo."""
    if shutil.which("docker") is None:
        return False
    try:
        proc = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Status}}", CONTAINER_NAME],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return proc.returncode == 0 and proc.stdout.strip() == "running"
    except Exception:
        return False


def get_fallback_cluster_metrics(num_images: int, omp_threads: int) -> dict | None:
    """Obtiene las metricas precalculadas desde data/resultados_benchmark.csv cuando Docker no esta activo."""
    if not BENCHMARK_CSV_PATH.exists():
        return None
    with BENCHMARK_CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (
                int(row["N_Imagenes"]) == num_images
                and int(row["Nodos_MPI"]) == 3
                and int(row["Hilos_OMP"]) == omp_threads
            ):
                t1 = float(row["Tiempo_Secuencial_s"])
                tp = float(row["Tiempo_Paralelo_s"])
                speedup = float(row["Speedup"])
                efficiency = float(row["Eficiencia"])
                return {
                    "num_images": num_images,
                    "omp_threads": omp_threads,
                    "T1": round(t1, 6),
                    "Tp": round(tp, 6),
                    "Speedup": round(speedup, 4),
                    "Eficiencia": round(efficiency, 4),
                }
    return None


def run_docker_exec(args: list, timeout: int = DOCKER_TIMEOUT_SECONDS) -> str:
    """Ejecuta un comando de terminal contra el contenedor edafix-master."""
    try:
        proc = subprocess.run(
            ["docker", "exec", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Docker no esta instalado o disponible en el PATH del sistema")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Timeout: el contenedor edafix-master no respondio a tiempo")

    if proc.returncode != 0:
        raise HTTPException(
            status_code=502,
            detail=f"Error ejecutando el contenedor edafix-master: {proc.stderr.strip()}",
        )
    return proc.stdout


def parse_seconds(output: str) -> float:
    """Extrae el tiempo en segundos (float) de la salida del binario."""
    match = re.search(r"\d+(?:\.\d+)?", output or "")
    if not match:
        raise RuntimeError(f"No se pudo leer el tiempo de la salida del contenedor: {output!r}")
    return float(match.group())


def run_quick_classification(raw: bytes, omp_threads: int = 1) -> float:
    """Guarda temporalmente la imagen subida como .bin y ejecuta la clasificacion
    rapida (una sola imagen) contra el contenedor edafix-master.

    El binario edafix_par lee los samples desde `data/samples/soil_NNNN.bin`,
    por lo que la imagen subida se coloca temporalmente en el slot 0 y se
    restaura el archivo original una vez terminada la ejecucion.
    """
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    USER_UPLOAD_PATH.write_bytes(raw)

    backup = CLUSTER_SLOT_PATH.read_bytes() if CLUSTER_SLOT_PATH.exists() else None
    try:
        CLUSTER_SLOT_PATH.write_bytes(raw)
        output = run_docker_exec(
            [
                "-e",
                f"OMP_NUM_THREADS={omp_threads}",
                CONTAINER_NAME,
                "mpirun",
                "--allow-run-as-root",
                "--hostfile",
                "infrastructure/hostfile",
                "--map-by",
                "node",
                "-np",
                "3",
                "./edafix_par",
                "1",
            ]
        )
        return parse_seconds(output)
    finally:
        if backup is not None:
            CLUSTER_SLOT_PATH.write_bytes(backup)
        else:
            CLUSTER_SLOT_PATH.unlink(missing_ok=True)


@app.post("/api/analyze-single")
async def analyze_single(file: UploadFile = File(...)) -> dict:
    """Recibe una imagen, la redimensiona a 512x512 RGB crudo (.bin),
    la guarda en data/samples/user_upload.bin y clasifica el suelo."""
    start_time = time.perf_counter()

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="El archivo de imagen esta vacio")

    try:
        image = Image.open(BytesIO(contents)).convert("RGB").resize(RESIZE_SIZE)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Formato de imagen no soportado. Use una imagen valida (.jpg, .png, .webp, .jfif, .bmp)",
        )
    raw = image.tobytes()  # 512 x 512 x 3 bytes, formato RGB crudo

    importlib.reload(classifier)
    analysis = classifier.analyze_image(raw)

    # Ejecutar la clasificacion contra el contenedor edafix-master si el cluster Docker esta activo
    if is_docker_cluster_ready():
        run_quick_classification(raw, omp_threads=1)
    else:
        try:
            SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
            USER_UPLOAD_PATH.write_bytes(raw)
        except OSError:
            pass

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return {
        "is_valid_soil": analysis.get("is_valid_soil", True),
        "soil_status": analysis.get("soil_status", "valid"),
        "soil_type": analysis["soil_type"],
        "recommended_crop": analysis["recommended_crop"],
        "avg_rgb": analysis["avg_rgb"],
        "roughness_index": analysis["roughness_index"],
        "response_time_ms": round(elapsed_ms, 3),
    }


@app.post("/api/run-cluster")
async def run_cluster(params: ClusterParams) -> dict:
    """Ejecuta la clasificacion secuencial (T1) y paralela (Tp) contra el cluster."""
    if not is_docker_cluster_ready():
        fallback = get_fallback_cluster_metrics(params.num_images, params.omp_threads)
        if fallback is not None:
            return fallback

    # T1: ejecucion secuencial
    t1 = parse_seconds(run_docker_exec(["edafix-master", "./edafix_seq", str(params.num_images)]))

    # Tp: ejecucion paralela (OpenMP) sobre el cluster MPI
    tp = parse_seconds(
        run_docker_exec(
            [
                "-e",
                f"OMP_NUM_THREADS={params.omp_threads}",
                "edafix-master",
                "mpirun",
                "--allow-run-as-root",
                "--hostfile",
                "infrastructure/hostfile",
                "--map-by",
                "node",
                "-np",
                "3",
                "./edafix_par",
                str(params.num_images),
            ]
        )
    )

    speedup = t1 / tp
    efficiency = speedup / (3 * params.omp_threads)

    return {
        "num_images": params.num_images,
        "omp_threads": params.omp_threads,
        "T1": round(t1, 6),
        "Tp": round(tp, 6),
        "Speedup": round(speedup, 4),
        "Eficiencia": round(efficiency, 4),
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


class TrainSampleParams(BaseModel):
    label: str = Field(..., description="Categoria: arenoso, arcilloso, limoso o no_apto")


@app.post("/api/train-sample")
async def train_sample(params: TrainSampleParams) -> dict:
    """Guarda la ultima imagen analizada en data/dataset_suelos/<label>/ para mejorar la precision del clasificador."""
    valid_labels = {"arenoso", "arcilloso", "limoso", "no_apto"}
    label = params.label.strip().lower()
    if label not in valid_labels:
        raise HTTPException(status_code=400, detail="Etiqueta invalida")
    if not USER_UPLOAD_PATH.exists():
        raise HTTPException(status_code=400, detail="Primero analiza una imagen antes de guardarla en el dataset")

    raw = USER_UPLOAD_PATH.read_bytes()
    img = Image.frombytes("RGB", RESIZE_SIZE, raw)
    target_dir = PROJECT_ROOT / "data" / "dataset_suelos" / label
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / f"sample_{int(time.time() * 1000)}.png"
    img.save(out_file, format="PNG")
    return {"status": "saved", "label": label, "file": out_file.name}

from fastapi.staticfiles import StaticFiles
import os

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
