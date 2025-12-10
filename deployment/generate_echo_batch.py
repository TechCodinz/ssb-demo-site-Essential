
import sys

def generate_echo_batch(filepath, start_line, num_lines, target_file):
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            start_index = start_line - 1
            selected = lines[start_index : start_index + num_lines]
            for line in selected:
                clean_line = line.strip()
                print(f'echo "{clean_line}" >> {target_file}')
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python generate_echo_batch.py <file> <start_line> <num_lines> <target_file>")
        sys.exit(1)
    
    generate_echo_batch(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
