#!/bin/bash
cd "$(dirname "$0")"
export PYTHONPATH="${PYTHONPATH}:$(dirname $(pwd))"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
