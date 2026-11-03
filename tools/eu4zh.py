"""EU4 中文模组（Chinese Language Mod for 1.37，工坊 2976470733）的文字编码。

EU4 只支持英、法、德、西四种语言；中文模组把中文写进 l_english，每个码位大于 U+00FF 的字符写成
"转义符＋低字节＋高字节"三个字符，三者都按 cp1252 字符存成 UTF-8。转义符起始为 0x10：
低字节落在 SPECIAL 里时转义符加 1、低字节加 14；高字节落在 SPECIAL 里时转义符加 2、高字节减 9。
U+00FF 以内的字符（ASCII、§、·）原样保留。

规则是 2026-11-02 从中文模组的 prov_names、text 两份本地化文件反推的，对这两份文件（共 82 万字节）
先解码再编码，逐字节一致。

    encode('巴黎')  ->  写进 l_english 的字符串
    decode(s)       ->  还原成中文
"""
SPECIAL={0x00,0x0A,0x0D,0x20,0x22,0x23,0x24,0x2F,0x3A,0x3B,0x3D,0x40,0x5B,0x5C,0x5D,0x5F,0x7B,0x7D,0x7E,0x80,0xA3,0xA4,0xA7,0xBD}
def b2c(x):
    try: return bytes([x]).decode('cp1252')
    except UnicodeDecodeError: return chr(x)
def c2b(c):
    try: return c.encode('cp1252')[0]
    except UnicodeEncodeError: return ord(c)
def encode(s):
    out=[]
    for ch in s:
        o=ord(ch)
        if o<=0xFF: out.append(ch); continue
        lo,hi=o&0xFF,o>>8; e=0x10
        if lo in SPECIAL: e+=1; lo+=14
        if hi in SPECIAL: e+=2; hi-=9
        out.append(chr(e)+b2c(lo)+b2c(hi))
    return ''.join(out)
def decode(s):
    out=[];i=0
    while i<len(s):
        e=ord(s[i])
        if 0x10<=e<=0x13 and i+2<len(s):
            lo,hi=c2b(s[i+1]),c2b(s[i+2])
            if e&1: lo-=14
            if e&2: hi+=9
            out.append(chr(hi<<8|lo)); i+=3
        else: out.append(s[i]); i+=1
    return ''.join(out)
if __name__=='__main__':
    import sys
    for fn in sys.argv[1:]:
        t=open(fn,encoding='utf-8-sig').read()
        d=decode(t); r=encode(d)
        print(fn.split('/')[-1],'roundtrip_equal=',r==t,'lines',t.count('\n'))
        print(' ', [l for l in d.splitlines() if l.startswith((' PROV1:',' PROV118:',' PROV183:',' PROV1816:'))])
