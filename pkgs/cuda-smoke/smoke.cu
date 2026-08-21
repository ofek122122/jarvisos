// cuda-smoke — the trivial CUDA kernel jarvis-doctor runs (BRIEF-phase0
// task 3). Vector add on the GPU, verified on the CPU. Prints the device
// name and PASS/FAIL; exit code 0 only on PASS.
#include <cstdio>
#include <cuda_runtime.h>

#define CHECK(call)                                                      \
  do {                                                                   \
    cudaError_t err = (call);                                            \
    if (err != cudaSuccess) {                                            \
      std::fprintf(stderr, "FAIL cuda-smoke: %s at %s:%d\n",             \
                   cudaGetErrorString(err), __FILE__, __LINE__);         \
      return 1;                                                          \
    }                                                                    \
  } while (0)

__global__ void vecAdd(const float *a, const float *b, float *c, int n) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i < n) c[i] = a[i] + b[i];
}

int main() {
  const int n = 1 << 20;
  const size_t bytes = n * sizeof(float);

  cudaDeviceProp prop;
  CHECK(cudaGetDeviceProperties(&prop, 0));
  std::printf("cuda-smoke: device 0 = %s\n", prop.name);

  float *ha = new float[n], *hb = new float[n], *hc = new float[n];
  for (int i = 0; i < n; i++) { ha[i] = float(i); hb[i] = 2.0f * float(i); }

  float *da, *db, *dc;
  CHECK(cudaMalloc(&da, bytes));
  CHECK(cudaMalloc(&db, bytes));
  CHECK(cudaMalloc(&dc, bytes));
  CHECK(cudaMemcpy(da, ha, bytes, cudaMemcpyHostToDevice));
  CHECK(cudaMemcpy(db, hb, bytes, cudaMemcpyHostToDevice));

  vecAdd<<<(n + 255) / 256, 256>>>(da, db, dc, n);
  CHECK(cudaGetLastError());
  CHECK(cudaMemcpy(hc, dc, bytes, cudaMemcpyDeviceToHost));

  for (int i = 0; i < n; i++) {
    if (hc[i] != 3.0f * float(i)) {
      std::fprintf(stderr, "FAIL cuda-smoke: wrong result at %d\n", i);
      return 1;
    }
  }

  std::printf("PASS cuda-smoke: %d-element vecAdd verified\n", n);
  return 0;
}
