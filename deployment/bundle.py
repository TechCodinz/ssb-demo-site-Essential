
import os
import shutil
import tarfile
import base64
import sys

def ignore_patterns(path, names):
    return [n for n in names if n == '__pycache__' or n.endswith('.pyc') or n == 'venv' or n == '.git' or n == 'logs']

def bundle_app():
    base_dir = r"c:\Users\User\Downloads\SSBPRO"
    dist_dir = os.path.join(base_dir, "dist_bundle")
    
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    os.makedirs(dist_dir)
    
    # Copy API
    shutil.copytree(os.path.join(base_dir, "saas_platform", "api"), os.path.join(dist_dir, "api"), ignore=ignore_patterns)

    # Copy Cloud Engine
    cloud_eng_src = os.path.join(base_dir, "saas_platform", "cloud_engine")
    if os.path.exists(cloud_eng_src):
        shutil.copytree(cloud_eng_src, os.path.join(dist_dir, "cloud_engine"), ignore=ignore_patterns)
        
    # Copy Telegram Bot
    shutil.copytree(os.path.join(base_dir, "telegram_bot"), os.path.join(dist_dir, "telegram_bot"), ignore=ignore_patterns)
    
    # Copy setup scripts as well
    shutil.copy(os.path.join(base_dir, "deployment", "deploy-app.sh"), os.path.join(dist_dir, "deploy-app.sh"))
    
    # Create services/middleware packages if missing
    for d in ["services", "middleware"]:
        path = os.path.join(dist_dir, "api", d)
        if not os.path.exists(path): os.makedirs(path)
        if not os.path.exists(os.path.join(path, "__init__.py")):
            with open(os.path.join(path, "__init__.py"), 'w') as f: f.write("")

    # Tar it
    tar_path = os.path.join(base_dir, "ssb-bundle.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(dist_dir, arcname=".")
        
    # Read and encode
    with open(tar_path, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode('utf-8')
        
    # Write to file with wrapping
    with open(os.path.join(base_dir, "ssb-bundle.b64"), "w") as f:
        for i in range(0, len(b64), 76):
            f.write(b64[i:i+76] + "\n")
            
    print(f"Bundle size: {len(data)} bytes")
    print(f"Written to ssb-bundle.b64")

if __name__ == "__main__":
    bundle_app()
