import os, sys, random

num_samples = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
os.makedirs("data/samples", exist_ok=True)
profiles = [(210, 180, 140), (130, 75, 55), (110, 105, 95)]

for i in range(num_samples):
    r, g, b = random.choice(profiles)
    # Generar bloque con variacion de textura espacial
    row = bytearray()
    for x in range(512):
        noise = (x % 7) * 3 - 9
        row.extend([
            max(0, min(255, r + random.randint(-12, 12) + noise)),
            max(0, min(255, g + random.randint(-12, 12) + noise)),
            max(0, min(255, b + random.randint(-12, 12) + noise))
        ])
    with open(f"data/samples/soil_{i:04d}.bin", "wb") as f:
        f.write(bytes(row) * 512)

print(f"Dataset de {num_samples} muestras generado.")
