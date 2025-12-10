
import sys

def print_chunk(filepath, start, end):
    with open(filepath, 'r') as f:
        lines = f.readlines()
        # 1-based index to 0-based
        chunk = lines[start-1:end]
        for line in chunk:
            print(line, end='')

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python print_chunk.py <file> <start> <end>")
        sys.exit(1)
    
    print_chunk(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
