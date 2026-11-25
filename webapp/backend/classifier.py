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
    {
        "soil_type": "Arenoso",
        "crop": CROPS[0],
        "r": 210,
        "g": 180,
        "b": 140,
        "roughness": 35.0,
        "luma_dry": 190.0,
        "luma_wet": 95.0,
    },
    {
        "soil_type": "Arcilloso",
        "crop": CROPS[1],
        "r": 130,
        "g": 75,
        "b": 55,
        "roughness": 12.0,
        "luma_dry": 138.0,
        "luma_wet": 58.0,
    },
    {
        "soil_type": "Limoso",
        "crop": CROPS[2],
        "r": 110,
        "g": 105,
        "b": 95,
        "roughness": 20.0,
        "luma_dry": 148.0,
        "luma_wet": 62.0,
    },
]


def classify_moisture_level(moisture_pct: float) -> tuple[str, str]:
    """Clasifica el porcentaje estimado de humedad superficial y retorna (nivel, recomendacion)."""
    if moisture_pct < 35.0:
        return (
            "Seco",
            "Baja humedad superficial; conviene riego previo o esperar lluvia antes de sembrar",
        )
    if moisture_pct <= 70.0:
        return (
            "Humedad Óptima",
            "Humedad superficial favorable (cercana a capacidad de campo) para siembra",
        )
    return (
        "Húmedo / Saturado",
        "Alta humedad superficial; esperar oreo del terreno para evitar compactación",
    )


def _estimate_soil_moisture(profile: dict, feat: dict) -> dict:
    """Estima opticamente la humedad edafica superficial (0-100%) solo para suelo agricola valido.

    Combina luminancia normalizada al tipo de suelo, proporcion de parches oscuros de tierra
    y saturacion cromatica promedio, excluyendo pixeles sobreexpuestos/brillo.
    """
    luma_dry = profile["luma_dry"]
    luma_wet = profile["luma_wet"]
    span = max(1.0, luma_dry - luma_wet)

    luma_score = (luma_dry - feat["earth_avg_luma"]) / span
    if luma_score < 0.0:
        luma_score = 0.0
    elif luma_score > 1.0:
        luma_score = 1.0

    dark_score = feat["earth_dark_ratio"]
    sat_score = min(1.0, feat["earth_avg_sat"] / 0.55)

    combined = (0.75 * luma_score) + (0.15 * dark_score) + (0.10 * sat_score)
    moisture_pct = round(max(5.0, min(95.0, combined * 100.0)), 1)
    level, advice = classify_moisture_level(moisture_pct)

    return {
        "moisture_index": moisture_pct,
        "moisture_level": level,
        "moisture_advice": advice,
        "lighting_warning": feat["ground_glare_ratio"] > 0.12,
    }


