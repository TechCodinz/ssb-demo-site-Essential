
import os

MAX_CHUNK_SIZE = 900
INPUT_FILE = 'ssb-bundle.b64'
OUTPUT_SCRIPT = 'deployment/upload_commands.sh'

def generate_script():
    with open(INPUT_FILE, 'r') as f:
        content = f.read()
    
    total_len = len(content)
    with open(OUTPUT_SCRIPT, 'w', newline='\n') as out:
        for i in range(0, total_len, MAX_CHUNK_SIZE):
            chunk = content[i:i+MAX_CHUNK_SIZE]
            # Verify no weird chars (base64 is safe)
            # Operator: > for first chunk, >> for rest
            operator = '>' if i == 0 else '>>'
            cmd = f'printf "%s" "{chunk}" {operator} /root/ssb-bundle.b64\n'
            out.write(cmd)
            
    print(f"Generated {total_len // MAX_CHUNK_SIZE + 1} commands in {OUTPUT_SCRIPT}")

if __name__ == "__main__":
    generate_script()
