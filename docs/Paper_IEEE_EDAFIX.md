# EDAFIX: Sistema Híbrido de Visión Artificial Distribuida para Clasificación Edafológica en el Gran Chaco

**Asignatura:** TEL420 - Sistemas Paralelos  
**Docente:** Ing. Elias Cassal Baldiviezo  
**Institución:** Universidad Autónoma "Juan Misael Saracho" — Facultad de Ciencias Integradas del Gran Chaco (Yacuiba)  

---

## Resumen (Abstract)
El presente documento técnico describe el diseño, implementación y evaluación experimental de **EDAFIX**, una arquitectura de cómputo paralelo híbrido (Memoria Distribuida con **OpenMPI** + Memoria Compartida con **OpenMP**) orientada a la clasificación edafológica de suelos agrícolas de la región del Gran Chaco (*Arenoso*, *Arcilloso* y *Limoso*). El sistema procesa lotes masivos de muestras digitales ($N \in \{500, 1000\}$ imágenes RGB de $512 \times 512$ píxeles) aplicando extracción cromática espectral y convolución espacial mediante el operador de bordes **Sobel $3 \times 3$** para estimar el índice de rugosidad superficial. Las pruebas experimentales sobre un clúster distribuido de 3 nodos contenedores demuestran una reducción del tiempo de ejecución desde $T_1 = 1.865714\text{ s}$ (secuencial) hasta $T_p = 0.524547\text{ s}$ (paralelo con 3 nodos MPI y 4 hilos OpenMP por nodo), alcanzando un **Speedup máximo de $3.5568\times$**.

---

## 1. Introducción y Problemática (Hito 1)
La clasificación de textura y composición superficial del suelo es determinante para la recomendación de cultivos estratégicos en el Gran Chaco (Sorgo granífero, Sésamo, Maíz, Soya y Fréjol). Sin embargo, el procesamiento píxel a píxel de grandes volúmenes de imágenes de alta resolución presenta una complejidad computacional de orden $\mathcal{O}(N \times W \times H)$, generando un cuello de botella cuando se ejecuta de forma secuencial en un único hilo de CPU.

### 1.1 Perfiles Edafológicos de Referencia
Cada muestra se modela como una matriz tridimensional cruda de $512 \times 512 \times 3$ bytes ($786,432$ bytes por imagen) y se clasifica mediante distancia euclidiana multidimensional hacia tres centroides edafológicos:

| Tipo de Suelo | Promedio Rojo ($R$) | Promedio Verde ($G$) | Promedio Azul ($B$) | Rugosidad Sobel ($\hat{E}$) | Cultivo Recomendado (Gran Chaco) |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Arenoso** | 210 | 180 | 140 | 35.0 | Sorgo granífero / Sésamo |
| **Arcilloso** | 130 | 75 | 55 | 12.0 | Maíz / Soya |
| **Limoso** | 110 | 105 | 95 | 20.0 | Soya / Fréjol |

---

## 2. Arquitectura del Clúster y Algoritmo Secuencial (Hito 2)

### 2.1 Topología de Red y Nodos
El clúster se despliega sobre tres contenedores Ubuntu 22.04 interconectados a través de una red virtual tipo *bridge* (`172.25.0.0/24`) con autenticación SSH mediante llaves RSA sin contraseña:

* **Nodo Maestro (`edafix-master`):** `172.25.0.10` (`slots=4`)
* **Nodo Trabajador 1 (`edafix-worker1`):** `172.25.0.11` (`slots=4`)
* **Nodo Trabajador 2 (`edafix-worker2`):** `172.25.0.12` (`slots=4`)

Para evitar cuellos de botella de entrada/salida (I/O) propios de motores de bases de datos relacionales durante lecturas concurrentes, el almacenamiento se implementó sobre archivos binarios crudos de acceso directo (`data/samples/soil_0000.bin` a `soil_0999.bin`).

### 2.2 Modelo Matemático del Operador Sobel y Clasificación ($T_1$)
Para cada píxel interior $(x, y)$ de cada imagen, el motor secuencial (`src/sequential/edafix_seq.cpp`) calcula los gradientes horizontales y verticales:

$$G_x(x,y) = I(x+1, y) - I(x-1, y), \qquad G_y(x,y) = I(x, y+1) - I(x, y-1)$$

La energía de borde normalizada (rugosidad) se obtiene como:

$$\hat{E} = \frac{1}{W \cdot H} \sum_{y=1}^{H-2} \sum_{x=1}^{W-2} \sqrt{G_x(x,y)^2 + G_y(x,y)^2}$$

---

## 3. Paralelización Híbrida OpenMPI + OpenMP (Hito 3)

El motor paralelo (`src/parallel/edafix_par.cpp`) combina dos paradigmas de paralelismo:

1. **Nivel 1 — Memoria Distribuida (OpenMPI):**
   El conjunto total de $N$ imágenes se particiona equitativamente entre los $M = 3$ procesos MPI utilizando `MPI_Comm_rank` y `MPI_Comm_size`:
   $$\text{chunk} = \lfloor N / M \rfloor, \qquad \text{remainder} = N \bmod M$$
   Al finalizar el procesamiento local, los conteos parciales de cada clase edafológica se consolidan en el nodo maestro mediante `MPI_Reduce` con la operación `MPI_SUM`.

2. **Nivel 2 — Memoria Compartida (OpenMP):**
   Cada nodo paraleliza su subconjunto de imágenes entre $T \in \{1, 2, 4\}$ hilos de CPU mediante planificación dinámica y reducción atómica libre de condiciones de carrera:
   ```cpp
   #pragma omp parallel for schedule(dynamic) reduction(+:c0,c1,c2)
   ```

---

## 4. Resultados Experimentales y Análisis de Rendimiento

Las métricas de desempeño se evaluaron bajo las definiciones clásicas de **Speedup** ($S_p = T_1 / T_p$) y **Eficiencia** ($E_p = S_p / P$, donde $P = \text{Nodos MPI} \times \text{Hilos OpenMP}$):

| Lote ($N$) | Nodos MPI | Hilos OMP | Total Núcleos ($P$) | $T_1$ Secuencial (s) | $T_p$ Paralelo (s) | Speedup ($S_p$) | Eficiencia ($E_p$) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 500 | 1 | 2 | 2 | 0.927044 | 0.812453 | 1.1410× | 57.05% |
| 500 | 1 | 4 | 4 | 0.927044 | 0.826560 | 1.1216× | 28.04% |
| 500 | 3 | 1 | 3 | 0.927044 | 0.408551 | 2.2691× | 75.64% |
| 500 | 3 | 2 | 6 | 0.927044 | 0.286630 | 3.2343× | 53.90% |
| 500 | 3 | 4 | 12 | 0.927044 | 0.274709 | 3.3746× | 28.12% |
| 1000 | 1 | 2 | 2 | 1.865714 | 1.608630 | 1.1598× | 57.99% |
| 1000 | 1 | 4 | 4 | 1.865714 | 1.638633 | 1.1386× | 28.46% |
| 1000 | 3 | 1 | 3 | 1.865714 | 0.832435 | 2.2413× | 74.71% |
| 1000 | 3 | 2 | 6 | 1.865714 | 0.565103 | 3.3015× | 55.03% |
| 1000 | 3 | 4 | 12 | 1.865714 | 0.524547 | **3.5568×** | 29.64% |

---

## 5. Conclusiones
1. **Escalabilidad Fuerte:** Para un tamaño de carga fijo ($N=1000$), incrementar el paralelismo híbrido de 1 núcleo hasta 3 nodos MPI con 4 hilos OpenMP reduce el tiempo de respuesta de $1.865\text{ s}$ a $0.524\text{ s}$ ($S_p = 3.5568\times$).
2. **Escalabilidad Débil:** Al duplicar la carga de trabajo de $N=500$ a $N=1000$, el Speedup del clúster se incrementa de $3.3746\times$ a $3.5568\times$, demostrando que a mayor volumen de datos se amortiza mejor la latencia de sincronización de red (`MPI_Barrier` y `MPI_Reduce`).
3. **Transferencia Tecnológica:** La integración del motor con una interfaz web FastAPI (`Modo Agricultor` y `Modo Laboratorio`) permite acercar el cómputo paralelo científico a la toma de decisiones agrícolas reales en el Gran Chaco.