def _extract_features(raw: bytes, step: int = 4) -> dict:
    """Extrae caracteristicas cromaticas, geometricas y de textura tanto globales como en la franja de suelo (70% inferior).

    Usa muestreo uniforme con paso `step` manteniendo vecinos exactos (+/-1 px) para el gradiente
    de textura, reduciendo ~20-30x la latencia en Python puro (ideal para lotes de 1-10 imagenes
    en Vercel Serverless) sin perder precision estadistica.
    """
    sum_r = 0
    sum_g = 0
    sum_b = 0
    edge_energy = 0.0

    # Contadores en la zona de suelo (70% inferior de la imagen, ignorando posible cielo en el 30% superior)
    ground_y_start = int(HEIGHT * 0.30)
    ground_pixels = 0
    ground_earth_pixels = 0
    ground_veg_pixels = 0
    ground_achromatic_pixels = 0
    ground_blue_or_magenta_pixels = 0
    ground_glare_pixels = 0
    ground_r_sum = 0
    ground_g_sum = 0
    ground_b_sum = 0
    ground_luma_sum = 0.0

    earth_r_sum = 0
    earth_g_sum = 0
    earth_b_sum = 0
    earth_luma_sum = 0.0
    earth_sat_sum = 0.0
    earth_dark_pixels = 0
    earth_total_pixels = 0

    red_paint_pixels = 0
    hv_edges = 0
    diag_edges = 0
    sampled_pixels = 0

    row_stride = WIDTH * 3
    x_step = step * 3
    x_end = (WIDTH - 1) * 3
    sqrt = math.sqrt

    for y in range(1, HEIGHT - 1, step):
        row = y * row_stride
        in_ground_zone = y >= ground_y_start
        idx_limit = row + x_end
        idx = row + 3

        while idx < idx_limit:
            sampled_pixels += 1
            r = raw[idx]
            g = raw[idx + 1]
            b = raw[idx + 2]

            sum_r += r
            sum_g += g
            sum_b += b

            c_max = r if r >= g else g
            if b > c_max:
                c_max = b
            c_min = r if r <= g else g
            if b < c_min:
                c_min = b
            chroma = c_max - c_min
            luma = (0.299 * r) + (0.587 * g) + (0.114 * b)

            rg = r - g
            gb = g - b

            # Detectar pintura roja/carmesi artificial (paredes/casas/objetos rojos donde G esta muy cerca de B)
            is_red_paint = (r > 85) and (rg > 20) and (gb < rg * 0.26)
            if is_red_paint:
                red_paint_pixels += 1

            is_glare_pixel = (c_min >= 224) or (luma >= 232.0 and chroma < 28)
            is_valid_brightness = (14 <= r <= 248) and (10 <= g <= 240) and (4 <= b <= 222) and not is_glare_pixel

            # Pixel de tierra natural (incluye arena clara, tierra ocre, arcilla rojiza, limo pardo y tierra negra humeda)
            is_warm_earth = (
                is_valid_brightness
                and (rg >= -2)
                and (gb >= 2)
                and ((r - b) >= 6)
                and (rg <= 95)
                and not ((rg > 20) and (gb < rg * 0.26))
            )

            # Pixel de monte / vegetacion / pastizal
            is_vegetation = (
                is_valid_brightness
                and not is_warm_earth
                and (g >= r - 2)
                and (gb >= 7)
                and (r >= b - 10)
            )

            if is_warm_earth:
                earth_total_pixels += 1
                earth_r_sum += r
                earth_g_sum += g
                earth_b_sum += b
                earth_luma_sum += luma
                if c_max > 0:
                    earth_sat_sum += chroma / c_max
                if luma < 95.0:
                    earth_dark_pixels += 1

            if in_ground_zone:
                ground_pixels += 1
                ground_r_sum += r
                ground_g_sum += g
                ground_b_sum += b
                ground_luma_sum += luma
                if is_glare_pixel:
                    ground_glare_pixels += 1
                if chroma < 9:
                    ground_achromatic_pixels += 1
                if (b > r + 8) or (b > g + 6):
                    ground_blue_or_magenta_pixels += 1
                if is_warm_earth:
                    ground_earth_pixels += 1
                elif is_vegetation:
                    ground_veg_pixels += 1

            gx = raw[idx + 3] - raw[idx - 3]
            gy = raw[idx + row_stride] - raw[idx - row_stride]
            abs_gx = -gx if gx < 0 else gx
            abs_gy = -gy if gy < 0 else gy
            edge_energy += sqrt(gx * gx + gy * gy)

            abs_sum = abs_gx + abs_gy
            if abs_sum > 25:
                if abs_gx > abs_gy * 3 or abs_gy > abs_gx * 3:
                    hv_edges += 1
                else:
                    diff = abs_gx - abs_gy
                    if diff < 0:
                        diff = -diff
                    if diff * 4 < abs_sum:
                        diag_edges += 1

            idx += x_step

    s_cnt = sampled_pixels if sampled_pixels > 0 else 1
    avg_r = sum_r / s_cnt
    avg_g = sum_g / s_cnt
    avg_b = sum_b / s_cnt
    norm_roughness = edge_energy / s_cnt

    g_cnt = ground_pixels if ground_pixels > 0 else 1
    ground_avg_r = ground_r_sum / g_cnt
    ground_avg_g = ground_g_sum / g_cnt
    ground_avg_b = ground_b_sum / g_cnt
    ground_avg_luma = ground_luma_sum / g_cnt

    return {
        "avg_r": avg_r,
        "avg_g": avg_g,
        "avg_b": avg_b,
        "earth_avg_r": (earth_r_sum / earth_total_pixels) if earth_total_pixels > 0 else ground_avg_r,
        "earth_avg_g": (earth_g_sum / earth_total_pixels) if earth_total_pixels > 0 else ground_avg_g,
        "earth_avg_b": (earth_b_sum / earth_total_pixels) if earth_total_pixels > 0 else ground_avg_b,
        "earth_avg_luma": (earth_luma_sum / earth_total_pixels) if earth_total_pixels > 0 else ground_avg_luma,
        "earth_avg_sat": (earth_sat_sum / earth_total_pixels) if earth_total_pixels > 0 else 0.0,
        "earth_dark_ratio": (earth_dark_pixels / earth_total_pixels) if earth_total_pixels > 0 else 0.0,
        "ground_avg_r": ground_avg_r,
        "ground_avg_g": ground_avg_g,
        "ground_avg_b": ground_avg_b,
        "ground_avg_luma": ground_avg_luma,
        "ground_glare_ratio": ground_glare_pixels / g_cnt,
        "norm_roughness": norm_roughness,
        "ground_earth_ratio": ground_earth_pixels / g_cnt,
        "ground_veg_ratio": ground_veg_pixels / g_cnt,
        "ground_achromatic_ratio": ground_achromatic_pixels / g_cnt,
        "ground_blue_ratio": ground_blue_or_magenta_pixels / g_cnt,
        "red_paint_ratio": red_paint_pixels / s_cnt,
        "hv_diag_ratio": hv_edges / (diag_edges if diag_edges > 0 else 1),
    }


