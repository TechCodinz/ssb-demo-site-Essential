
import sys

def read_lines(filepath, start_line, num_lines):
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            # 0-indexed slicing, but user passes 1-indexed start
            start_index = start_line - 1
            selected = lines[start_index : start_index + num_lines]
            for line in selected:
                print(line, end='')
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python read_lines.py <file> <start_line> <num_lines>")
        sys.exit(1)
    
    read_lines(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
