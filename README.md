# EDAFIX: Sistema Híbrido de Visión Artificial Distribuida para Clasificación Edafológica

**Asignatura:** TEL420 - Sistemas Paralelos  
**Docente:** Ing. Elias Cassal Baldiviezo  
**Institución:** Universidad Autónoma "Juan Misael Saracho" (FCIC - Yacuiba)  
**Integrantes:** Isaías Edmundo Armella, Luz Clarita Castillo Duran, Rubiela Alison Parabá Medrano  
**Aplicación Web en Vivo:** [https://edafix-paralelo.vercel.app/](https://edafix-paralelo.vercel.app/)

---

## 1. Estructura Oficial del Repositorio
```text
edafix-paralelos/
├── src/
│   ├── sequential/edafix_seq.cpp    # Motor secuencial base (T1)
│   └── parallel/edafix_par.cpp      # Motor paralelo híbrido (OpenMPI + OpenMP)
├── infrastructure/
│   ├── Dockerfile                   # Imagen Ubuntu 22.04 + GCC/OpenMP + OpenMPI + SSH RSA
│   ├── docker-compose.yml           # Clúster de 3 nodos en red bridge 172.25.0.0/24
│   └── hostfile                     # Topología MPI (master, worker1, worker2 con 4 slots)
├── data/
│   ├── generate_dataset.py          # Generador de lotes binarios RGB (512x512x3 bytes)
│   └── resultados_benchmark.csv     # Reporte experimental T1, Tp, Speedup y Eficiencia
├── scripts/
│   ├── benchmark.sh                 # Script automatizado de compilación y benchmarking
│   ├── start_app.sh                 # Inicio de servidores en Linux
│   └── start_app.ps1                # Inicio de servidores en Windows
├── docs/
│   └── Paper_IEEE_EDAFIX.md         # Informe Técnico en formato Paper IEEE (Hitos 1, 2 y 3)
└── webapp/
    ├── backend/                     # API FastAPI + Clasificador Edafológico Sobel 3x3
    └── frontend/                    # Interfaz Web (Modo Agricultor y Modo Laboratorio)
```

---

## 2. Arquitectura del Clúster Contenerizado (Opción A — Hito 2)
Desplegado sobre estación **Dell OptiPlex 7010** (Intel Core i7, 32 GB RAM, Ubuntu Linux / Docker):
* **Master (`edafix-master`):** `172.25.0.10` (`slots=4`)
* **Worker 1 (`edafix-worker1`):** `172.25.0.11` (`slots=4`)
* **Worker 2 (`edafix-worker2`):** `172.25.0.12` (`slots=4`)
* **Red Virtual:** Bridge interna `edafix-net` (`172.25.0.0/24`) con acceso SSH sin contraseña y volumen compartido `/workspace`.
* **Huella de Memoria Inicial:** Cada muestra RGB cruda de $512 \times 512 \times 3$ bytes ocupa exactamente **$786,432\text{ bytes}$ ($768\text{ KiB}$)** en RAM por hilo (`std::vector<unsigned char>`), totalizando $\sim 9.2\text{ MB}$ de memoria activa concurrente para $P = 12$ hilos.

---

## 3. Instrucciones de Clonación, Arranque y Smoke Test (Hito 2)

### Paso 1: Clonar el repositorio
```bash
git clone https://github.com/armella828/edafix-paralelo.git
cd edafix-paralelo
```

### Paso 2: Levantar el clúster de 3 contenedores con Docker Compose
```bash
docker compose -f infrastructure/docker-compose.yml up -d --build
```

### Paso 3: Prueba de conectividad distribuida y SSH sin contraseña (Smoke Test MPI)
```bash
docker exec edafix-master mpirun --allow-run-as-root --hostfile infrastructure/hostfile --map-by node -np 3 hostname
```
*(Retorna `master`, `worker1` y `worker2` verificando resolución de nombres y ejecución remota).*

### Paso 4: Compilar y ejecutar Código Secuencial ($T_1$) vs. Paralelo Híbrido ($T_p$)
```bash
# Compilar versión secuencial y paralela híbrida (OpenMPI + OpenMP)
docker exec edafix-master bash -c "g++ -O2 src/sequential/edafix_seq.cpp -o edafix_seq && mpic++ -O2 -fopenmp src/parallel/edafix_par.cpp -o edafix_par"

# Generar dataset de 1000 muestras binarias (512x512x3)
docker exec edafix-master python3 data/generate_dataset.py 1000

# Ejecutar versión secuencial base (T1)
docker exec edafix-master ./edafix_seq 1000

# Ejecutar versión paralela híbrida (3 nodos MPI x 4 hilos OpenMP = 12 hilos)
docker exec -e OMP_NUM_THREADS=4 edafix-master mpirun --allow-run-as-root --hostfile infrastructure/hostfile --map-by node -np 3 ./edafix_par 1000
```

### Paso 5: Monitoreo de Recursos y Memoria en Vivo
```bash
# Ver consumo de CPU y memoria RAM de los 3 contenedores en el host
docker stats edafix-master edafix-worker1 edafix-worker2

# Monitoreo interactivo de núcleos dentro del nodo coordinador
docker exec -it edafix-master htop
```

---

## 4. Reproducibilidad Automatizada del Benchmark (Un Solo Comando — Hito 3)
Para compilar, generar los datasets de 500 y 1000 muestras y exportar el reporte CSV de rendimiento:
```bash
chmod +x scripts/benchmark.sh
sudo ./scripts/benchmark.sh
```

---

## 5. Resultados Experimentales Obtenidos

| Lote ($N$) | Nodos MPI | Hilos OMP | Total Hilos ($P$) | $T_1$ Secuencial (s) | $T_p$ Paralelo (s) | Speedup ($S_p$) | Eficiencia ($E_p$) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 500 | 3 | 1 | 3 | 0.927044 | 0.408551 | 2.2691× | **75.64%** |
| 500 | 3 | 2 | 6 | 0.927044 | 0.286630 | 3.2343× | 53.90% |
| 500 | 3 | 4 | 12 | 0.927044 | 0.274709 | 3.3746× | 28.12% |
| 1000 | 3 | 1 | 3 | 1.865714 | 0.832435 | 2.2413× | **74.71%** |
| 1000 | 3 | 2 | 6 | 1.865714 | 0.565103 | 3.3015× | 55.03% |
| 1000 | 3 | 4 | 12 | 1.865714 | **0.524547** | **3.5568×** | 29.64% |
