#!/bin/bash
set -e

echo "=========================================================="
echo "   EDAFIX - BENCHMARKING CIENTIFICO (HITO 3 - TEL420)     "
echo "=========================================================="

# 1. Asegurar que el cluster Docker este arriba
if [ -f "infrastructure/docker-compose.yml" ]; then
    echo "[1/4] Verificando cluster Docker..."
    docker compose -f infrastructure/docker-compose.yml up -d
fi

# 2. Compilar versiones secuencial y paralela dentro del Master
echo "[2/4] Compilando codigo secuencial y paralelo hibrido..."
docker exec edafix-master bash -c "
    g++ -O2 src/sequential/edafix_seq.cpp -o edafix_seq &&
    mpic++ -O2 -fopenmp src/parallel/edafix_par.cpp -o edafix_par
"

# 3. Ejecutar bateria de pruebas y exportar a CSV
CSV_FILE="data/resultados_benchmark.csv"
echo "N_Imagenes,Nodos_MPI,Hilos_OMP,Total_Cores,Tiempo_Secuencial_s,Tiempo_Paralelo_s,Speedup,Eficiencia" > $CSV_FILE

echo "[3/4] Ejecutando pruebas de carga (Escalabilidad Fuerte y Debil)..."

for N in 500 1000; do
    echo " -> Generando dataset de $N imagenes..."
    docker exec edafix-master python3 data/generate_dataset.py $N

    T1=$(docker exec edafix-master ./edafix_seq $N)
    echo "    [Secuencial N=$N] T1 = $T1 s"

    # Configuraciones: (Procesos MPI, Hilos OpenMP)
    for CONFIG in "1 2" "1 4" "3 1" "3 2" "3 4"; do
        set -- $CONFIG
        NP=$1
        OMP=$2
        TOTAL_P=$((NP * OMP))

        TP=$(docker exec -e OMP_NUM_THREADS=$OMP edafix-master \
            mpirun --allow-run-as-root --hostfile infrastructure/hostfile --map-by node -np $NP ./edafix_par $N)

        # Calcular Speedup y Eficiencia con Python
        METRICS=$(python3 -c "t1=float('$T1'); tp=float('$TP'); p=int('$TOTAL_P'); sp=t1/tp; ep=sp/p; print(f'{sp:.4f},{ep:.4f}')")
        
        echo "    [MPI=$NP | OMP=$OMP | P=$TOTAL_P] Tp = $TP s | Speedup,Eficiencia = $METRICS"
        echo "$N,$NP,$OMP,$TOTAL_P,$T1,$TP,$METRICS" >> $CSV_FILE
    done
done

echo "[4/4] Benchmark finalizado. Resultados guardados en: $CSV_FILE"
cat $CSV_FILE
