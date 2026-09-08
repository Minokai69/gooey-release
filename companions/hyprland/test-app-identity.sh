#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
mkdir -p build
"${CXX:-c++}" -std=c++23 -Wall -Wextra -Werror -pedantic -I. tests/appIdentity.cpp -o build/app-identity-test
build/app-identity-test
