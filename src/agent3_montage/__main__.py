"""
module Montage & Animation — Entrée CLI avec `python -m agent3_montage`
"""

from agent3_montage.cli import main

if __name__ == "__main__":
    import asyncio
    import sys
    sys.exit(asyncio.run(main()))
