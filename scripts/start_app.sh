#!/bin/bash
# EDAFIX - Script de inicio del backend FastAPI y del frontend estatico

PROJECT_ROOT="/home/isaias/edafix-paralelos"
BACKEND_DIR="$PROJECT_ROOT/webapp/backend"
FRONTEND_DIR="$PROJECT_ROOT/webapp/frontend"
BACKEND_LOG="/tmp/edafix_backend.log"
FRONTEND_LOG="/tmp/edafix_frontend.log"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "🧹 Deteniendo servidores EDAFIX..."
  if [ -n "$BACKEND_PID" ]; then kill "$BACKEND_PID" 2>/dev/null; fi
  if [ -n "$FRONTEND_PID" ]; then kill "$FRONTEND_PID" 2>/dev/null; fi
  wait 2>/dev/null
  echo "✅ Servidores detenidos."
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "=========================================================="
echo "   EDAFIX - INICIO DE SERVIDORES"
echo "=========================================================="

# 1. Verificar que los contenedores Docker esten encendidos
echo "[1/3] Verificando contenedores Docker..."
for c in edafix-master edafix-worker1 edafix-worker2; do
  state=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo "missing")
  if [ "$state" != "running" ]; then
    echo "❌ El contenedor '$c' NO esta corriendo (estado: ${state:-missing})."
    echo "   Inicia el cluster con: sudo docker compose -f infrastructure/docker-compose.yml up -d"
    exit 1
  fi
  echo "✅ Contenedor $c corriendo"
done

# 2. Instalar dependencias del backend si no estan instaladas
echo "[2/3] Instalando dependencias de webapp/backend/requirements.txt..."
if ! webapp/backend/venv/bin/python -c "import fastapi, uvicorn, PIL, multipart" >/dev/null 2>&1; then
  echo "📦 Instalando dependencias..."
  python3 -m webapp/backend/venv/bin/pip install -r "$BACKEND_DIR/requirements.txt"
else
  echo "✅ Dependencias ya instaladas"
fi

# 3. Levantar backend FastAPI en el puerto 8000
echo "[3/3] Levantando servidor FastAPI en el puerto 8000..."
cd "$BACKEND_DIR"
nohup venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
BACKEND_READY=0
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
    BACKEND_READY=1
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "❌ El backend FastAPI (uvicorn) fallo al iniciar. Log: $BACKEND_LOG"
    tail -30 "$BACKEND_LOG"
    exit 1
  fi
  sleep 1
done
if [ "$BACKEND_READY" != "1" ]; then
  echo "❌ Timeout esperando el backend FastAPI en el puerto 8000."
  exit 1
fi

# 4. Servir webapp/frontend con un servidor estatico en el puerto 3000
echo "🌐 Sirviendo webapp/frontend en el puerto 3000..."
cd "$FRONTEND_DIR"
nohup python3 -m http.server 3000 > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
FRONTEND_READY=0
for i in $(seq 1 15); do
  if curl -sf http://127.0.0.1:3000/ > /dev/null 2>&1; then
    FRONTEND_READY=1
    break
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "❌ El servidor estatico (http.server) fallo al iniciar. Log: $FRONTEND_LOG"
    tail -30 "$FRONTEND_LOG"
    exit 1
  fi
  sleep 1
done
if [ "$FRONTEND_READY" != "1" ]; then
  echo "❌ Timeout esperando el servidor estatico en el puerto 3000."
  exit 1
fi

# 5. Mostrar URLs finales
echo ""
echo "=========================================================="
echo "   ✅ SERVIDORES INICIADOS CORRECTAMENTE"
echo "=========================================================="
echo "🌐 Frontend (listo para abrir en el navegador):  http://localhost:3000"
echo "⚙️  Backend API (documentacion interactiva):     http://localhost:8000/docs"
echo ""
echo "👉 Abre en tu navegador:  http://localhost:3000"
echo ""
echo "Para detener ambos servidores: presiona Ctrl+C en esta terminal."

wait
