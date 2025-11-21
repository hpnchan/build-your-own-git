import os
import sys
import hashlib
import zlib

def cmd_init():
    os.makedirs(".hpn", exist_ok=True)
    
    os.makedirs(".hpn/objects", exist_ok=True)
    
    os.makedirs(".hpn/refs/heads", exist_ok=True)
    
    with open(".hpn/HEAD", "w") as f:
        f.write("ref: refs/heads/master\n")
        
    print("Initialized empty HPN repository.") 
    
    #* blob <space> <size> <null> <content> hpn

def cmd_hash_object(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    
    #* \0
    header = f"blob {len(data)}".encode() + b'\0'
    full_data = header + data
    
    sha1 = hashlib.sha1(full_data).hexdigest()
    
    #* a1/b2c3d4...
    obj_dir = os.path.join(".hpn", "objects", sha1[:2])
    obj_file = os.path.join(obj_dir, sha1[2:])
    
    if not os.path.exists(obj_file):
        os.makedirs(obj_dir, exist_ok=True)
        
        compressed_data = zlib.compress(full_data)
        
        with open(obj_file, 'wb') as f:
            f.write(compressed_data)
    
    print(sha1)
    return sha1

def main():
    args = sys.argv[1:]
    
    if not args:
        print("Usage: python main.py [init|add <file>]")
        return
    
    command = args[0]
    
    if command == "init":
        cmd_init()
    elif command == "add":
        if len(args) < 2:
            print("Error: Missing file path")
            return
        file_path = args[1]
        cmd_hash_object(file_path)
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
