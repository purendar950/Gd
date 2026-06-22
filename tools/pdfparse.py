"""Stdlib-only PDF text + layout + fill-color extractor.

Designed for the scanned-but-vector-text SSC GD PDFs. Text is drawn with
Identity-H composite fonts (2-byte codes) that carry ToUnicode CMaps, so we can
recover real Unicode. We also track non-stroking color + rectangle fills to
detect green/yellow answer highlights.
"""
import sys, re, zlib

# ----------------------------- object store -----------------------------

class PDF:
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.data = f.read()
        self.objs = {}        # objnum -> (raw_bytes_of_object_body)
        self.streams = {}     # objnum -> raw stream bytes (compressed)
        self._parse_indirect_objects()
        self._parse_objstms()

    # --- low level dict parsing helpers (regex/byte based, tolerant) ---
    def _parse_indirect_objects(self):
        # match "num gen obj" ... "endobj"
        for m in re.finditer(rb'(\d+)\s+(\d+)\s+obj\b', self.data):
            num = int(m.group(1))
            body_start = m.end()
            endobj = self.data.find(b'endobj', body_start)
            if endobj == -1:
                endobj = len(self.data)
            body = self.data[body_start:endobj]
            self.objs[num] = body
            # stream?
            sm = re.search(rb'stream\r?\n', body)
            if sm:
                s = sm.end()
                e = body.find(b'endstream', s)
                if e != -1:
                    self.streams[num] = body[s:e]

    def _parse_objstms(self):
        for num, body in list(self.objs.items()):
            if b'/ObjStm' not in body:
                continue
            raw = self.streams.get(num)
            if raw is None:
                continue
            try:
                dec = zlib.decompress(raw)
            except Exception:
                continue
            nm = re.search(rb'/N\s+(\d+)', body)
            fm = re.search(rb'/First\s+(\d+)', body)
            if not nm or not fm:
                continue
            N = int(nm.group(1)); first = int(fm.group(1))
            header = dec[:first].split()
            nums = []
            for i in range(0, min(len(header), 2*N), 2):
                try:
                    onum = int(header[i]); off = int(header[i+1])
                    nums.append((onum, off))
                except Exception:
                    pass
            for i, (onum, off) in enumerate(nums):
                start = first + off
                end = first + nums[i+1][1] if i+1 < len(nums) else len(dec)
                if onum not in self.objs:
                    self.objs[onum] = dec[start:end]

    # --- accessors ---
    def get_stream(self, num):
        raw = self.streams.get(num)
        if raw is None:
            return None
        try:
            return zlib.decompress(raw)
        except Exception:
            return raw

    def resolve(self, token):
        """token like b'12 0 R' -> object body bytes; or returns token."""
        m = re.match(rb'\s*(\d+)\s+(\d+)\s+R', token)
        if m:
            return self.objs.get(int(m.group(1)), b'')
        return token


# ----------------------------- dict helpers -----------------------------

def find_dict_value(body, key):
    """Return raw bytes after /key in a dict body (best-effort, one token/group)."""
    m = re.search(re.escape(key) + rb'\s*', body)
    if not m:
        return None
    i = m.end()
    # skip whitespace
    while i < len(body) and body[i:i+1].isspace():
        i += 1
    rest = body[i:]
    # indirect ref
    rm = re.match(rb'(\d+)\s+(\d+)\s+R', rest)
    if rm:
        return rm.group(0)
    if rest[:1] == b'[':
        depth = 0; j = 0
        for j in range(len(rest)):
            c = rest[j:j+1]
            if c == b'[': depth += 1
            elif c == b']':
                depth -= 1
                if depth == 0:
                    return rest[:j+1]
        return rest
    if rest[:2] == b'<<':
        depth = 0; j = 0
        while j < len(rest):
            if rest[j:j+2] == b'<<':
                depth += 1; j += 2; continue
            if rest[j:j+2] == b'>>':
                depth -= 1; j += 2
                if depth == 0:
                    return rest[:j]
                continue
            j += 1
        return rest
    if rest[:1] == b'/':
        nm = re.match(rb'/[^\s/<>\[\]()]+', rest)
        return nm.group(0)
    nm = re.match(rb'[-+0-9.]+', rest)
    if nm:
        return nm.group(0)
    return None


# ----------------------------- ToUnicode CMap -----------------------------

def parse_tounicode(stream_bytes):
    """Return dict: int code -> unicode str."""
    cmap = {}
    if not stream_bytes:
        return cmap
    s = stream_bytes
    # bfchar
    for block in re.findall(rb'beginbfchar(.*?)endbfchar', s, re.S):
        for m in re.finditer(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', block):
            code = int(m.group(1), 16)
            cmap[code] = _hex_to_str(m.group(2))
    # bfrange
    for block in re.findall(rb'beginbfrange(.*?)endbfrange', s, re.S):
        # form1: <lo> <hi> <dststart>
        for m in re.finditer(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', block):
            lo = int(m.group(1), 16); hi = int(m.group(2), 16)
            dst = int(m.group(3), 16)
            for k, code in enumerate(range(lo, hi+1)):
                cmap[code] = chr(dst + k)
        # form2: <lo> <hi> [ <d1> <d2> ... ]
        for m in re.finditer(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[(.*?)\]', block, re.S):
            lo = int(m.group(1), 16); hi = int(m.group(2), 16)
            dsts = re.findall(rb'<([0-9A-Fa-f]+)>', m.group(3))
            for k, code in enumerate(range(lo, hi+1)):
                if k < len(dsts):
                    cmap[code] = _hex_to_str(dsts[k])
    return cmap

def _hex_to_str(h):
    h = h.decode('latin1')
    if len(h) % 4 != 0:
        # pad to 4
        if len(h) % 2 != 0:
            h = '0' + h
        # treat as 2-byte units if multiple of 4 else single
    out = []
    if len(h) % 4 == 0:
        for i in range(0, len(h), 4):
            out.append(chr(int(h[i:i+4], 16)))
    else:
        for i in range(0, len(h), 2):
            out.append(chr(int(h[i:i+2], 16)))
    return ''.join(out)


if __name__ == '__main__':
    pdf = PDF(sys.argv[1])
    pages = [n for n,b in pdf.objs.items() if b'/Type' in b and b'/Page' in b and b'/Pages' not in b]
    print('total objects:', len(pdf.objs))
    print('page objects:', len(pages))
    # show a font ToUnicode count
    tus = [n for n,b in pdf.objs.items() if b'/ToUnicode' in b]
    print('objects referencing /ToUnicode:', len(tus))
