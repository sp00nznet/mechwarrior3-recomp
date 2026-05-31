#!/usr/bin/env python3
"""
MechWarrior 3 Static Recompilation Pipeline (Phase 1 codegen).

Reuses the shared pcrecomp lifter, but seeds the function-entry list from
config/functions.json (IDA Pro discovery, which follows vtables) instead of a
call-graph/prologue heuristic. This captures the ~950 virtual methods up-front
that a call-graph sweep would miss (cf. the Crimson Skies vtable gap).

Usage: python run_pipeline.py [analysis/HSBR.exe] [src/recomp/gen]
"""
import sys, os, json, time, struct

_here = os.path.dirname(os.path.abspath(__file__))
_pc = os.path.join(_here, 'tools', 'pcrecomp', 'tools')
sys.path.insert(0, os.path.join(_pc, 'pe'))
sys.path.insert(0, os.path.join(_pc, 'lift'))

from pe_analyze import analyze_pe, build_iat_map
from lift32 import Lifter
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM

COND_JUMPS = {'je','jne','jz','jnz','ja','jae','jb','jbe','jg','jge','jl','jle',
              'js','jns','jo','jno','jp','jnp','jcxz','jecxz'}


class LinearInstruction:
    __slots__ = ['address','size','mnemonic','op_str','bytes','operands',
                 'is_call','is_ret','is_cond_jump','is_uncond_jump','is_jump']
    def __init__(self, insn):
        self.address=insn.address; self.size=insn.size
        self.mnemonic=insn.mnemonic; self.op_str=insn.op_str
        self.bytes=bytes(insn.bytes)
        self.operands=list(insn.operands) if insn.operands else []
        self.is_call=insn.mnemonic=='call'
        self.is_ret=insn.mnemonic in ('ret','retn','retf')
        self.is_cond_jump=insn.mnemonic in COND_JUMPS
        self.is_uncond_jump=insn.mnemonic=='jmp'
        self.is_jump=self.is_cond_jump or self.is_uncond_jump
    @property
    def end_address(self): return self.address+self.size
    def get_branch_target(self):
        if self.operands and self.operands[0].type==X86_OP_IMM:
            return self.operands[0].imm & 0xFFFFFFFF
        return None


def linear_disassemble_function(md, code_data, code_start, func_start, func_end):
    offset=func_start-code_start; size=func_end-func_start
    if offset<0 or offset+size>len(code_data): return [], set()
    raw=code_data[offset:offset+size]; instructions=[]; leaders={func_start}
    for insn in md.disasm(raw, func_start):
        li=LinearInstruction(insn); instructions.append(li)
        if li.is_jump:
            t=li.get_branch_target()
            if t and func_start<=t<func_end: leaders.add(t)
            leaders.add(li.end_address)
        if li.mnemonic=='int3': break
    return instructions, leaders


def lift_function_linear(lifter, name, instructions, leaders):
    lines=[f'void {name}(void) {{',
           '    uint32_t ebp = 0;','    double _st[8] = {0};','    int _fp_top = 0;',
           '    int _fpu_cmp = 0;','    uint32_t _cf = 0;','    int _df = 1;',
           '    uint16_t _fpu_cw = 0x037F;','']
    lifter._flag_state=None
    for insn in instructions:
        if insn.address in leaders: lines.append(f'L_{insn.address:08X}:')
        for line in lifter.lift_instruction(insn): lines.append(f'    {line}')
    if instructions and not instructions[-1].is_ret:
        lines.append('    return; /* end of function */')
    lines.append('}')
    return '\n'.join(lines)


def write_chunk(out, idx, funcs):
    with open(os.path.join(out, f'recomp_{idx:04d}.c'),'w') as f:
        f.write('/* MechWarrior 3 Recompilation - Auto-generated - DO NOT EDIT */\n')
        f.write(f'/* File {idx}: {len(funcs)} functions */\n\n')
        f.write('#define RECOMP_GENERATED_CODE\n#include "recomp_types.h"\n')
        f.write('#include "recomp_funcs.h"\n#include <math.h>\n#include <string.h>\n\n')
        for code,_,_ in funcs: f.write(code+'\n\n')


