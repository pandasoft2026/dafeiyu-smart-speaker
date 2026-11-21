from elftools.elf.elffile import ELFFile
from elftools.elf.dynamic import DynamicSection
import os

base = r"D:\workbuddy\2026-11-19-10-59-25\tools\libs"

def dynsyms(path):
    syms = set()
    with open(path, "rb") as f:
        elf = ELFFile(f)
        for section in elf.iter_sections():
            if section.header["sh_type"] == "SHT_DYNSYM":
                for s in section.iter_symbols():
                    if s.name:
                        syms.add(s.name)
    return syms

def needed(path):
    req = []
    with open(path, "rb") as f:
        elf = ELFFile(f)
        for section in elf.iter_sections():
            if isinstance(section, DynamicSection):
                for tag in section.iter_tags():
                    if tag.entry.d_tag == "DT_NEEDED":
                        req.append(tag.needed)
    return req

vosk = os.path.join(base, "libvosk.so")
crt = os.path.join(base, "libcompiler_rt.so")

print("=== libvosk NEEDED ===")
for n in needed(vosk):
    print("  ", n)

vsyms = dynsyms(vosk)
atomic_needed = sorted(s for s in vsyms if s.startswith("__atomic") or s.startswith("__sync"))
print("\n=== libvosk 引用/定义的 atomic 符号 ===")
for s in atomic_needed:
    print("  ", s)

crtsyms = dynsyms(crt)
atomic_provided = sorted(s for s in crtsyms if s.startswith("__atomic") or s.startswith("__sync"))
print("\n=== libcompiler_rt 提供的 atomic 符号 ===")
for s in atomic_provided:
    print("  ", s)

print("\n=== 交集（vosk 需要的符号 compiler_rt 能否满足）===")
need_set = set(atomic_needed)
have_set = set(atomic_provided)
print("  vosk 需要但 compiler_rt 没有:", sorted(need_set - have_set))
