@echo off
title Open Git Graph (Zero-Server)
cd /d "%~dp0"
python generate_dag.py
start "" "index.html"
