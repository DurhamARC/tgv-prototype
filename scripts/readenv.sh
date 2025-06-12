#!/usr/bin/env bash
# Source this script using "source scripts/readenv.sh"
export $(cat .env | awk '''!/^\s*#/''' | xargs)
