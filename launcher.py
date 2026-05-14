import sys
import os

# Ensure src/ is on path so db_tunnels package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from db_tunnels.main import main

if __name__ == "__main__":
    main()
