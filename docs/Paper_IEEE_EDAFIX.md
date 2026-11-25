# EDAFIX: Arquitectura Paralela Híbrida (OpenMPI + OpenMP) para Clasificación Edafológica, Estimación Óptica de Humedad y Recomendación Agrícola en el Gran Chaco

**Autores:** Isaías Edmundo Armella, Luz Clarita Castillo Duran, Rubiela Alison Parabá Medrano  
**Carrera:** Ingeniería Informática (8.º Semestre) — Facultad de Ciencias Integradas de Yacuiba (FCIC)  
**Universidad:** Universidad Autónoma "Juan Misael Saracho" (UAJMS) — Yacuiba, Tarija, Bolivia  
**Asignatura:** TEL420 - Sistemas Paralelos | **Docente:** Ing. Elias Cassal Baldiviezo  
**Aplicación Web en Producción:** [https://edafix-paralelo.vercel.app/](https://edafix-paralelo.vercel.app/)

---

## Resumen
El procesamiento masivo de imágenes fotográficas de suelos agrícolas representa un reto computacional crítico para la agricultura de precisión en la región del Gran Chaco boliviano. En este artículo se presenta el diseño, despliegue y evaluación experimental de **EDAFIX**, una plataforma de visión artificial paralela basada en un esquema híbrido de memoria distribuida (**OpenMPI**) y memoria compartida (**OpenMP**) implementado en C++, acoplado a una aplicación web operativa desplegada en la nube (**FastAPI + Vercel Serverless**). El clúster de cómputo se implementó sobre tres nodos contenerizados (1 Master y 2 Workers) mediante Docker Compose en estaciones Dell OptiPlex 7010. Las pruebas de rendimiento sobre lotes de 500 y 1000 muestras espectrales ($512 \times 512$ píxeles) demuestran una reducción del tiempo secuencial de $1.865714\text{ s}$ a $0.524547\text{ s}$, alcanzando una aceleración máxima (**Speedup**) de **$3.5568\times$** y una eficiencia distribuida de hasta **$75.64\%$**, validando su escalabilidad bajo las leyes de Amdahl y Gustafson. Adicionalmente, la plataforma incorpora análisis paralelo por lotes de **1 a 10 muestras reales de parcela**, **estimación óptica de humedad edáfica superficial** con filtros estrictos anti-brillo y rechazo de escenas no agrícolas, generación de **reportes técnicos imprimibles en PDF**, planes de manejo agronómico y un **Modo Laboratorio** con barrido automático de escalabilidad y exportación CSV.

## Abstract
Massive image processing of agricultural soils poses a critical computational challenge for precision agriculture in the Bolivian Gran Chaco region. This paper presents the design, deployment, and experimental evaluation of **EDAFIX**, a parallel computer vision platform built on a hybrid distributed-memory (**OpenMPI**) and shared-memory (**OpenMP**) engine in C++, coupled with a production web application (**FastAPI + Vercel Serverless**). Deployed over a three-node containerized Docker cluster (1 Master, 2 Workers), experimental benchmarks across 500 and 1000 soil samples ($512 \times 512$ pixels) demonstrate a runtime reduction from $1.865714\text{ s}$ to $0.524547\text{ s}$, achieving a peak speedup of **$3.5568\times$** and distributed efficiency up to **$75.64\%$**. Furthermore, the operational platform integrates parallel batch analysis of **1 to 10 field images**, **optical surface soil moisture estimation** with strict glare/non-soil rejection filters, printable PDF technical reports, agronomic management plans, and a live scalability sweep laboratory with CSV export.

**Palabras clave:** Cómputo Paralelo Híbrido, OpenMPI, OpenMP, Clasificación Edafológica, Humedad Superficial Óptica, Docker, Gran Chaco.

---

## I. INTRODUCCIÓN Y CONTEXTUALIZACIÓN REGIONAL
La región del Gran Chaco, y en particular el municipio de Yacuiba en el departamento de Tarija, constituye un polo agropecuario estratégico caracterizado por marcados contrastes edafológicos y climáticos. Los suelos locales oscilan entre texturas arenosas en zonas de secano, suelos arcillosos en llanuras aluviales y suelos limosos de transición, exigiendo decisiones agronómicas diferenciadas para optimizar el rendimiento de cultivos como sorgo granífero, sésamo, maíz, soya y fréjol.

En la práctica de campo, diagnosticar una parcela a partir de una sola fotografía resulta insuficiente debido a variaciones puntuales de humedad, sombra o cobertura vegetal; por otro lado, el procesamiento secuencial ($T_1$) de grandes volúmenes de fotografías agrícolas mediante convolución espacial genera severos cuellos de botella ($\mathcal{O}(N \times W \times H)$). El objetivo de este trabajo es resolver ambas limitaciones mediante **EDAFIX**, integrando un motor híbrido de alto rendimiento (OpenMPI + OpenMP) reproducible en Docker con una interfaz web accesible que permite evaluar lotes reales de **1 a 10 imágenes**, estimar humedad superficial y consolidar recomendaciones productivas inmediatas.

---

## II. MARCO TEÓRICO Y TAXONOMÍA DEL SISTEMA
* **Taxonomía de Flynn:** La arquitectura corresponde a un sistema **MIMD (*Multiple Instruction, Multiple Data*)**, donde múltiples nodos e hilos independientes ejecutan extracción espectral, filtrado convolucional y clasificación sobre subconjuntos disjuntos de imágenes.
* **Modelo de Memoria Híbrido (Jerarquía de 2 Niveles):**
  1. **Memoria Distribuida (OpenMPI):** Gestiona el paso de mensajes entre contenedores Docker aislados mediante red virtual TCP/IP, usando particionamiento estático por bloques y reducción colectiva final (`MPI_Reduce`).
  2. **Memoria Compartida (OpenMP):** Explota el paralelismo multihilo dentro de cada nodo multinúcleo mediante `#pragma omp parallel for schedule(dynamic)`, aprovechando memoria caché L1/L2 sin sobrecarga de serialización en red.
* **Modelo LogP y Granularidad:** La latencia ($L$) y el *overhead* ($o$) de red se mitigan aplicando **granularidad gruesa** (imágenes completas de $512 \times 512 \times 3$ bytes por hilo) en lugar de sincronizaciones finas por píxel.
* **Fundamento Óptico de Humedad Edáfica:** Conforme a los principios de reflectancia espectral del suelo, la presencia de película de agua alrededor de las partículas reduce la reflectancia difusa (disminuyendo la luminancia percibida $Y$ y modificando la saturación cromática), lo cual permite estimar de manera orientativa el estado hídrico superficial cuando se normaliza respecto al tipo de suelo.

---

## III. DISEÑO DE ARQUITECTURA E INFRAESTRUCTURA
Sobre estaciones de laboratorio **Dell OptiPlex 7010** (Intel Core i7, 32 GB RAM, Ubuntu Linux / Docker Engine) se implementó un clúster contenerizado reproducible mediante **Docker Compose** (Opción Arquitectónica A) con red virtual dedicada `edafix-net` (`172.25.0.0/24`), acceso SSH RSA sin contraseña y volumen compartido `/workspace`:

| Nodo Contenedor | Hostname | Dirección IPv4 | Imagen Base | Slots MPI / Hilos OMP | Rol en el Clúster |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **`edafix-master`** | `master` | `172.25.0.10` | Ubuntu 22.04 LTS | 4 slots (1–4 hilos) | Orquestación `mpirun`, cómputo local y `MPI_Reduce` |
| **`edafix-worker1`** | `worker1` | `172.25.0.11` | Ubuntu 22.04 LTS | 4 slots (1–4 hilos) | Procesamiento paralelo de sub-lote asignado |
| **`edafix-worker2`** | `worker2` | `172.25.0.12` | Ubuntu 22.04 LTS | 4 slots (1–4 hilos) | Procesamiento paralelo de sub-lote asignado |

Para garantizar disponibilidad pública sin infraestructura dedicada, la capa de servicios **FastAPI** opera en arquitectura dual: en entornos locales con Docker activo delega el cómputo al clúster C++ (OpenMPI + OpenMP), mientras que en el despliegue en la nube (**Vercel Serverless**) ejecuta procesamiento concurrente mediante `ThreadPoolExecutor` con respaldo de métricas experimentales del clúster.

---

## IV. IMPLEMENTACIÓN ALGORÍTMICA PARALELA Y EXTENSIÓN EDAFOLÓGICA
Cada muestra $I \in \mathbb{R}^{512 \times 512 \times 3}$ ($768\text{ KiB}$ en RGB crudo) atraviesa cuatro etapas integradas:

1. **Validación Edafológica y Filtros Anti-Brillo / No-Suelo:**
   El análisis cromático se concentra en la franja inferior ($70\%$) para admitir tomas de parcela con cielo u horizonte. Se rechazan automáticamente como *Terreno No Apto* las escenas artificiales o con iluminación inválida: pintura roja ($>25\%$), superficies acromáticas/cemento ($>55\%$), predominancia azul/magenta ($>25\%$), bordes rectilíneos H/V artificiales, baja textura ($G_{\text{norm}} < 3.5$), **reflejos o brillo especular excesivo ($>28\%$)** y sobreexposición/oscuridad extrema ($Y > 224$ o $Y < 18$). Asimismo, se detecta cobertura vegetal densa (*Terreno con Monte*), bloqueando cualquier cálculo espurio de humedad o rugosidad sobre escenas no válidas.
2. **Extracción Espectral, Convolución Sobel $3\times 3$ y Clasificación Euclidiana:**
   Sobre los píxeles de tierra natural se calcula la energía de borde:
   $$G(x,y) = \sqrt{\left[I(x+1,y) - I(x-1,y)\right]^2 + \left[I(x,y+1) - I(x,y-1)\right]^2}$$
   y la distancia euclidiana $d(v, C_k)$ frente a los centroides regionales: **Arenoso** $(210, 180, 140, 35.0) \rightarrow$ *Sorgo granífero / Sésamo*, **Arcilloso** $(130, 75, 55, 12.0) \rightarrow$ *Maíz / Soya* y **Limoso** $(110, 105, 95, 20.0) \rightarrow$ *Soya / Fréjol*.
3. **Estimación Óptica de Humedad Edáfica Superficial:**
   Exclusivamente para muestras clasificadas como suelo agrícola válido, se calcula la luminancia media de la tierra ($Y = 0.299R + 0.587G + 0.114B$), la proporción de parches oscuros y la saturación HSV, normalizando el índice ($5\%\text{--}95\%$) contra los rangos seco–húmedo propios de cada tipo de suelo para clasificar en **Seco** ($<35\%$), **Humedad Óptima** ($35\%\text{--}70\%$) y **Húmedo / Saturado** ($>70\%$).
4. **Paralelismo Híbrido (C++) y Procesamiento en Lote (1–10 Fotos):**
   En `edafix_par.cpp`, los nodos dividen las imágenes mediante `chunk = N / size` y `remainder = N % size`, ejecutando `#pragma omp parallel for schedule(dynamic) reduction(+:c0,c1,c2)` y consolidando con `MPI_Reduce`. En el servicio web (`POST /api/analyze-batch`), las 1–10 imágenes son redimensionadas en paralelo en el navegador a $512 \times 512$ JPEG ($\sim 0.75\text{ MB}$ por lote de 10 fotos, respetando el límite de $4.5\text{ MB}$ de Vercel), distribuidas en el clúster MPI en local (ej. $4, 3, 3$ muestras en los 3 nodos) o ejecutadas concurrentemente en nube en $< 1\text{ s}$ gracias a muestreo espacial optimizado ($\sim 15\times$ más rápido en Python puro).

---

## V. RESULTADOS EXPERIMENTALES Y ANÁLISIS DE RENDIMIENTO

| Tamaño Lote ($N$) | Configuración | Nodos MPI | Hilos OMP | Total Hilos ($P$) | $T_1$ Secuencial (s) | $T_p$ Paralelo (s) | Speedup ($S_p$) | Eficiencia ($E_p$) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 500 | Secuencial Base | 1 | 1 | 1 | 0.927044 | 0.927044 | 1.0000× | 100.00% |
| 500 | Memoria Compartida | 1 | 2 | 2 | 0.927044 | 0.812453 | 1.1410× | 57.05% |
| 500 | Memoria Compartida | 1 | 4 | 4 | 0.927044 | 0.826560 | 1.1216× | 28.04% |
| 500 | Distribuido Puro | 3 | 1 | 3 | 0.927044 | 0.408551 | 2.2691× | **75.64%** |
| 500 | Híbrido (MPI+OMP) | 3 | 2 | 6 | 0.927044 | 0.286630 | 3.2343× | 53.90% |
| 500 | Híbrido Máximo | 3 | 4 | 12 | 0.927044 | **0.274709** | **3.3746×** | 28.12% |
| 1000 | Secuencial Base | 1 | 1 | 1 | 1.865714 | 1.865714 | 1.0000× | 100.00% |
| 1000 | Memoria Compartida | 1 | 2 | 2 | 1.865714 | 1.608630 | 1.1598× | 57.99% |
| 1000 | Memoria Compartida | 1 | 4 | 4 | 1.865714 | 1.638633 | 1.1386× | 28.46% |
| 1000 | Distribuido Puro | 3 | 1 | 3 | 1.865714 | 0.832435 | 2.2413× | **74.71%** |
| 1000 | Híbrido (MPI+OMP) | 3 | 2 | 6 | 1.865714 | 0.565103 | 3.3015× | 55.03% |
| 1000 | Híbrido Máximo | 3 | 4 | 12 | 1.865714 | **0.524547** | **3.5568×** | 29.64% |

### A. Análisis de Granularidad y Validación de Amdahl / Gustafson
* **Granularidad gruesa:** Migrar del paralelismo por píxel al paralelismo por imagen completa con convolución Sobel $3\times 3$ eliminó la sobrecarga de barreras OpenMP ($S_p < 1$ inicial), alcanzando hasta **$75.64\%$ de eficiencia** en modo distribuido puro ($P=3$).
* **Ley de Amdahl:** La fracción secuencial irreductible ($f \approx 0.21$, asociada a lectura concurrente de disco e inicialización MPI) acota la aceleración teórica cerca de $4.0\times$ en un host de 4 núcleos físicos, coincidiendo con el **$3.5568\times$** medido experimentalmente ($P=12$).
* **Ley de Gustafson:** Al duplicar el lote de $N=500$ a $N=1000$ imágenes, el Speedup escaló de **$3.3746\times$ a $3.5568\times$**, confirmando escalabilidad sostenida.

---

## VI. PLATAFORMA WEB OPERATIVA Y DESPLIEGUE EN PRODUCCIÓN
La solución se consolidó en una aplicación web responsiva ([https://edafix-paralelo.vercel.app/](https://edafix-paralelo.vercel.app/)) dividida en dos módulos funcionales:

* **Modo Agricultor:** Permite cargar **1 a 10 imágenes** mediante arrastre (*drag & drop*), selección múltiple nativa o selector visual desde carpeta (con casillas de 1 clic). Entrega el **diagnóstico consolidado de la parcela** (suelo predominante, composición porcentual, humedad superficial promedio excluyendo muestras inválidas/monte, y tarjetas individuales), un **Plan de Manejo Agronómico** adaptado al Gran Chaco según el cruce *Suelo × Humedad*, **historial local de parcelas** (`localStorage`) y **exportación de Reporte Técnico imprimible en PDF**.
* **Modo Laboratorio:** Permite ejecutar benchmarks puntuales y un **Barrido Completo automático (1, 2 y 4 hilos OpenMP)** que grafica en vivo curvas vectoriales SVG de **Speedup Real vs. Ideal** y **Eficiencia Paralela**, junto a la tabla comparativa descargable en formato **CSV**.

---

## VII. CONCLUSIONES E IMPACTO SOCIAL Y PRODUCTIVO
EDAFIX demuestra que la integración de cómputo paralelo híbrido (OpenMPI + OpenMP) en clústeres Docker con una capa web optimizada para la nube permite trasladar la computación de alto rendimiento a necesidades productivas reales del Gran Chaco. La reducción del tiempo de procesamiento en más de un **$71\%$** ($1.8657\text{ s} \rightarrow 0.5245\text{ s}$), sumada al análisis paralelo de múltiples muestras por parcela, la estimación óptica de humedad superficial con control de brillo y la emisión de reportes técnicos PDF, constituye una herramienta práctica y extensible para fortalecer la agricultura de precisión en Yacuiba y la región chaqueña.

---

## VIII. REFERENCIAS BIBLIOGRÁFICAS
1. M. J. Flynn, "Some Computer Organizations and Their Effectiveness," *IEEE Transactions on Computers*, vol. C-21, no. 9, pp. 948–960, Sept. 1972.
2. G. M. Amdahl, "Validity of the Single Processor Approach to Achieving Large Scale Computing Capabilities," in *Proc. AFIPS Spring Joint Computer Conf.*, 1967, pp. 483–485.
3. J. L. Gustafson, "Reevaluating Amdahl's Law," *Communications of the ACM*, vol. 31, no. 5, pp. 532–533, May 1988.
4. R. Chandra et al., *Parallel Programming in OpenMP*. San Francisco, CA, USA: Morgan Kaufmann, 2001.
5. W. Gropp, E. Lusk, and A. Skjellum, *Using MPI: Portable Parallel Programming with the Message-Passing Interface*, 3rd ed. Cambridge, MA, USA: MIT Press, 2014.
6. D. B. Lobell and G. P. Asner, "Moisture Effects on Soil Reflectance," *Soil Science Society of America Journal*, vol. 66, no. 3, pp. 722–727, May 2002.
