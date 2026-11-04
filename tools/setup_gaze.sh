#!/bin/sh
# Optional laptop-only Part B environment. Run from any directory; requires uv/git/curl.
set -eu
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="$PWD/.tools/uv-cache"
export UV_PYTHON_INSTALL_DIR="$PWD/.tools/python"
mkdir -p .tools/gaze-models output/part-b/inputs
if [ ! -d .tools/gaze-env ]; then
  uv venv --python 3.12 .tools/gaze-env
fi
uv pip sync --python .tools/gaze-env/bin/python tools/gaze-requirements.lock

checkout() {
  if [ ! -d "$2/.git" ]; then git clone "$1" "$2"; fi
  git -C "$2" checkout "$3"
}
checkout https://github.com/idiap/MTGS.git .tools/MTGS a2ce45f44ed73d86e89e16bffb6be7a9567e3052
checkout https://github.com/facebookresearch/dinov2.git .tools/dinov2 7764ea0f912e53c92e82eb78a2a1631e92725fc8

download() {
  if [ ! -f "$2" ]; then
    curl -L --fail --retry 3 "$1" -o "$2.partial"
    mv "$2.partial" "$2"
  fi
  printf '%s  %s\n' "$3" "$2" | shasum -a 256 -c -
}
download https://huggingface.co/Idiap/mtgs-static-vsgaze/resolve/dc0e35b2f37bd594cccdd5177ea9317a6e131d02/mtgs-static-vsgaze.ckpt .tools/gaze-models/mtgs-static-vsgaze.ckpt 30f340477ec5c7f5cc48e905b2f35565b3714e29dda03956d3b6d9a77421d31f
download https://huggingface.co/MK-CUPIST/crowdhuman_yolov5m/resolve/ed73865c731033a1b48f61de3894f074e2acf4e1/crowdhuman_yolov5m.pt .tools/gaze-models/crowdhuman_yolov5m.pt 2e220dee5fe94145c20eab2679bc94f6987e4a736e71fbbb703b111c7d3dfcee
download https://github.com/yakhyo/gaze-estimation/releases/download/weights/mobileone_s0_gaze.onnx .tools/gaze-models/mobileone_s0_gaze.onnx 8b4fdc4e3da44733c9a82e7776b411e4a39f94e8e285aee0fc85a548a55f7d9f
download https://raw.githubusercontent.com/yakhyo/gaze-estimation/main/assets/in_video.mp4 output/part-b/inputs/classroom.mp4 297ba55e2f547a6ee8ae17e11a61035f7efb67ec95a05f5faf859a3fa7e100df
download https://storage.openvinotoolkit.org/data/test_data/videos/face-demographics-walking.mp4 output/part-b/inputs/walking.mp4 91af68da819a9c0caab06c6c21414e6ebdb378ff28fee90e1f937165bc1007c6
UNIFACE_CACHE_DIR="$PWD/.tools/gaze-models" .tools/gaze-env/bin/python -c 'from uniface import RetinaFace; from uniface.constants import RetinaFaceWeights; RetinaFace(model_name=RetinaFaceWeights.MNET_025, input_size=(320,320), providers=["CPUExecutionProvider"])'
