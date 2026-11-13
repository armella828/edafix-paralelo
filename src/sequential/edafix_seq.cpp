#include <iostream>
#include <fstream>
#include <vector>
#include <cmath>
#include <chrono>
#include <iomanip>
using namespace std;

const int WIDTH = 512, HEIGHT = 512, NUM_IMAGES = 500;
struct SoilResult { string soil_type; string recommendation; };

SoilResult classify_soil(const vector<unsigned char>& img) {
    double sum_r = 0, sum_g = 0, sum_b = 0;
    int total_pixels = WIDTH * HEIGHT;
    for (int i = 0; i < total_pixels * 3; i += 3) {
        sum_r += img[i];
        sum_g += img[i + 1];
        sum_b += img[i + 2];
    }
    double avg_r = sum_r / total_pixels;
    double avg_g = sum_g / total_pixels;
    double avg_b = sum_b / total_pixels;

    double d_arenoso   = sqrt(pow(avg_r - 210, 2) + pow(avg_g - 180, 2) + pow(avg_b - 140, 2));
    double d_arcilloso = sqrt(pow(avg_r - 130, 2) + pow(avg_g - 75, 2)  + pow(avg_b - 55, 2));
    double d_limoso    = sqrt(pow(avg_r - 110, 2) + pow(avg_g - 105, 2) + pow(avg_b - 95, 2));

    if (d_arenoso <= d_arcilloso && d_arenoso <= d_limoso)
        return {"Arenoso", "Sorgo granifero / Sesamo"};
    else if (d_arcilloso <= d_arenoso && d_arcilloso <= d_limoso)
        return {"Arcilloso", "Maiz / Soya"};
    else
        return {"Limoso", "Soya / Frejol"};
}

int main() {
    auto start = chrono::high_resolution_clock::now();
    int c_are = 0, c_arc = 0, c_lim = 0;
    for (int i = 0; i < NUM_IMAGES; ++i) {
        char filename[64];
        snprintf(filename, sizeof(filename), "data/samples/soil_%04d.bin", i);
        ifstream file(filename, ios::binary);
        if (!file) { cerr << "Error abriendo: " << filename << endl; return 1; }
        vector<unsigned char> buffer(WIDTH * HEIGHT * 3);
        file.read(reinterpret_cast<char*>(buffer.data()), buffer.size());
        file.close();
        SoilResult res = classify_soil(buffer);
        if (res.soil_type == "Arenoso") c_are++;
        else if (res.soil_type == "Arcilloso") c_arc++;
        else c_lim++;
    }
    auto end = chrono::high_resolution_clock::now();
    chrono::duration<double> elapsed = end - start;
    cout << "Procesadas: " << NUM_IMAGES << " | Arenoso: " << c_are << " Arcilloso: " << c_arc << " Limoso: " << c_lim << endl;
    cout << fixed << setprecision(4) << "Tiempo Secuencial (T1): " << elapsed.count() << " s" << endl;
    return 0;
}
