#!/usr/bin/env bash
set -e
pip install -e .
cd apps/web && npm install
