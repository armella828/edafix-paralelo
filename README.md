# EDAFIX: Sistema Híbrido de Visión Artificial Distribuida para Clasificación Edafológica

**Asignatura:** TEL420 - Sistemas Paralelos  
**Docente:** Ing. Elias Cassal Baldiviezo  
**Institución:** Universidad Autónoma "Juan Misael Saracho" (FCIC - Yacuiba)  

## 1. Topología del Clúster (Opción A)
Infraestructura contenerizada con **Docker Compose** sobre red *bridge* (`172.25.0.0/24`) y comunicación OpenMPI sin contraseña:
* **Master (`edafix-master`):** `172.25.0.10`
* **Worker 1 (`edafix-worker1`):** `172.25.0.11`
* **Worker 2 (`edafix-worker2`):** `172.25.0.12`

## 2. Resultados Línea Base Secuencial (Hito 2)
* **Dataset de prueba:** 500 matrices de suelo (512x512 RGB).
* **Distribución obtenida:** 161 Arenoso | 156 Arcilloso | 183 Limoso.
* **Tiempo Secuencial (T1):** `0.5713 segundos`.
