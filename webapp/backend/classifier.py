"""Motor de clasificacion edafologica.

Replica en Python la logica de `src/parallel/edafix_par.cpp` y `src/sequential/edafix_seq.cpp`
para una imagen en formato RGB crudo de 512x512 bytes (WxH*3), incorporando:
1. Analisis enfocado en la zona de suelo (70% inferior) para aceptar tanto tomas de cerca (macro)
   como fotos de terrenos/parcelas donde aparece cielo u horizonte arriba.
2. Deteccion de terreno con monte / cobertura vegetal densa (maleza, arbustos, pastizal).
3. Rechazo preciso de interiores, habitaciones, casas pintadas, cemento y objetos artificiales.
"""

import math

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
    """Extrae caracteristicas cromaticas, geometricas y de textura tanto globales como en la franja de suelo (70% inferior)."""
    sum_r = 0.0
    sum_g = 0.0
    sum_b = 0.0
    edge_energy = 0.0

    # Contadores en la zona de suelo (70% inferior de la imagen, ignorando posible cielo en el 30% superior)
    ground_y_start = int(HEIGHT * 0.30)
    ground_pixels = 0
    ground_earth_pixels = 0
    ground_veg_pixels = 0
    ground_achromatic_pixels = 0
    ground_blue_or_magenta_pixels = 0
    ground_r_sum = 0.0
    ground_g_sum = 0.0
    ground_b_sum = 0.0

    earth_r_sum = 0.0
    earth_g_sum = 0.0
    earth_b_sum = 0.0
    earth_total_pixels = 0

    red_paint_pixels = 0
    hv_edges = 0
    diag_edges = 0
    interior_pixels = (WIDTH - 2) * (HEIGHT - 2)

    for y in range(1, HEIGHT - 1):
        row = y * WIDTH * 3
        in_ground_zone = y >= ground_y_start
        for x in range(1, WIDTH - 1):
            idx = row + x * 3
            r = raw[idx]
            g = raw[idx + 1]
            b = raw[idx + 2]

            sum_r += r
            sum_g += g
            sum_b += b

            # Detectar pintura roja/carmesi artificial (paredes/casas/objetos rojos donde G esta muy cerca de B)
            if (r > 85) and (r - g > 25) and ((g - b) < (r - g) * 0.20):
                red_paint_pixels += 1

            is_valid_brightness = (14 <= r <= 248) and (10 <= g <= 240) and (4 <= b <= 222)

            # Pixel de tierra natural (incluye arena clara, tierra ocre, arcilla rojiza, limo pardo y tierra negra humeda)
            is_warm_earth = (
                is_valid_brightness
                and (r >= g - 2)
                and (g >= b + 2)
                and ((r - b) >= 6)
                and ((r - g) <= 95)
                and not ((r - g > 25) and ((g - b) < (r - g) * 0.20))
            )

            # Pixel de monte / vegetacion / pastizal
            is_vegetation = (
                is_valid_brightness
                and not is_warm_earth
                and (g >= r - 2)
                and (g >= b + 7)
                and (r >= b - 10)
            )

            if is_warm_earth:
                earth_total_pixels += 1
                earth_r_sum += r
                earth_g_sum += g
                earth_b_sum += b

            if in_ground_zone:
                ground_pixels += 1
                ground_r_sum += r
                ground_g_sum += g
                ground_b_sum += b
                if max(r, g, b) - min(r, g, b) < 9:
                    ground_achromatic_pixels += 1
                if (b > r + 8) or (b > g + 6):
                    ground_blue_or_magenta_pixels += 1
                if is_warm_earth:
                    ground_earth_pixels += 1
                elif is_vegetation:
                    ground_veg_pixels += 1

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

            if abs_gx + abs_gy > 25.0:
                if abs_gx > abs_gy * 3.0 or abs_gy > abs_gx * 3.0:
                    hv_edges += 1
                elif abs(abs_gx - abs_gy) < (abs_gx + abs_gy) * 0.25:
                    diag_edges += 1

    avg_r = sum_r / TOTAL_PIXELS
    avg_g = sum_g / TOTAL_PIXELS
    avg_b = sum_b / TOTAL_PIXELS
    norm_roughness = edge_energy / TOTAL_PIXELS

    g_cnt = max(1, ground_pixels)
    ground_avg_r = ground_r_sum / g_cnt
    ground_avg_g = ground_g_sum / g_cnt
    ground_avg_b = ground_b_sum / g_cnt

    return {
        "avg_r": avg_r,
        "avg_g": avg_g,
        "avg_b": avg_b,
        "earth_avg_r": (earth_r_sum / earth_total_pixels) if earth_total_pixels > 0 else ground_avg_r,
        "earth_avg_g": (earth_g_sum / earth_total_pixels) if earth_total_pixels > 0 else ground_avg_g,
        "earth_avg_b": (earth_b_sum / earth_total_pixels) if earth_total_pixels > 0 else ground_avg_b,
        "ground_avg_r": ground_avg_r,
        "ground_avg_g": ground_avg_g,
        "ground_avg_b": ground_avg_b,
        "norm_roughness": norm_roughness,
        "ground_earth_ratio": ground_earth_pixels / g_cnt,
        "ground_veg_ratio": ground_veg_pixels / g_cnt,
        "ground_achromatic_ratio": ground_achromatic_pixels / g_cnt,
        "ground_blue_ratio": ground_blue_or_magenta_pixels / g_cnt,
        "red_paint_ratio": red_paint_pixels / interior_pixels,
        "hv_diag_ratio": hv_edges / max(1, diag_edges),
    }


def analyze_image(raw: bytes) -> dict:
    """Analiza una imagen RGB cruda (512x512x3) y devuelve el resultado completo:
    - 'valid': suelo agricola (Arenoso, Arcilloso o Limoso)
    - 'monte': terreno cubierto de monte / maleza / vegetacion
    - 'invalid': imagen ajena al campo (casa, habitacion, piso, objeto, etc.)
    """
    feat = _extract_features(raw)
    avg_r = feat["avg_r"]
    avg_g = feat["avg_g"]
    avg_b = feat["avg_b"]
    norm_roughness = feat["norm_roughness"]

    ground_earth = feat["ground_earth_ratio"]
    ground_veg = feat["ground_veg_ratio"]
    ground_nature = ground_earth + ground_veg
    ground_warmth = feat["ground_avg_r"] - feat["ground_avg_b"]

    # Descartar construcciones (casas pintadas, habitaciones con lineas rectas H/V, pisos grises de cemento/ceramica, objetos azules)
    is_artificial_scene = (
        feat["red_paint_ratio"] > 0.25
        or feat["ground_achromatic_ratio"] > 0.55
        or feat["ground_blue_ratio"] > 0.25
        or (feat["hv_diag_ratio"] > 3.8 and ground_earth < 0.72)
        or norm_roughness < 3.5
        or ground_nature < 0.35
    )

    if is_artificial_scene:
        return _invalid_soil_response(avg_r, avg_g, avg_b, norm_roughness)

    # Caso 1: Terreno con Monte / Abundante Vegetacion
    if ground_veg >= 0.28 and ground_veg > ground_earth * 0.85:
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

    # Caso 2: Suelo Agricola (usa el color promedio de los pixeles de tierra para no distorsionar si hay cielo o pasto arriba)
    if ground_earth < 0.28 or ground_warmth < 5.5:
        return _invalid_soil_response(avg_r, avg_g, avg_b, norm_roughness)

    eval_r = feat["earth_avg_r"]
    eval_g = feat["earth_avg_g"]
    eval_b = feat["earth_avg_b"]

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