def main():
    exe = sys.argv[1] if len(sys.argv)>1 else os.path.join(_here,'analysis','HSBR.exe')
    out = sys.argv[2] if len(sys.argv)>2 else os.path.join(_here,'src','recomp','gen')
    split = int(sys.argv[3]) if len(sys.argv)>3 else 500
    os.makedirs(out, exist_ok=True)

    print('=== MechWarrior 3 Static Recompilation (Phase 1) ===', flush=True)
    info=analyze_pe(exe); iat=build_iat_map(info)
    print(f'[*] base=0x{info.image_base:08X} code=0x{info.code_start:08X}-0x{info.code_end:08X} IAT={len(iat)}')
    pe_data=open(exe,'rb').read()
    text=[s for s in info.sections if s.name=='.text'][0]
    code_data=pe_data[text.raw_offset: text.raw_offset+min(text.virtual_size,text.raw_size)]
    cs, ce = info.code_start, info.code_end

    # Step 2: seed entries from IDA's functions.json (includes vtable virtuals)
    fj=json.load(open(os.path.join(_here,'config','functions.json'),encoding='utf-8'))
    entries=sorted({(e.get('address_int') or int(e['address'],16)) for e in fj
                    if cs <= (e.get('address_int') or int(e['address'],16)) < ce})
    print(f'[*] seeded {len(entries)} entries from IDA functions.json')

    md=Cs(CS_ARCH_X86, CS_MODE_32); md.detail=True
    lifter=Lifter(iat_map=iat)
    all_entries=[]; stats=[]; errors=0; idx=0; chunk=[]; t0=time.time()
    for i,addr in enumerate(entries):
        end=min(entries[i+1], addr+65536) if i+1<len(entries) else min(ce, addr+65536)
        if end-addr<2: continue
        name=f'sub_{addr:08X}'
        try:
            insns,leaders=linear_disassemble_function(md, code_data, cs, addr, end)
            if not insns: continue
            trimmed=[]; seen_ret=False
            for ins in insns:
                if ins.mnemonic=='int3': break
                if seen_ret:
                    if ins.address not in leaders: continue
                    seen_ret=False
                trimmed.append(ins)
                if ins.is_ret: seen_ret=True
            if not trimmed: continue
            code=lift_function_linear(lifter, name, trimmed, leaders)
            chunk.append((code,addr,name)); all_entries.append((addr,name))
            stats.append({'address':f'0x{addr:08X}','address_int':addr,'name':name,
                          'num_instructions':len(trimmed)})
        except Exception as e:
            chunk.append((f'/* ERROR {name}: {e} */\nvoid {name}(void) {{}}\n',addr,name))
            all_entries.append((addr,name)); errors+=1
        if len(chunk)>=split:
            write_chunk(out, idx, chunk); idx+=1; chunk=[]
            print(f'[*]   {len(all_entries)}/{len(entries)} ({errors} err)', flush=True)
    if chunk: write_chunk(out, idx, chunk); idx+=1

    with open(os.path.join(out,'recomp_funcs.h'),'w') as f:
        f.write('/* MechWarrior 3 Recompilation - Auto-generated */\n#pragma once\n#include <stdint.h>\n\n')
        for a,n in all_entries: f.write(f'void {n}(void);  /* 0x{a:08X} */\n')
    with open(os.path.join(out,'recomp_dispatch.c'),'w') as f:
        f.write('/* MechWarrior 3 Recompilation - Auto-generated */\n#include "recomp_types.h"\n#include "recomp_funcs.h"\n\n')
        f.write('const recomp_dispatch_entry_t recomp_dispatch_table[] = {\n')
        for a,n in sorted(all_entries): f.write(f'    {{ 0x{a:08X}u, {n} }},\n')
        f.write('};\n\n'+f'const uint32_t recomp_dispatch_count = {len(all_entries)};\n')

    total_lines=total_bytes=0
    for fn in os.listdir(out):
        fp=os.path.join(out,fn)
        if os.path.isfile(fp):
            total_bytes+=os.path.getsize(fp)
            total_lines+=sum(1 for _ in open(fp, encoding='utf-8', errors='replace'))
    json.dump({'functions':len(all_entries),'errors':errors,'files':idx,
               'lines':total_lines,'bytes':total_bytes},
              open(os.path.join(_here,'analysis','phase1_codegen.json'),'w'), indent=1)
    print('='*56)
    print(f'  functions: {len(all_entries):,}  errors: {errors}  files: {idx}')
    print(f'  lines of C: {total_lines:,}  size: {total_bytes/1048576:.1f} MB  time: {time.time()-t0:.1f}s')
    print('='*56)


if __name__=='__main__':
    main()
