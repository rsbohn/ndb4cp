# ingest.py
"""Ingest .ndb data"""

from ndb.db import cas_put as put

def ingest_ndb_data(file_path: str):
    """Ingest data from a .ndb file."""
    with open(file_path, 'r') as file:
        lines = file.readlines()
        for line in lines:
            if line[0] == '#':
                continue
            if line.strip() == '':
                continue
            put(line.strip())

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python ingest.py <path_to_ndb_file>")
    else:
        ingest_ndb_data(sys.argv[1])