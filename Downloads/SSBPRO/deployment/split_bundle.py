
import os

def split_file():
    base_dir = r"c:\Users\User\Downloads\SSBPRO"
    file_path = os.path.join(base_dir, "ssb-bundle.b64")
    
    with open(file_path, "r") as f:
        content = f.read()
        
    chunk_size = 10000  # 10KB
    parts = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
    
    for idx, part in enumerate(parts):
        part_path = os.path.join(base_dir, f"ssb-bundle.b64.part{idx+1}")
        with open(part_path, "w") as f:
            f.write(part)
            
    print(f"Split into {len(parts)} parts")

if __name__ == "__main__":
    split_file()
