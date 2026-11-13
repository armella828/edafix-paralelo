#include <iostream>
#include <fstream>
#include <vector>
#include <cmath>
#include <chrono>
#include <iomanip>
#include <cstdlib>

using namespace std;

const int WIDTH = 512, HEIGHT = 512;

int classify_image(const vector<unsigned char>& img) {
    double sum_r = 0, sum_g = 0, sum_b = 0;
    double edge_energy = 0;
    int total_pixels = WIDTH * HEIGHT;

    for (int y = 1; y < HEIGHT - 1; ++y) {
        for (int x = 1; x < WIDTH - 1; ++x) {
            int idx = (y * WIDTH + x) * 3;
            sum_r += img[idx];
            sum_g += img[idx + 1];
            sum_b += img[idx + 2];

            int idx_l = (y * WIDTH + (x - 1)) * 3;
            int idx_r = (y * WIDTH + (x + 1)) * 3;
            int idx_u = ((y - 1) * WIDTH + x) * 3;
            int idx_d = ((y + 1) * WIDTH + x) * 3;

            double gx = (double)img[idx_r] - (double)img[idx_l];
            double gy = (double)img[idx_d] - (double)img[idx_u];
            edge_energy += sqrt(gx * gx + gy * gy);
        }
    }

    double avg_r = sum_r / total_pixels;
    double avg_g = sum_g / total_pixels;
    double avg_b = sum_b / total_pixels;
    double norm_roughness = edge_energy / total_pixels;

    double d_arenoso   = sqrt(pow(avg_r - 210, 2) + pow(avg_g - 180, 2) + pow(avg_b - 140, 2) + pow(norm_roughness - 35, 2));
    double d_arcilloso = sqrt(pow(avg_r - 130, 2) + pow(avg_g - 75, 2)  + pow(avg_b - 55, 2)  + pow(norm_roughness - 12, 2));
    double d_limoso    = sqrt(pow(avg_r - 110, 2) + pow(avg_g - 105, 2) + pow(avg_b - 95, 2)  + pow(norm_roughness - 20, 2));

    if (d_arenoso <= d_arcilloso && d_arenoso <= d_limoso) return 0;
    if (d_arcilloso <= d_arenoso && d_arcilloso <= d_limoso) return 1;
    return 2;
}

int main(int argc, char** argv) {
    int num_images = (argc > 1) ? atoi(argv[1]) : 500;
    int counts[3] = {0, 0, 0};

    auto start = chrono::high_resolution_clock::now();

    for (int i = 0; i < num_images; ++i) {
        char filename[64];
        snprintf(filename, sizeof(filename), "data/samples/soil_%04d.bin", i);
        ifstream file(filename, ios::binary);
        if (!file) return 1;
        vector<unsigned char> buffer(WIDTH * HEIGHT * 3);
        file.read(reinterpret_cast<char*>(buffer.data()), buffer.size());
        file.close();

        counts[classify_image(buffer)]++;
    }

    auto end = chrono::high_resolution_clock::now();
    chrono::duration<double> elapsed = end - start;
    cout << fixed << setprecision(6) << elapsed.count() << endl;
    return 0;
}
