import os
import sys
import hashlib
import zlib
import time
# import struct

def cmd_init():
    os.makedirs(".hpn", exist_ok=True)
    
    os.makedirs(".hpn/objects", exist_ok=True)
    
    os.makedirs(".hpn/refs/heads", exist_ok=True)
    
    with open(".hpn/HEAD", "w") as f:
        f.write("ref: refs/heads/master\n")
        
    print("Initialized empty HPN repository.") 
    
    #* blob <space> <size> <null> <content> hpn

def hash_object(data, obj_type, write=True):
    header = f"{obj_type} {len(data)}".encode() + b'\0'
    full_data = header + data
    sha1 = hashlib.sha1(full_data).hexdigest()
    if write:
        path = os.path.join(".hpn", "objects", sha1[:2], sha1[2:])
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(zlib.compress(full_data))
    return sha1

def write_tree(directory="."):
    entries = []
    
    with os.scandir(directory) as it:
        for entry in it:
            if entry.name.startswith(".") or entry.name == "__pycache__":
                continue
            
            if entry.is_file(follow_symlinks=False):
                with open(entry.path, 'rb') as f:
                    data = f.read()
                sha1 = hash_object(data, "blob")
                #! Mode 100644 là file thường
                entries.append((entry.name, sha1, "100644"))
            
            elif entry.is_dir(follow_symlinks=False):
                sha1 = write_tree(entry.path)
                #! Mode 40000 là directory
                entries.append((entry.name, sha1, "40000"))
    
    entries.sort(key=lambda x: x[0])
    
    tree_content = b""
    for name, sha1, mode in entries:
        #* Format chuẩn: "mode name\0sha1_binary"
        #! sha1 trong Trê được lưu dạng Binary (20 bytes) chứ KHÔNG PHẢI hex string
        sha1_bytes = bytes.fromhex(sha1)
        tree_content += f"{mode} {name}".encode() + b'\0' + sha1_bytes
    
    return hash_object(tree_content, "tree")

def get_current_head():
    if os.path.exists(".hpn/HEAD"):
        with open(".hpn/HEAD", "r") as f:
            ref = f.read().strip().split(": ")[1]  #* refs/heads/master
        
        ref_path = os.path.join(".hpn", ref)
        if os.path.exists(ref_path):
            with open(ref_path, "r") as f:
                return f.read().strip()
    
    return None

def cmd_commit(message):
    tree_sha1 = write_tree()
    
    parent = get_current_head()
    
    timestamp = int(time.time())
    timezone = "#0700"
    author = "HPN User <user@hpn.example.com>"
    
    lines = [f"tree {tree_sha1}"]
    if parent:
        lines.append(f"parent {parent}")
    
    lines.append(f"author {author} {timestamp} {timezone}")
    lines.append(f"committer {author} {timestamp} {timezone}")
    lines.append("")  #* Dòng trống để ngăn cách header - message
    lines.append(message)
    lines.append("")
    
    data = "\n".join(lines).encode()
    
    commit_sha1 = hash_object(data, "commit")
    
    with open(".hpn/HEAD", "r") as f:
        ref = f.read().strip().split(": ")[1]
    
    ref_path = os.path.join(".hpn", ref)
    
    with open(ref_path, "w") as f:
        f.write(commit_sha1)
    
    print(f"[{ref.split('/')[-1]} {commit_sha1[:7]}] {message}")

def cmd_log():
    commit_sha1 = get_current_head()
    
    while commit_sha1:
        path = os.path.join(".hpn", "objects", commit_sha1[:2], commit_sha1[2:])
        with open(path, "rb") as f:
            raw = zlib.decompress(f.read())
            
            header_end = raw.find(b'\0')
            content = raw[header_end+1:].decode()
            
            lines = content.split("\n")
            print(f"\033[33mcommit {commit_sha1}\033[0m")
            parent = None
            
            for line in lines:
                if line.startswith("parent"):
                    parent = line.split()[1]
                elif line.startswith("author"):
                    print(f"Author: {line[7:]}")
                elif line.startswith("date"):
                    pass
                elif not line:
                    break
            
            msg_index = lines.index("") + 1
            print(f"\n  {lines[msg_index]}\n")
            
            commit_sha1 = parent

def main():
    args = sys.argv[1:]
    
    if not args:
        print("Usage: hpn [init|add|commit|log <file>]")
        return
    
    command = args[0]
    
    if command == "init":
        cmd_init()
    elif command == "add":
        if len(args) < 2:
            print("Error: Missing file path")
            return
        hash_object(open(args[1], 'rb').read(), "blob")
        print(f"Added {args[1]}")
    elif command == "commit":
        if len(args) < 2:
            print("Message required: hpn commit 'message'")
            return 
        cmd_commit(args[1])
    elif command == "log":
        cmd_log()
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()


#*qoweihoiqwehoiqwehowqehqwoiehqwoieho