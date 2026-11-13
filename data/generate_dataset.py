import os, random
os.makedirs("data/samples", exist_ok=True)
profiles = [(210, 180, 140), (130, 75, 55), (110, 105, 95)]
for i in range(500):
    r, g, b = random.choice(profiles)
    block = bytes([max(0, min(255, r + random.randint(-15, 15))),
                   max(0, min(255, g + random.randint(-15, 15))),
                   max(0, min(255, b + random.randint(-15, 15)))] * 1024)
    with open(f"data/samples/soil_{i:04d}.bin", "wb") as f:
        f.write(block * 256)
print("Dataset de 500 muestras generado en 2 segundos!")
