# EDAFIX: Sistema Híbrido de Visión Artificial Distribuida para Clasificación Edafológica

**Asignatura:** TEL420 - Sistemas Paralelos  
**Docente:** Ing. Elias Cassal Baldiviezo  
**Institución:** Universidad Autónoma "Juan Misael Saracho" (FCIC - Yacuiba)  

## 1. Arquitectura del Clúster (Opción A)
* **Master (`edafix-master`):** `172.25.0.10`
* **Worker 1 (`edafix-worker1`):** `172.25.0.11`
* **Worker 2 (`edafix-worker2`):** `172.25.0.12`
* **Red Virtual:** Bridge interna `172.25.0.0/24` con SSH sin contraseña.

## 2. Reproducibilidad Automatizada (Un Solo Comando)
Para compilar, generar los datasets de 500 y 1000 muestras y obtener el reporte CSV de rendimiento:
```bash
chmod +x scripts/benchmark.sh
sudo ./scripts/benchmark.sh
```

## 3. Resultados Experimentales Obtenidos

| Lote (N) | Nodos MPI | Hilos OMP | Total Hilos (P) | T₁ Secuencial (s) | Tₚ Paralelo (s) | Speedup (Sₚ) | Eficiencia (Eₚ) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 500 | 3 | 1 | 3 | 0.927044 | 0.408551 | 2.2691× | 75.64% |
| 500 | 3 | 4 | 12 | 0.927044 | 0.274709 | 3.3746× | 28.12% |
| 1000 | 3 | 1 | 3 | 1.865714 | 0.832435 | 2.2413× | 74.71% |
| 1000 | 3 | 4 | 12 | 1.865714 | 0.524547 | 3.5568× | 29.64% |

## 4. Comandos para Demostración en Vivo (Live Demo)
* **Variar hilos OpenMP en tiempo real:** `docker exec -e OMP_NUM_THREADS=4 edafix-master mpirun --allow-run-as-root --hostfile infrastructure/hostfile --map-by node -np 3 ./edafix_par 1000`
* **Monitoreo de núcleos:** `docker exec -it edafix-master htop`
