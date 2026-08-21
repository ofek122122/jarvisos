# Tiny CUDA vector-add used by jarvis-doctor to prove the toolchain and
# the driver actually execute kernels — not just that nvidia-smi exists.
{
  stdenv,
  cudaPackages,
  autoAddDriverRunpath,
}:
stdenv.mkDerivation {
  pname = "cuda-smoke";
  version = "0.1.0";
  src = ./.;

  nativeBuildInputs = [
    cudaPackages.cuda_nvcc
    autoAddDriverRunpath # patches in /run/opengl-driver/lib for libcuda
  ];
  buildInputs = [ cudaPackages.cuda_cudart ];

  buildPhase = ''
    runHook preBuild
    nvcc -O2 -o cuda-smoke smoke.cu -lcudart
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    install -Dm755 cuda-smoke $out/bin/cuda-smoke
    runHook postInstall
  '';

  meta.mainProgram = "cuda-smoke";
}
