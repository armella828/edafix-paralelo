#include <mpi.h>
#include <omp.h>
#include <iostream>
#include <fstream>
#include <vector>
#include <cmath>
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
    MPI_Init(&argc, &argv);

    int rank, size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    int num_images = (argc > 1) ? atoi(argv[1]) : 500;

    MPI_Barrier(MPI_COMM_WORLD);
    double start_time = MPI_Wtime();

    int chunk = num_images / size;
    int remainder = num_images % size;
    int start_idx = rank * chunk + min(rank, remainder);
    int end_idx = start_idx + chunk + (rank < remainder ? 1 : 0);

    int c0 = 0, c1 = 0, c2 = 0;

    #pragma omp parallel for schedule(dynamic) reduction(+:c0,c1,c2)
    for (int i = start_idx; i < end_idx; ++i) {
        char filename[64];
        snprintf(filename, sizeof(filename), "data/samples/soil_%04d.bin", i);
        ifstream file(filename, ios::binary);
        if (file) {
            vector<unsigned char> buffer(WIDTH * HEIGHT * 3);
            file.read(reinterpret_cast<char*>(buffer.data()), buffer.size());
            file.close();
            int soil = classify_image(buffer);
            if (soil == 0) c0++;
            else if (soil == 1) c1++;
            else c2++;
        }
    }

    int local_counts[3] = {c0, c1, c2};
    int global_counts[3] = {0, 0, 0};

    MPI_Reduce(local_counts, global_counts, 3, MPI_INT, MPI_SUM, 0, MPI_COMM_WORLD);

    MPI_Barrier(MPI_COMM_WORLD);
    double end_time = MPI_Wtime();

    if (rank == 0) {
        cout << fixed << setprecision(6) << (end_time - start_time) << endl;
    }

    MPI_Finalize();
    return 0;
}