def analyze_image(raw: bytes) -> dict:
    """Analiza una imagen RGB cruda (512x512x3) y devuelve el resultado completo:
    - 'valid': suelo agricola (Arenoso, Arcilloso o Limoso) + estimacion optica de humedad superficial
    - 'monte': terreno cubierto de monte / maleza / vegetacion (sin humedad de suelo)
    - 'invalid': imagen ajena al campo, sobreexpuesta o con brillo excesivo (sin metricas de suelo)
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

    # Descartar construcciones, imagenes ajenas, reflejos/brillo excesivo, sobreexposicion o fotos totalmente oscuras
    is_artificial_or_bad_lighting = (
        feat["red_paint_ratio"] > 0.25
        or feat["ground_achromatic_ratio"] > 0.55
        or feat["ground_blue_ratio"] > 0.25
        or feat["ground_glare_ratio"] > 0.28
        or feat["ground_avg_luma"] > 224.0
        or feat["ground_avg_luma"] < 18.0
        or (feat["hv_diag_ratio"] > 3.8 and ground_earth < 0.72)
        or norm_roughness < 3.5
        or ground_nature < 0.35
    )

    if is_artificial_or_bad_lighting:
        return _invalid_soil_response(avg_r, avg_g, avg_b, norm_roughness)

    # Caso 1: Terreno con Monte / Abundante Vegetacion (no estimar humedad de suelo porque lo cubre el follaje)
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
            "moisture_index": None,
            "moisture_level": None,
            "moisture_advice": "No determinable por cobertura vegetal (tomar muestra sobre tierra despejada)",
            "lighting_warning": False,
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
    moisture = _estimate_soil_moisture(profile, feat)
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
        "moisture_index": moisture["moisture_index"],
        "moisture_level": moisture["moisture_level"],
        "moisture_advice": moisture["moisture_advice"],
        "lighting_warning": moisture["lighting_warning"],
    }


def _invalid_soil_response(avg_r: float, avg_g: float, avg_b: float, norm_roughness: float) -> dict:
    return {
        "is_valid_soil": False,
        "soil_status": "invalid",
        "soil_index": -1,
        "soil_type": "Terreno No Apto / No es Suelo Agrícola",
        "recommended_crop": "No se puede sembrar en este suelo (la imagen no corresponde a tierra de cultivo o presenta brillo/iluminación excesiva)",
        "avg_rgb": None,
        "roughness_index": None,
        "moisture_index": None,
        "moisture_level": None,
        "moisture_advice": None,
        "lighting_warning": False,
    }


def classify_image(raw: bytes) -> int:
    """Retorna el indice del tipo de suelo: 0=Arenoso, 1=Arcilloso, 2=Limoso, -1=No apto, -2=Monte."""
    return analyze_image(raw)["soil_index"]
