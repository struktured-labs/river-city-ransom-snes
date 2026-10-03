"""Assemble Project Nested's SPC700 sound engine sources (Myself086 syntax).

Project Nested (MIT) assembles Assembly/Project/Spc700/*.asm with a private,
unreleased assembler. This is a small independent assembler for exactly the
subset that Spc.asm, Spc.Memory.asm and Dmc.asm use: .def, .macro/.endm with
{n} arguments, .include, .db/.data8/.data16/.fill, .addr/.pushaddr/.pulladdr,
global labels, +name/-name near labels, and SPC700 instructions written with
'!' for absolute operands. Output is the raw image loaded at SPC $0400, the
same layout Project Nested's Sound__Init uploads (Spc_Code_Start..End).
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from tools.spc700_opcodes import OPCODES

ORIGIN = 0x400
SOURCES = ('Project/Spc700/Spc.asm', 'Project/Spc700/Spc.Memory.asm',
           'Project/Spc700/Dmc.asm')
REGS = {'a': 'A', 'x': 'X', 'y': 'Y', 'ya': 'YA', 'sp': 'SP', 'psw': 'PSW', 'c': 'C'}


class AsmError(Exception):
    pass


def find_file(root, rel):
    path = root
    for part in rel.split('/'):
        hits = [p for p in path.iterdir() if p.name.lower() == part.lower()]
        if len(hits) != 1:
            raise AsmError(f'cannot resolve include {rel}')
        path = hits[0]
    return path


def strip_comment(line):
    return line.split('//', 1)[0].rstrip()


def read_lines(root, rel, out):
    path = find_file(root, rel)
    for number, raw in enumerate(path.read_text(encoding='latin-1').splitlines(), 1):
        line = strip_comment(raw).strip()
        label = None
        m = re.match(r'^([A-Za-z_]\w*):\s*(.*)$', line)
        if m:
            label, line = m.group(1), m.group(2).strip()
        m = re.match(r'^\.include\s+"([^"]+)"$', line)
        if m:
            if label:
                out.append((f'{path.name}:{number}', label, ''))
            read_lines(root, m.group(1), out)
            continue
        if label or line:
            out.append((f'{path.name}:{number}', label, line))


def expand_macros(lines):
    macros, out, i = {}, [], 0
    while i < len(lines):
        where, label, text = lines[i]
        m = re.match(r'^\.macro\s+(\w+)', text)
        if m:
            body = []
            i += 1
            while not lines[i][2].startswith('.endm'):
                body.append(lines[i])
                i += 1
            macros[m.group(1).lower()] = body
            i += 1
            continue
        word = text.split(None, 1)
        if word and word[0].lower() in macros:
            args = [a.strip() for a in word[1].split(',')] if len(word) > 1 else []
            if label:
                out.append((where, label, ''))
            for bwhere, blabel, btext in macros[word[0].lower()]:
                for n, arg in enumerate(args):
                    btext = btext.replace('{%d}' % n, arg)
                    blabel = blabel and blabel.replace('{%d}' % n, arg)
                out.append((f'{where}<{bwhere}', blabel, btext))
        else:
            out.append((where, label, text))
        i += 1
    return out


TOKEN = re.compile(r'\s*(?:(0x[0-9a-fA-F]+)|([01]+)b(?!\w)|([0-9][0-9a-fA-F]*)h(?!\w)|(\d+)'
                   r'|([A-Za-z_.][\w.]*)|(>>|<<|[-+*/&|()^~]))')


class Assembler:
    def __init__(self):
        self.defs = {'Zero': 0}
        self.labels = {}
        self.near = {}

    def value(self, expr, at=None, strict=True):
        pos, out = 0, []
        expr = expr.strip()
        while pos < len(expr):
            m = TOKEN.match(expr, pos)
            if not m or m.end() == pos:
                raise AsmError(f'bad expression {expr!r}')
            pos = m.end()
            hexv, binv, hexh, dec, name, op = m.groups()
            if hexv: out.append(str(int(hexv, 16)))
            elif binv: out.append(str(int(binv, 2)))
            elif hexh: out.append(str(int(hexh, 16)))
            elif dec: out.append(dec)
            elif op: out.append('//' if op == '/' else op)
            else: out.append(str(self.symbol(name, at, strict)))
        try:
            return int(eval(' '.join(out), {'__builtins__': {}}))
        except SyntaxError:
            raise AsmError(f'bad expression {expr!r}')

    def symbol(self, name, at, strict):
        if name.startswith(('+', '-')):
            raise AsmError(name)
        for candidate in (name, name.lstrip('._=')):
            if candidate in self.defs:
                v = self.defs[candidate]
                return self.value(v, at, strict) if isinstance(v, str) else v
            if candidate in self.labels:
                return self.labels[candidate]
            if candidate in self.near and at is not None:
                # Unprefixed reuse of a local label name: most recent definition.
                before = [a for i, a in self.near[candidate] if i <= at]
                if before:
                    return before[-1]
        if strict:
            raise AsmError(f'undefined symbol {name}')
        return 0

    def near_label(self, ref, index):
        direction, name = ref[0], ref[1:]
        hits = self.near.get(name, [])
        if direction == '+':
            hits = [a for i, a in hits if i > index]
            if hits: return hits[0]
        else:
            hits = [a for i, a in hits if i <= index]
            if hits: return hits[-1]
        raise AsmError(f'unresolved near label {ref}')


def split_operands(text):
    parts, depth, cur = [], 0, ''
    for ch in text:
        if ch in '([': depth += 1
        if ch in ')]': depth -= 1
        if ch == ',' and depth == 0:
            parts.append(cur.strip()); cur = ''
        else:
            cur += ch
    if cur.strip(): parts.append(cur.strip())
    return parts


def classify(operand):
    o = operand.strip()
    low = o.lower().replace(' ', '')
    if low in REGS: return REGS[low], None
    if low in ('(x)', '(y)', '(x)+'): return low.upper(), None
    if o.startswith('#'): return 'imm', o[1:]
    m = re.match(r'^\[\s*!(.*)\+\s*[xX]\s*\]$', o)
    if m: return '[abs+X]', m.group(1)
    m = re.match(r'^\[(.*)\+\s*[xX]\s*\]$', o)
    if m: return '[dp+X]', m.group(1)
    m = re.match(r'^\[(.*)\]\s*\+\s*[yY]$', o)
    if m: return '[dp]+Y', m.group(1)
    absolute = o.startswith('!')
    body = o[1:] if absolute else o
    m = re.match(r'^(.*)\+\s*([xXyY])$', body)
    base = 'abs' if absolute else 'dp'
    if m: return f'{base}+{m.group(2).upper()}', m.group(1)
    return base, body


def parse_instruction(text):
    word = text.split(None, 1)
    mn = word[0].upper()
    ops = split_operands(word[1]) if len(word) > 1 else []
    if mn in ('BBS', 'BBC', 'SET1', 'CLR1') and len(ops) >= 2:
        kinds = [classify(ops[0]), ('bit', ops[1])] + [classify(o) for o in ops[2:]]
    else:
        kinds = [classify(o) for o in ops]
    return mn, kinds


def lookup(mn, kinds, asm, index):
    names = []
    for k, e in kinds:
        if k == 'bit':
            names.append('bit%d' % asm.value(e))
        else:
            names.append(k)
    candidates = [tuple(names)]
    if names and names[-1] == 'dp':
        candidates.append(tuple(names[:-1]) + ('rel',))
    for c in candidates:
        if (mn, c) in OPCODES:
            return OPCODES[(mn, c)], c
    raise AsmError(f'no encoding for {mn} {names}')


def instruction_size(kinds_key):
    size = 1
    for k in kinds_key:
        if k.startswith(('abs', '[abs')) or k in ('membit', '/membit'): size += 2
        elif k in ('dp', 'imm', 'rel', 'dp+X', 'dp+Y', '[dp+X]', '[dp]+Y', 'upage'): size += 1
    return size


def encode(opcode, key, kinds, asm, pc, index, strict):
    size = instruction_size(key)
    def val(e, kind):
        e = e.strip()
        if kind == 'rel' and e[:1] in '+-' and re.match(r'^[+-][A-Za-z_]', e):
            target = asm.near_label(e, index) if strict else pc
        else:
            target = asm.value(e, index, strict)
        if kind == 'rel':
            delta = target - (pc + size)
            if strict and not -128 <= delta <= 127:
                raise AsmError('branch out of range')
            return [delta & 0xFF]
        if kind.startswith(('abs', '[abs')):
            if strict and not 0 <= target <= 0xFFFF: raise AsmError('absolute range')
            return [target & 0xFF, (target >> 8) & 0xFF]
        if kind == 'imm':
            return [target & 0xFF]
        if strict and not 0 <= target <= 0xFF:
            raise AsmError(f'direct page operand {e} = {target:#x}')
        return [target & 0xFF]
    pairs = [(kk, e) for (k, e), kk in zip(kinds, key) if e is not None and k != 'bit']
    if key == ('dp', 'dp'):
        return [opcode] + val(pairs[1][1], 'dp') + val(pairs[0][1], 'dp')
    if key == ('dp', 'imm'):
        return [opcode] + val(pairs[1][1], 'imm') + val(pairs[0][1], 'dp')
    out = [opcode]
    for k, e in pairs:
        out += val(e, k)
    if len(out) != size:
        raise AsmError('size mismatch')
    return out


def assemble(root, sources=SOURCES):
    lines = []
    for rel in sources:
        read_lines(root, rel, lines)
    lines = expand_macros(lines)
    asm = Assembler()
    image = {}
    for strict in (False, True):
        pc, stack, image = ORIGIN, [], {}
        if strict:
            pass
        else:
            asm.near = {}
        for index, (where, label, text) in enumerate(lines):
            try:
                if label:
                    if not strict:
                        if label.startswith('b_') or label.endswith('__') or label.startswith('b_loop'):
                            asm.near.setdefault(label, []).append((index, pc))
                        elif label in asm.labels and asm.labels[label] != pc and label not in asm.near:
                            raise AsmError(f'duplicate label {label}')
                        else:
                            asm.labels[label] = pc
                    elif not (label.startswith('b_') or label.endswith('__')):
                        if asm.labels[label] != pc:
                            raise AsmError(f'label moved {label}')
                if not text:
                    continue
                if text.startswith('.'):
                    word = text.split(None, 1)
                    d, rest = word[0].lower(), (word[1] if len(word) > 1 else '')
                    if d == '.def':
                        name, expr = rest.split(None, 1)
                        try:
                            asm.defs[name] = asm.value(expr, index, True)
                        except AsmError:
                            if re.search(r'\b%s\b' % re.escape(name), expr):
                                raise
                            asm.defs[name] = expr
                    elif d in ('.db', '.data8', '.data16', '.dw'):
                        width = 2 if d in ('.data16', '.dw') else 1
                        for item in re.split(r'[\s,]+', rest.strip()):
                            if not item: continue
                            v = asm.value(item, index, strict)
                            for b in range(width):
                                image[pc] = (v >> (8 * b)) & 0xFF; pc += 1
                    elif d == '.fill':
                        args = [a.strip() for a in rest.split(',')]
                        count = asm.value(args[0], index, True)
                        fill = asm.value(args[1], index, True) if len(args) > 1 else 0
                        for _ in range(count):
                            image[pc] = fill & 0xFF; pc += 1
                    elif d == '.pushaddr':
                        stack.append(pc)
                    elif d == '.pulladdr':
                        pc = stack.pop()
                    elif d == '.addr':
                        pc = asm.value(rest, index, strict) if strict else asm.value(rest, index, False)
                    else:
                        raise AsmError(f'unsupported directive {d}')
                    continue
                mn, kinds = parse_instruction(text)
                opcode, key = lookup(mn, kinds, asm, index)
                code = encode(opcode, key, kinds, asm, pc, index, strict)
                for b in code:
                    image[pc] = b; pc += 1
            except AsmError as e:
                raise AsmError(f'{where}: {text!r}: {e}')
        end = pc
        # Includes.asm places Spc_HeapStart immediately after Dmc.asm.
        asm.labels['Spc_HeapStart'] = pc
    lo, hi = min(image), max(image)
    if lo != ORIGIN:
        raise AsmError('image does not start at $0400')
    data = bytes(image.get(a, 0) for a in range(ORIGIN, max(hi + 1, end)))
    return data, asm.labels


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path('.deps/project-nested/Assembly'))
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--labels', type=Path)
    a = p.parse_args()
    data, labels = assemble(a.root)
    a.out.write_bytes(data)
    if a.labels:
        a.labels.write_text(json.dumps({k: v for k, v in sorted(labels.items(), key=lambda kv: kv[1])}, indent=1) + '\n')
    print(json.dumps(dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), end=hex(ORIGIN + len(data)))))


if __name__ == '__main__':
    main()
