"""Motor de clasificacion edafologica.

Replica en Python la logica de `src/parallel/edafix_par.cpp` y `src/sequential/edafix_seq.cpp`
para una imagen en formato RGB crudo de 512x512 bytes (WxH*3), incorporando:
1. Validacion estricta de terreno agricola (cromaticidad terrosa + micro-granularidad por bloques 16x16).
2. Aprendizaje por muestras de referencia en `data/dataset_suelos/{arenoso,arcilloso,limoso,no_apto}` si existen.
"""

import json
import math
from pathlib import Path
from PIL import Image

WIDTH = 512
HEIGHT = 512
TOTAL_PIXELS = WIDTH * HEIGHT

SOIL_TYPES = ["Arenoso", "Arcilloso", "Limoso"]

CROPS = {
    0: "Sorgo granífero / Sésamo",
    1: "Maíz / Soya",
    2: "Soya / Fréjol",
}

SOIL_PROFILES = [
    {"soil_type": "Arenoso", "crop": CROPS[0], "r": 210, "g": 180, "b": 140, "roughness": 35.0},
    {"soil_type": "Arcilloso", "crop": CROPS[1], "r": 130, "g": 75, "b": 55, "roughness": 12.0},
    {"soil_type": "Limoso", "crop": CROPS[2], "r": 110, "g": 105, "b": 95, "roughness": 20.0},
]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = PROJECT_ROOT / "data" / "dataset_suelos"
CACHE_FILE = DATASET_DIR / "perfiles_aprendidos.json"


