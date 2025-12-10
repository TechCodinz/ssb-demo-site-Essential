
import sys

def read_bytes(filepath, start, length):
    with open(filepath, 'r') as f:
        # read() reads characters (base64 is ascii, so 1 char = 1 byte approx)
        f.seek(start)
        data = f.read(length)
        print(data, end='')

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python read_bytes.py <file> <start_offset> <length>")
        sys.exit(1)
    
    read_bytes(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
