"""Motor de clasificacion edafologica.

Replica en Python la logica de `src/parallel/edafix_par.cpp` y `src/sequential/edafix_seq.cpp`
para una imagen en formato RGB crudo de 512x512 bytes (WxH*3), incorporando:
1. Deteccion de suelo agricola limpio (Arenoso, Arcilloso, Limoso).
2. Deteccion de terreno con monte / cobertura vegetal densa (maleza, arbustos, pastizal).
3. Rechazo de construcciones, casas, habitaciones y objetos (deteccion de lineas rectas H/V,
   pintura roja/ladrillo artificial, cielo/ventanas y superficies lisas).
"""

import math
from pathlib import Path

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


def _extract_features(raw: bytes) -> dict:
    """Extrae caracteristicas cromaticas, geometricas (lineas H/V de construcciones) y de textura por parches."""
    sum_r = 0.0
    sum_g = 0.0
    sum_b = 0.0
    edge_energy = 0.0

    earth_pixels = 0
    veg_pixels = 0
    achromatic_pixels = 0
    sky_or_artificial_pixels = 0
    red_paint_pixels = 0
    flat_pixels = 0
    grain_flips = 0
    hv_edges = 0
    diag_edges = 0
    interior_pixels = (WIDTH - 2) * (HEIGHT - 2)

    earth_r_sum = 0.0
    earth_g_sum = 0.0
    earth_b_sum = 0.0

    top_g_sum = 0.0
    top_b_sum = 0.0
    top_count = 0
    third_h = HEIGHT // 3

    # Grilla de 16x16 parches (cada parche de 32x32 pixeles)
    grid_n = 16
    patch_size = WIDTH // grid_n
    patch_grad = [0.0] * (grid_n * grid_n)
    patch_earth = [0] * (grid_n * grid_n)
    patch_veg = [0] * (grid_n * grid_n)
    patch_count = [0] * (grid_n * grid_n)

    for y in range(1, HEIGHT - 1):
        row = y * WIDTH * 3
        py = min(grid_n - 1, y // patch_size)
        is_top_third = y < third_h
        for x in range(1, WIDTH - 1):
            idx = row + x * 3
            r = raw[idx]
            g = raw[idx + 1]
            b = raw[idx + 2]

            sum_r += r
            sum_g += g
            sum_b += b

            if is_top_third:
                top_g_sum += g
                top_b_sum += b
                top_count += 1

            px = min(grid_n - 1, x // patch_size)
            p_idx = py * grid_n + px
            patch_count[p_idx] += 1

            # 1. Pixeles grises/acromaticos (pisos, cemento, paredes, asfalto)
            if max(r, g, b) - min(r, g, b) < 10:
                achromatic_pixels += 1

            # 2. Cielo, blanco brillante, azul o tonos magenta/violeta (ajenos a una muestra de suelo)
            if (b > r + 4) or (b > g + 2) or (r > 220 and g > 220 and b > 220):
                sky_or_artificial_pixels += 1

            # 3. Pintura roja / pared roja / ladrillo artificial (R muy alto pero G cercano a B, sin ocre amarillo)
            if (r > 85) and (r - g > 22) and ((g - b) < (r - g) * 0.25):
                red_paint_pixels += 1

            is_valid_brightness = (18 <= r <= 242) and (14 <= g <= 228) and (6 <= b <= 195)

            # 4. Pixel de tierra agricola real: R >= G > B con componente ocre natural (G-B >= 26% de R-G)
            is_warm_earth = (
                is_valid_brightness
                and (r >= g + 2)
                and (g >= b + 5)
                and ((r - b) >= 12)
                and ((r - g) <= 85)
                and ((g - b) >= (r - g) * 0.26)
            )
            # 5. Pixel de monte / vegetacion / follaje (G > R >= B)
            is_vegetation = (
                is_valid_brightness
                and (g > r)
                and (g >= b + 10)
                and (r >= b - 6)
                and ((g - r) <= 85)
            )

            if is_warm_earth:
                earth_pixels += 1
                patch_earth[p_idx] += 1
                earth_r_sum += r
                earth_g_sum += g
                earth_b_sum += b
            elif is_vegetation:
                veg_pixels += 1
                patch_veg[p_idx] += 1

            idx_l = row + (x - 1) * 3
            idx_r = row + (x + 1) * 3
            idx_u = ((y - 1) * WIDTH + x) * 3
            idx_d = ((y + 1) * WIDTH + x) * 3

            gx = float(raw[idx_r]) - float(raw[idx_l])
            gy = float(raw[idx_d]) - float(raw[idx_u])
            abs_gx = abs(gx)
            abs_gy = abs(gy)
            grad = math.sqrt(gx * gx + gy * gy)
            edge_energy += grad
            patch_grad[p_idx] += grad

            if grad < 3.0:
                flat_pixels += 1

            # Detectar orientacion de bordes: las casas/objetos tienen bordes rectos horizontales/verticales
            if abs_gx + abs_gy > 25.0:
                if abs_gx > abs_gy * 3.0 or abs_gy > abs_gx * 3.0:
                    hv_edges += 1
                elif abs(abs_gx - abs_gy) < (abs_gx + abs_gy) * 0.25:
                    diag_edges += 1

            diff_l = int(r) - int(raw[idx_l])
            diff_r = int(raw[idx_r]) - int(r)
            if diff_l * diff_r < -4:
                grain_flips += 1

    avg_r = sum_r / TOTAL_PIXELS
    avg_g = sum_g / TOTAL_PIXELS
    avg_b = sum_b / TOTAL_PIXELS
    norm_roughness = edge_energy / TOTAL_PIXELS

    earth_ratio = earth_pixels / interior_pixels
    veg_ratio = veg_pixels / interior_pixels
    achromatic_ratio = achromatic_pixels / interior_pixels
    sky_or_artificial_ratio = sky_or_artificial_pixels / interior_pixels
    red_paint_ratio = red_paint_pixels / interior_pixels
    flat_ratio = flat_pixels / interior_pixels
    grain_ratio = grain_flips / interior_pixels
    hv_diag_ratio = hv_edges / max(1, diag_edges)
    top_g_minus_b = (top_g_sum - top_b_sum) / max(1, top_count)

    valid_soil_patches = 0
    valid_nature_patches = 0
    smooth_patches = 0
    total_patches = grid_n * grid_n
    for i in range(total_patches):
        cnt = max(1, patch_count[i])
        p_rough = patch_grad[i] / cnt
        p_earth = patch_earth[i] / cnt
        p_nature = (patch_earth[i] + patch_veg[i]) / cnt
        if p_rough < 9.5:
            smooth_patches += 1
        if p_rough >= 10.0 and p_earth >= 0.55:
            valid_soil_patches += 1
        if p_rough >= 9.5 and p_nature >= 0.50:
            valid_nature_patches += 1

    soil_patch_ratio = valid_soil_patches / total_patches
    nature_patch_ratio = valid_nature_patches / total_patches
    smooth_patch_ratio = smooth_patches / total_patches

    return {
        "avg_r": avg_r,
        "avg_g": avg_g,
        "avg_b": avg_b,
        "earth_avg_r": (earth_r_sum / earth_pixels) if earth_pixels > 0 else avg_r,
        "earth_avg_g": (earth_g_sum / earth_pixels) if earth_pixels > 0 else avg_g,
        "earth_avg_b": (earth_b_sum / earth_pixels) if earth_pixels > 0 else avg_b,
        "norm_roughness": norm_roughness,
        "earth_ratio": earth_ratio,
        "veg_ratio": veg_ratio,
        "achromatic_ratio": achromatic_ratio,
        "sky_or_artificial_ratio": sky_or_artificial_ratio,
        "red_paint_ratio": red_paint_ratio,
        "flat_ratio": flat_ratio,
        "grain_ratio": grain_ratio,
        "hv_diag_ratio": hv_diag_ratio,
        "top_g_minus_b": top_g_minus_b,
        "soil_patch_ratio": soil_patch_ratio,
        "nature_patch_ratio": nature_patch_ratio,
        "smooth_patch_ratio": smooth_patch_ratio,
    }


def analyze_image(raw: bytes) -> dict:
    """Analiza una imagen RGB cruda (512x512x3) y devuelve el resultado completo:
    - 'valid': suelo agricola limpio (Arenoso, Arcilloso o Limoso)
    - 'monte': terreno cubierto de monte / maleza / vegetacion densa
    - 'invalid': imagen que no corresponde a terreno (casa, habitacion, piso, objeto, etc.)
    """
    feat = _extract_features(raw)
    avg_r = feat["avg_r"]
    avg_g = feat["avg_g"]
    avg_b = feat["avg_b"]
    norm_roughness = feat["norm_roughness"]

    # Descartar inmediatamente construcciones/escenas con cielo, pintura roja, lineas rectas H/V o fondos lisos
    has_building_or_sky = (
        feat["sky_or_artificial_ratio"] > 0.08
        or feat["red_paint_ratio"] > 0.12
        or feat["hv_diag_ratio"] > 3.5
        or feat["top_g_minus_b"] < 4.0
    )

    # Caso 1: Detectar Terreno con Monte / Abundante Vegetacion (maleza, arbustos, pastizal denso)
    is_monte_terrain = (
        not has_building_or_sky
        and feat["veg_ratio"] >= 0.25
        and (feat["veg_ratio"] + feat["earth_ratio"]) >= 0.48
        and feat["achromatic_ratio"] <= 0.30
        and norm_roughness >= 9.0
        and feat["nature_patch_ratio"] >= 0.45
        and feat["smooth_patch_ratio"] <= 0.35
        and feat["earth_ratio"] < 0.55
    )

    if is_monte_terrain:
        return {
            "is_valid_soil": False,
            "soil_status": "monte",
            "soil_index": -2,
            "soil_type": "Terreno con Monte / Cobertura Vegetal",
            "recommended_crop": "Requiere desmonte y limpieza previa del terreno para sembrar (o tomar muestra en tierra despejada)",
            "avg_rgb": {
                "r": round(float(avg_r), 2),
                "g": round(float(avg_g), 2),
                "b": round(float(avg_b), 2),
            },
            "roughness_index": round(float(norm_roughness), 4),
        }

    # Caso 2: Validar Suelo Agricola Despejado
    eval_r = feat["earth_avg_r"] if feat["veg_ratio"] >= 0.10 else avg_r
    eval_g = feat["earth_avg_g"] if feat["veg_ratio"] >= 0.10 else avg_g
    eval_b = feat["earth_avg_b"] if feat["veg_ratio"] >= 0.10 else avg_b

    rgb_distances = [
        math.sqrt((eval_r - p["r"]) ** 2 + (eval_g - p["g"]) ** 2 + (eval_b - p["b"]) ** 2)
        for p in SOIL_PROFILES
    ]
    min_rgb_dist = min(rgb_distances)
    color_warmth = eval_r - eval_b

    is_valid_soil = (
        not has_building_or_sky
        and feat["earth_ratio"] >= 0.65
        and feat["achromatic_ratio"] <= 0.25
        and color_warmth >= 14.0
        and (eval_r >= eval_g + 3.0)
        and (eval_g >= eval_b + 5.0)
        and norm_roughness >= 10.0
        and feat["soil_patch_ratio"] >= 0.60
        and feat["smooth_patch_ratio"] <= 0.22
        and feat["grain_ratio"] >= 0.04
        and min_rgb_dist <= 110.0
    )

    if not is_valid_soil:
        return _invalid_soil_response(avg_r, avg_g, avg_b, norm_roughness)

    d_arenoso = math.sqrt(
        (eval_r - 210) ** 2 + (eval_g - 180) ** 2 + (eval_b - 140) ** 2 + (norm_roughness - 35) ** 2
    )
    d_arcilloso = math.sqrt(
        (eval_r - 130) ** 2 + (eval_g - 75) ** 2 + (eval_b - 55) ** 2 + (norm_roughness - 12) ** 2
    )
    d_limoso = math.sqrt(
        (eval_r - 110) ** 2 + (eval_g - 105) ** 2 + (eval_b - 95) ** 2 + (norm_roughness - 20) ** 2
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
        "soil_status": "valid",
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
        "soil_status": "invalid",
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
    """Retorna el indice del tipo de suelo: 0=Arenoso, 1=Arcilloso, 2=Limoso, -1=No apto, -2=Monte."""
    return analyze_image(raw)["soil_index"]
