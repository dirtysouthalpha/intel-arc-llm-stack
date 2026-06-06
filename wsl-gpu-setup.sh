#!/bin/bash
exec > /tmp/wsl-gpu2.log 2>&1
set -x
apt-get install -y libze-intel-gpu1 libze1 intel-opencl-icd clinfo
echo '=== clinfo -l ==='
clinfo -l
echo '=== DONE ==='