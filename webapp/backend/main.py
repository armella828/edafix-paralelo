import csv
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import Any

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
    description="Backend para analisis edafologico: clasificacion individual, por lotes (1-10) y benchmark del cluster",
    version="1.1.0",
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

CONTAINER_NAME = "edafix-master"
CLUSTER_NODES = ("master", "worker1", "worker2")
CLUSTER_SLOT_LOCK = threading.Lock()
DOCKER_TIMEOUT_SECONDS = 900
RESIZE_SIZE = (512, 512)
MAX_BATCH_IMAGES = 10
BATCH_THREAD_WORKERS = 4
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


DEFAULT_BENCHMARK_METRICS = {
    (500, 1): {"T1": 0.927044, "Tp": 0.408551, "Speedup": 2.2691, "Eficiencia": 0.7564},
    (500, 2): {"T1": 0.927044, "Tp": 0.286630, "Speedup": 3.2343, "Eficiencia": 0.5390},
    (500, 4): {"T1": 0.927044, "Tp": 0.274709, "Speedup": 3.3746, "Eficiencia": 0.2812},
    (1000, 1): {"T1": 1.865714, "Tp": 0.832435, "Speedup": 2.2413, "Eficiencia": 0.7471},
    (1000, 2): {"T1": 1.865714, "Tp": 0.565103, "Speedup": 3.3015, "Eficiencia": 0.5503},
    (1000, 4): {"T1": 1.865714, "Tp": 0.524547, "Speedup": 3.5568, "Eficiencia": 0.2964},
}


def get_fallback_cluster_metrics(num_images: int, omp_threads: int) -> dict | None:
    """Obtiene las metricas precalculadas desde data/resultados_benchmark.csv o el respaldo en memoria."""
    if BENCHMARK_CSV_PATH.exists():
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
    preset = DEFAULT_BENCHMARK_METRICS.get((num_images, omp_threads))
    if preset is not None:
        return {"num_images": num_images, "omp_threads": omp_threads, **preset}
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


def compute_node_distribution(num_images: int) -> dict[str, int]:
    """Replica el reparto de carga de `src/parallel/edafix_par.cpp` entre los 3 nodos MPI."""
    size = len(CLUSTER_NODES)
    chunk = num_images // size
    remainder = num_images % size
    return {
        node: chunk + (1 if rank < remainder else 0)
        for rank, node in enumerate(CLUSTER_NODES)
    }


def run_cluster_batch(raw_list: list[bytes], omp_threads: int = 4) -> float:
    """Guarda temporalmente un lote (1-10 imagenes) como .bin y ejecuta la clasificacion
    paralela hibrida (OpenMPI + OpenMP) contra los 3 nodos del contenedor edafix-master.

    El binario edafix_par lee `data/samples/soil_0000.bin` .. `soil_{N-1:04d}.bin`,
    por lo que se respaldan y restauran los slots originales sin alterar el dataset del benchmark.
    """
    if not raw_list:
        return 0.0

    num_images = len(raw_list)
    with CLUSTER_SLOT_LOCK:
        SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        USER_UPLOAD_PATH.write_bytes(raw_list[0])

        backups: list[tuple[Path, bytes | None]] = []
        try:
            for i, raw in enumerate(raw_list):
                slot_path = SAMPLES_DIR / f"soil_{i:04d}.bin"
                backups.append((slot_path, slot_path.read_bytes() if slot_path.exists() else None))
                slot_path.write_bytes(raw)

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
                    str(len(CLUSTER_NODES)),
                    "./edafix_par",
                    str(num_images),
                ]
            )
            return parse_seconds(output)
        finally:
            for slot_path, backup in backups:
                if backup is not None:
                    slot_path.write_bytes(backup)
                else:
                    slot_path.unlink(missing_ok=True)


def run_quick_classification(raw: bytes, omp_threads: int = 1) -> float:
    """Ejecuta la clasificacion rapida de una sola imagen en el cluster."""
    return run_cluster_batch([raw], omp_threads=omp_threads)


def _decode_and_analyze_one(index: int, filename: str, contents: bytes) -> dict[str, Any]:
    """Decodifica, redimensiona a 512x512 RGB y analiza una imagen (seguro para hilos)."""
    if not contents:
        return {
            "index": index,
            "filename": filename,
            "ok": False,
            "error": "El archivo de imagen esta vacio",
        }

    try:
        with Image.open(BytesIO(contents)) as img:
            image = img.convert("RGB")
            if image.size != RESIZE_SIZE:
                image = image.resize(RESIZE_SIZE)
            raw = image.tobytes()
    except Exception:
        return {
            "index": index,
            "filename": filename,
            "ok": False,
            "error": "Formato de imagen no soportado (.jpg, .png, .webp, .jfif, .bmp)",
        }

    analysis = classifier.analyze_image(raw)
    return {
        "index": index,
        "filename": filename,
        "ok": True,
        "raw": raw,
        "result": {
            "index": index,
            "filename": filename,
            "is_valid_soil": analysis.get("is_valid_soil", True),
            "soil_status": analysis.get("soil_status", "valid"),
            "soil_type": analysis["soil_type"],
            "recommended_crop": analysis["recommended_crop"],
            "avg_rgb": analysis["avg_rgb"],
            "roughness_index": analysis["roughness_index"],
            "moisture_index": analysis.get("moisture_index"),
            "moisture_level": analysis.get("moisture_level"),
            "moisture_advice": analysis.get("moisture_advice"),
            "lighting_warning": analysis.get("lighting_warning", False),
        },
    }


