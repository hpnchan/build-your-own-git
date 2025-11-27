import os
import sys
import hashlib
import zlib
import time
# import struct

HPN_DIR = ".hpn"
OBJECTS_DIR = os.path.join(HPN_DIR, "objects")
HEAD_FILE = os.path.join(HPN_DIR, "HEAD")

def read_object(sha1):
    path = os.path.join(OBJECTS_DIR, sha1[:2], sha1[2:])
    if not os.path.exists(path):
        return None, None
    
    with open(path, "rb") as f:
        try:
            raw = zlib.decompress(f.read())
        except zlib.error:
            return None, None
    
    spc_idx = raw.find(b' ')
    nul_idx = raw.find(b'\0', spc_idx)
    
    obj_type = raw[:spc_idx].decode()
    content = raw[nul_idx+1:]
    
    return obj_type, content

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
            if entry.name.startswith(".") or entry.name == "__pycache__" or entry.name == "main.py":
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

def get_current_head_info():
    if not os.path.exists(HEAD_FILE):
        return None, None
        
    with open(HEAD_FILE, "r") as f:
        content = f.read().strip()
    
    if content.startswith("ref: "):
        ref = content.split(": ")[1]
        ref_path = os.path.join(HPN_DIR, ref)
        if os.path.exists(ref_path):
            with open(ref_path, "r") as f:
                return ref, f.read().strip()
        return ref, None
    else:
        return None, content

def cmd_commit(message):
    tree_sha1 = write_tree()
    
    parent = get_current_head_info()
    
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
    _, commit_sha1 = get_current_head_info()
    while commit_sha1:
        obj_type, content = read_object(commit_sha1) #* Dùng hàm read_object
        if obj_type != "commit": break
        
        lines = content.decode().split("\n")
        print(f"\033[33mcommit {commit_sha1}\033[0m")
        parent = None
        for line in lines:
            if line.startswith("parent"): parent = line.split()[1]
            elif line == "": 
                print(f"\n  {lines[lines.index('')+1]}\n")
                break
        commit_sha1 = parent
        

def restore_tree(tree_sha1, base_path="."):
    obj_type, content = read_object(tree_sha1)
    if obj_type != "tree":
        return

    i = 0
    while i < len(content):
        #* Format: [mode] [space] [name] [\0] [sha1_bytes_20]
        
        nul_pos = content.find(b'\0', i)
        
        header = content[i:nul_pos].decode()
        #! split(" ", 1)
        mode, name = header.split(" ", 1)
        
        sha1_bytes = content[nul_pos+1 : nul_pos+21]
        sha1 = sha1_bytes.hex()
        
        i = nul_pos + 21
        
        current_path = os.path.join(base_path, name)
        
        child_type, child_content = read_object(sha1)
        
        if child_type == "blob":
            #* Force Checkout
            with open(current_path, "wb") as f:
                f.write(child_content)
                print(f"Restored file: {current_path}")
        elif child_type == "tree":
            if not os.path.exists(current_path):
                os.makedirs(current_path)
            restore_tree(sha1, current_path)

#* -b <tên nhánh>: tạo nhánh mới từ commit hiện tại
#* <tên nhánh>: chuyển sang nhánh đã có
#* <commit_hash>: quay về quá khứ 

def get_tree_from_commit(commit_sha1):
    obj_type, content = read_object(commit_sha1)
    if obj_type != "commit":
        return None
    #* tree <tree_sha1>
    return content.decode().split("\n")[0].split()[1]

def cmd_checkout(args):
    if not args:
        print(f"Usage: checkout [-b] <branch/commit")
        return
    
    target = args[0]
    is_new_branch = False
    
    if target == "-b":
        if len(args) < 2:
            print("Error: Missing branch name")
            return
        is_new_branch = True
        target = args[1]
    
    _, current_commit_sha1 = get_current_head_info()
    
    if is_new_branch:
        if not current_commit_sha1:
            print("Cannot create branch from empty history.")
            return
        
        new_ref_path = os.path.join(HPN_DIR, "refs", "heads", target)
        with open(new_ref_path, "w") as f:
            f.write(current_commit_sha1)
        
        with open(HEAD_FILE, "w") as f:
            f.write(f"ref: refs/heads/{target}]\n")
        print(f"Switched to a new branch '{target}'")
    else:
        branch_path = os.path.join(HPN_DIR, "refs", "heads", target)
        
        #* Case 1: target - branch
        if os.path.exists(branch_path):
            with open(branch_path, "r") as f:
                target_commit = f.read().strip()
            
            tree_sha1 = get_tree_from_commit(target_commit)
            restore_tree(tree_sha1)
            
            with open(HEAD_FILE, "w") as f:
                f.write(f"ref: refs/heads/{target}\n")
            print(f"Switched to branch '{target}'")
        
        #* Case 2: target - commit hash
        else:
            obj_type, _ = read_object(target)
            if obj_type == "commit":
                tree_sha1 = get_tree_from_commit(target)
                restore_tree(tree_sha1)
                
                with open(HEAD_FILE, "w") as f:
                    f.write(target)
                print(f"Note: checking out '{target}'. You are in 'detached HEAD' state.")
            else:
                print(f"Error: '{target}' is not a valid branch or commit.")

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
    elif command == "checkout":
        if len(args) < 2:
            return
        cmd_checkout(args[1:])
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()


#*qoweihoiqwehoiqwehowqehqwoiehqwoieho