def _extract_features(raw: bytes) -> dict:
    """Extrae caracteristicas cromaticas, de rugosidad Sobel y de micro-textura granular por parches."""
    sum_r = 0.0
    sum_g = 0.0
    sum_b = 0.0
    edge_energy = 0.0

    earth_pixels = 0
    achromatic_pixels = 0
    flat_pixels = 0
    grain_flips = 0
    interior_pixels = (WIDTH - 2) * (HEIGHT - 2)

    # Grilla de 16x16 parches (cada parche de 32x32 pixeles)
    grid_n = 16
    patch_size = WIDTH // grid_n
    patch_grad = [0.0] * (grid_n * grid_n)
    patch_earth = [0] * (grid_n * grid_n)
    patch_count = [0] * (grid_n * grid_n)

    for y in range(1, HEIGHT - 1):
        row = y * WIDTH * 3
        py = min(grid_n - 1, y // patch_size)
        for x in range(1, WIDTH - 1):
            idx = row + x * 3
            r = raw[idx]
            g = raw[idx + 1]
            b = raw[idx + 2]

            sum_r += r
            sum_g += g
            sum_b += b

            px = min(grid_n - 1, x // patch_size)
            p_idx = py * grid_n + px
            patch_count[p_idx] += 1

            # Detectar pixeles grises/acromaticos (pisos de ceramica, cemento, paredes, asfalto, muebles grises)
            if max(r, g, b) - min(r, g, b) < 12:
                achromatic_pixels += 1

            # Un pixel de tierra agricola real tiene calidez cromatica (oxidos de hierro / materia organica): R > G > B
            is_valid_brightness = (22 <= r <= 235) and (18 <= g <= 215) and (10 <= b <= 190)
            is_warm_earth = (
                (r >= g + 2)
                and (g >= b + 2)
                and ((r - b) >= 12)
                and ((r - g) <= 75)
            )
            if is_valid_brightness and is_warm_earth:
                earth_pixels += 1
                patch_earth[p_idx] += 1

            idx_l = row + (x - 1) * 3
            idx_r = row + (x + 1) * 3
            idx_u = ((y - 1) * WIDTH + x) * 3
            idx_d = ((y + 1) * WIDTH + x) * 3

            gx = float(raw[idx_r]) - float(raw[idx_l])
            gy = float(raw[idx_d]) - float(raw[idx_u])
            grad = math.sqrt(gx * gx + gy * gy)
            edge_energy += grad
            patch_grad[p_idx] += grad

            if grad < 3.0:
                flat_pixels += 1

            # Micro-granularidad: cambio de signo entre pixeles vecinos (granos/poros de tierra vs superficies lisas)
            diff_l = int(r) - int(raw[idx_l])
            diff_r = int(raw[idx_r]) - int(r)
            if diff_l * diff_r < -4:
                grain_flips += 1

    avg_r = sum_r / TOTAL_PIXELS
    avg_g = sum_g / TOTAL_PIXELS
    avg_b = sum_b / TOTAL_PIXELS
    norm_roughness = edge_energy / TOTAL_PIXELS

    earth_ratio = earth_pixels / interior_pixels
    achromatic_ratio = achromatic_pixels / interior_pixels
    flat_ratio = flat_pixels / interior_pixels
    grain_ratio = grain_flips / interior_pixels

    # Evaluar cuantos parches 32x32 tienen textura granular y color de tierra simultaneamente
    valid_soil_patches = 0
    smooth_patches = 0
    total_patches = grid_n * grid_n
    for i in range(total_patches):
        cnt = max(1, patch_count[i])
        p_rough = patch_grad[i] / cnt
        p_earth = patch_earth[i] / cnt
        if p_rough < 10.0:
            smooth_patches += 1
        if p_rough >= 11.0 and p_earth >= 0.55:
            valid_soil_patches += 1

    soil_patch_ratio = valid_soil_patches / total_patches
    smooth_patch_ratio = smooth_patches / total_patches

    return {
        "avg_r": avg_r,
        "avg_g": avg_g,
        "avg_b": avg_b,
        "norm_roughness": norm_roughness,
        "earth_ratio": earth_ratio,
        "achromatic_ratio": achromatic_ratio,
        "flat_ratio": flat_ratio,
        "grain_ratio": grain_ratio,
        "soil_patch_ratio": soil_patch_ratio,
        "smooth_patch_ratio": smooth_patch_ratio,
    }


def load_custom_dataset_profiles() -> list[dict]:
    """Carga perfiles aprendidos desde imagenes reales en data/dataset_suelos/ si el usuario agrego fotos."""
    folder_map = {
        "arenoso": ("Arenoso", CROPS[0], 0),
        "arcilloso": ("Arcilloso", CROPS[1], 1),
        "limoso": ("Limoso", CROPS[2], 2),
        "no_apto": ("No Apto", "No apto", -1),
    }
    if not DATASET_DIR.exists():
        return []

    files_sig = []
    for folder_name in folder_map:
        sub = DATASET_DIR / folder_name
        if sub.exists():
            for p in sorted(sub.glob("*.*")):
                if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".jfif", ".bmp"}:
                    files_sig.append(f"{folder_name}/{p.name}:{p.stat().st_mtime_ns}")

    if not files_sig:
        return []

    sig_str = "|".join(files_sig)
    if CACHE_FILE.exists():
        try:
            cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if cached.get("signature") == sig_str:
                return cached.get("samples", [])
        except Exception:
            pass

    samples = []
    for folder_name, (soil_type, crop, idx) in folder_map.items():
        sub = DATASET_DIR / folder_name
        if not sub.exists():
            continue
        for p in sorted(sub.glob("*.*")):
            if p.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".jfif", ".bmp"}:
                continue
            try:
                img = Image.open(p).convert("RGB").resize((WIDTH, HEIGHT))
                feat = _extract_features(img.tobytes())
                samples.append(
                    {
                        "label": folder_name,
                        "soil_index": idx,
                        "soil_type": soil_type,
                        "crop": crop,
                        "r": feat["avg_r"],
                        "g": feat["avg_g"],
                        "b": feat["avg_b"],
                        "roughness": feat["norm_roughness"],
                    }
                )
            except Exception:
                continue

    try:
        CACHE_FILE.write_text(
            json.dumps({"signature": sig_str, "samples": samples}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass
    return samples


def analyze_image(raw: bytes) -> dict:
    """Analiza una imagen RGB cruda (512x512x3) y devuelve el resultado completo,
    rechazando imagenes que no correspondan a terreno agricola real."""
    feat = _extract_features(raw)
    avg_r = feat["avg_r"]
    avg_g = feat["avg_g"]
    avg_b = feat["avg_b"]
    norm_roughness = feat["norm_roughness"]

    # 1. Consultar primero muestras reales del dataset en data/dataset_suelos/ si existen
    custom_samples = load_custom_dataset_profiles()
    if custom_samples:
        best_sample = min(
            custom_samples,
            key=lambda s: math.sqrt(
                (avg_r - s["r"]) ** 2
                + (avg_g - s["g"]) ** 2
                + (avg_b - s["b"]) ** 2
                + ((norm_roughness - s["roughness"]) * 1.5) ** 2
            ),
        )
        dist_best = math.sqrt(
            (avg_r - best_sample["r"]) ** 2
            + (avg_g - best_sample["g"]) ** 2
            + (avg_b - best_sample["b"]) ** 2
            + ((norm_roughness - best_sample["roughness"]) * 1.5) ** 2
        )
        if best_sample["soil_index"] == -1 and dist_best < 35.0:
            return _invalid_soil_response(avg_r, avg_g, avg_b, norm_roughness)
        if best_sample["soil_index"] != -1 and dist_best < 25.0 and feat["earth_ratio"] >= 0.45:
            return {
                "is_valid_soil": True,
                "soil_index": best_sample["soil_index"],
                "soil_type": best_sample["soil_type"],
                "recommended_crop": best_sample["crop"],
                "avg_rgb": {
                    "r": round(float(avg_r), 2),
                    "g": round(float(avg_g), 2),
                    "b": round(float(avg_b), 2),
                },
                "roughness_index": round(float(norm_roughness), 4),
            }

    # 2. Validacion estricta de terreno agricola (color terroso + textura granular en toda la imagen)
    rgb_distances = [
        math.sqrt((avg_r - p["r"]) ** 2 + (avg_g - p["g"]) ** 2 + (avg_b - p["b"]) ** 2)
        for p in SOIL_PROFILES
    ]
    min_rgb_dist = min(rgb_distances)
    color_warmth = avg_r - avg_b  # El suelo real nunca es gris neutro (cemento/piso/pared tiene R-B < 10)

    is_valid_soil = (
        feat["earth_ratio"] >= 0.60
        and feat["achromatic_ratio"] <= 0.25
        and color_warmth >= 13.0
        and (avg_r >= avg_g + 2.0)
        and (avg_g >= avg_b + 2.0)
        and norm_roughness >= 13.5
        and feat["soil_patch_ratio"] >= 0.60
        and feat["smooth_patch_ratio"] <= 0.30
        and feat["grain_ratio"] >= 0.04
        and min_rgb_dist <= 65.0
    )

    if not is_valid_soil:
        return _invalid_soil_response(avg_r, avg_g, avg_b, norm_roughness)

    d_arenoso = math.sqrt(
        (avg_r - 210) ** 2 + (avg_g - 180) ** 2 + (avg_b - 140) ** 2 + (norm_roughness - 35) ** 2
    )
    d_arcilloso = math.sqrt(
        (avg_r - 130) ** 2 + (avg_g - 75) ** 2 + (avg_b - 55) ** 2 + (norm_roughness - 12) ** 2
    )
    d_limoso = math.sqrt(
        (avg_r - 110) ** 2 + (avg_g - 105) ** 2 + (avg_b - 95) ** 2 + (norm_roughness - 20) ** 2
    )

    if d_arenoso <= d_arcilloso and d_arenoso <= d_limoso:
        soil_index = 0
    elif d_arcilloso <= d_arenoso and d_arcilloso <= d_limoso:
        soil_index = 1
    else:
        soil_index = 2

    profile = SOIL_PROFILES[soil_index]
    return {
        "is_valid_soil": True,
        "soil_index": soil_index,
        "soil_type": profile["soil_type"],
        "recommended_crop": profile["crop"],
        "avg_rgb": {
            "r": round(float(avg_r), 2),
            "g": round(float(avg_g), 2),
            "b": round(float(avg_b), 2),
        },
        "roughness_index": round(float(norm_roughness), 4),
    }


def _invalid_soil_response(avg_r: float, avg_g: float, avg_b: float, norm_roughness: float) -> dict:
    return {
        "is_valid_soil": False,
        "soil_index": -1,
        "soil_type": "Terreno No Apto / No es Suelo Agrícola",
        "recommended_crop": "No se puede sembrar en este suelo (la imagen no corresponde a tierra de cultivo)",
        "avg_rgb": {
            "r": round(float(avg_r), 2),
            "g": round(float(avg_g), 2),
            "b": round(float(avg_b), 2),
        },
        "roughness_index": round(float(norm_roughness), 4),
    }


def classify_image(raw: bytes) -> int:
    """Retorna el indice del tipo de suelo: 0=Arenoso, 1=Arcilloso, 2=Limoso, -1=No apto."""
    return analyze_image(raw)["soil_index"]