def _build_batch_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Consolida un diagnostico global de parcela a partir de los resultados individuales."""
    counts_by_soil = {soil: 0 for soil in classifier.SOIL_TYPES}
    valid_items: list[dict[str, Any]] = []
    monte_items: list[dict[str, Any]] = []
    invalid_items: list[dict[str, Any]] = []
    error_items: list[dict[str, Any]] = []

    for item in results:
        status = item.get("soil_status")
        if status == "valid":
            valid_items.append(item)
            soil_type = item.get("soil_type")
            if soil_type in counts_by_soil:
                counts_by_soil[soil_type] += 1
        elif status == "monte":
            monte_items.append(item)
        elif status == "error":
            error_items.append(item)
        else:
            invalid_items.append(item)

    total_images = len(results)
    profile_by_name = {p["soil_type"]: p for p in classifier.SOIL_PROFILES}

    avg_moisture_index: float | None = None
    dominant_moisture_level: str | None = None
    moisture_advice: str | None = None
    lighting_warning = any(bool(item.get("lighting_warning")) for item in valid_items)

    if valid_items:
        dominant_soil = max(classifier.SOIL_TYPES, key=lambda s: counts_by_soil[s])
        dominant_count = counts_by_soil[dominant_soil]
        dominant_percentage = round((dominant_count / len(valid_items)) * 100.0, 1)
        recommended_crop = profile_by_name[dominant_soil]["crop"]
        avg_roughness = round(
            sum(float(item["roughness_index"]) for item in valid_items if item["roughness_index"] is not None)
            / len(valid_items),
            4,
        )
        moisture_vals = [float(item["moisture_index"]) for item in valid_items if item.get("moisture_index") is not None]
        if moisture_vals:
            avg_moisture_index = round(sum(moisture_vals) / len(moisture_vals), 1)
            dominant_moisture_level, moisture_advice = classifier.classify_moisture_level(avg_moisture_index)
        dominant_status = "valid"
    elif monte_items:
        dominant_soil = "Terreno con Monte / Cobertura Vegetal"
        dominant_count = len(monte_items)
        dominant_percentage = round((dominant_count / max(1, total_images - len(error_items))) * 100.0, 1)
        recommended_crop = (
            "Requiere desmonte y limpieza previa del terreno para sembrar "
            "(o tomar muestras en tierra despejada)"
        )
        avg_roughness = round(
            sum(float(item["roughness_index"]) for item in monte_items if item["roughness_index"] is not None)
            / len(monte_items),
            4,
        )
        moisture_advice = "No determinable por cobertura vegetal (tomar muestras sobre tierra despejada)"
        dominant_status = "monte"
    else:
        dominant_soil = "Terreno No Apto / No es Suelo Agrícola"
        dominant_count = 0
        dominant_percentage = 0.0
        recommended_crop = "No se puede sembrar en este suelo (las imágenes no corresponden a tierra de cultivo)"
        avg_roughness = None
        dominant_status = "invalid"

    return {
        "total_images": total_images,
        "valid_soil_count": len(valid_items),
        "monte_count": len(monte_items),
        "invalid_count": len(invalid_items),
        "error_count": len(error_items),
        "counts_by_soil": counts_by_soil,
        "dominant_status": dominant_status,
        "dominant_soil_type": dominant_soil,
        "dominant_count": dominant_count,
        "dominant_percentage": dominant_percentage,
        "recommended_crop": recommended_crop,
        "avg_roughness_index": avg_roughness,
        "avg_moisture_index": avg_moisture_index,
        "dominant_moisture_level": dominant_moisture_level,
        "moisture_advice": moisture_advice,
        "lighting_warning": lighting_warning,
    }


@app.post("/api/analyze-single")
async def analyze_single(file: UploadFile = File(...)) -> dict:
    """Recibe una imagen, la redimensiona a 512x512 RGB crudo (.bin),
    la guarda en data/samples/user_upload.bin y clasifica el suelo."""
    start_time = time.perf_counter()

    contents = await file.read()
    decoded = _decode_and_analyze_one(0, file.filename or "imagen.jpg", contents)
    if not decoded["ok"]:
        raise HTTPException(status_code=400, detail=decoded["error"])

    raw = decoded["raw"]
    analysis = decoded["result"]

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
        "is_valid_soil": analysis["is_valid_soil"],
        "soil_status": analysis["soil_status"],
        "soil_type": analysis["soil_type"],
        "recommended_crop": analysis["recommended_crop"],
        "avg_rgb": analysis["avg_rgb"],
        "roughness_index": analysis["roughness_index"],
        "moisture_index": analysis["moisture_index"],
        "moisture_level": analysis["moisture_level"],
        "moisture_advice": analysis["moisture_advice"],
        "lighting_warning": analysis["lighting_warning"],
        "response_time_ms": round(elapsed_ms, 3),
    }


@app.post("/api/analyze-batch")
async def analyze_batch(files: list[UploadFile] = File(...)) -> dict:
    """Analiza en paralelo un lote de 1 a 10 imagenes de suelo.

    - En local con Docker activo: distribuye el lote en el cluster hibrido OpenMPI (3 nodos) + OpenMP.
    - En Vercel Serverless (sin Docker): procesa el lote en paralelo con ThreadPoolExecutor (seguro sin /dev/shm).
    """
    start_time = time.perf_counter()

    if not files:
        raise HTTPException(status_code=400, detail="Debes subir al menos 1 imagen para analizar.")
    if len(files) > MAX_BATCH_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Se permite un maximo de {MAX_BATCH_IMAGES} imagenes por analisis.",
        )

    payloads: list[tuple[int, str, bytes]] = []
    for idx, upload in enumerate(files):
        filename = upload.filename or f"muestra_{idx + 1}.jpg"
        data = await upload.read()
        payloads.append((idx, filename, data))

    workers = min(len(payloads), BATCH_THREAD_WORKERS)
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            processed = list(executor.map(lambda p: _decode_and_analyze_one(*p), payloads))
    else:
        processed = [_decode_and_analyze_one(*payloads[0])]

    processed.sort(key=lambda item: item["index"])

    valid_raws: list[bytes] = []
    results: list[dict[str, Any]] = []
    for item in processed:
        if item["ok"]:
            valid_raws.append(item["raw"])
            results.append(item["result"])
        else:
            results.append(
                {
                    "index": item["index"],
                    "filename": item["filename"],
                    "is_valid_soil": False,
                    "soil_status": "error",
                    "soil_type": "Imagen no válida / error de lectura",
                    "recommended_crop": item["error"],
                    "avg_rgb": None,
                    "roughness_index": None,
                    "moisture_index": None,
                    "moisture_level": None,
                    "moisture_advice": None,
                    "lighting_warning": False,
                }
            )

    if not valid_raws:
        raise HTTPException(
            status_code=400,
            detail="Ninguna de las imagenes subidas pudo procesarse. Usa formatos validos (.jpg, .png, .webp).",
        )

    cluster_time_ms: float | None = None
    node_distribution: dict[str, int] | None = None

    if is_docker_cluster_ready():
        omp_threads = min(4, max(1, len(valid_raws)))
        cluster_seconds = run_cluster_batch(valid_raws, omp_threads=omp_threads)
        cluster_time_ms = round(cluster_seconds * 1000.0, 3)
        node_distribution = compute_node_distribution(len(valid_raws))
        execution_mode = "cluster_mpi_openmp"
        cluster_nodes = len(CLUSTER_NODES)
        workers_used = cluster_nodes * omp_threads
    else:
        try:
            SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
            USER_UPLOAD_PATH.write_bytes(valid_raws[0])
        except OSError:
            pass
        omp_threads = workers
        execution_mode = "serverless_parallel"
        cluster_nodes = 1
        workers_used = workers

    summary = _build_batch_summary(results)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    return {
        "total_images": len(results),
        "execution_mode": execution_mode,
        "cluster_nodes": cluster_nodes,
        "omp_threads": omp_threads,
        "workers_used": workers_used,
        "node_distribution": node_distribution,
        "cluster_time_ms": cluster_time_ms,
        "response_time_ms": round(elapsed_ms, 3),
        "summary": summary,
        "results": results,
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

from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
import os

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))
index_html_file = Path(frontend_path) / "index.html"
app_js_file = Path(frontend_path) / "app.js"


@app.get("/", response_class=HTMLResponse)
@app.get("/api/index", response_class=HTMLResponse)
async def serve_index() -> HTMLResponse:
    if index_html_file.exists():
        return HTMLResponse(content=index_html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>EDAFix Server Running</h1>")


@app.get("/app.js")
async def serve_app_js() -> Response:
    if app_js_file.exists():
        return Response(
            content=app_js_file.read_text(encoding="utf-8"),
            media_type="application/javascript; charset=utf-8",
        )
    raise HTTPException(status_code=404, detail="app.js no encontrado")


if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
