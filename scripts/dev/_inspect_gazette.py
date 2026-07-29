import pdfplumber
import re
from pathlib import Path

pdf_path = Path(r'D:\MFUMO LUMC\Vijiji\drive-download-20250811T084705Z-1-001\Katavi Mamlaka za Wilaya na Mamlaka za Miji GP DOM.pdf')
print('PDF:', pdf_path.name)
print('exists:', pdf_path.exists())

with pdfplumber.open(str(pdf_path)) as pdf:
    print('pages:', len(pdf.pages))
    for i in range(2, min(8, len(pdf.pages))):
        page = pdf.pages[i]
        text = page.extract_text() or ''
        print('\n' + '=' * 70)
        print(f'PAGE {i+1} | chars={len(text)} | width={page.width} height={page.height}')
        print('=' * 70)
        sample = text[:2500]
        print(sample)
        if len(text) > 2500:
            print(f'\n... [truncated, total {len(text)} chars] ...\n')
            print(text[-800:])

        tables = page.extract_tables() or []
        print(f'\n--- TABLES on page {i+1}: count={len(tables)} ---')
        for ti, t in enumerate(tables[:3]):
            print(f'  table[{ti}] rows={len(t)} cols={len(t[0]) if t else 0}')
            for row in t[:8]:
                print('   ', row)
            if len(t) > 8:
                print(f'    ... ({len(t)-8} more rows)')

    print('\n' + '=' * 70)
    print('ALT TABLE SETTINGS (page 4)')
    print('=' * 70)
    if len(pdf.pages) >= 4:
        p = pdf.pages[3]
        for name, settings in [
            ('lines', {'vertical_strategy': 'lines', 'horizontal_strategy': 'lines'}),
            ('text', {'vertical_strategy': 'text', 'horizontal_strategy': 'text'}),
            ('lines_strict', {'vertical_strategy': 'lines_strict', 'horizontal_strategy': 'lines_strict'}),
        ]:
            try:
                ts = p.extract_tables(table_settings=settings) or []
                print(f'  strategy={name}: tables={len(ts)}')
                if ts:
                    t = ts[0]
                    print(f'    first table rows={len(t)} sample rows:')
                    for row in t[:5]:
                        print('   ', row)
            except Exception as e:
                print(f'  strategy={name}: ERROR {e}')

    print('\n' + '=' * 70)
    print('HIERARCHY PATTERN SCAN (pages 3-8)')
    print('=' * 70)
    patterns = {
        'MKOA': re.compile(r'MKOA\s+WA\s+\S+', re.I),
        'WILAYA_LINE': re.compile(r'(?im)^.*(WILAYA|HALMASHAURI|MAMLAKA).{0,80}$'),
        'KATA': re.compile(r'(?im)^.*\bKATA\b.{0,60}$'),
        'KIJIJI_HDR': re.compile(r'(?im)^.*(KIJIJI|VILLAGE).{0,40}$'),
        'numbered': re.compile(r'(?m)^\s*\d+[\.\)]\s+\S+'),
    }
    for i in range(2, min(8, len(pdf.pages))):
        text = pdf.pages[i].extract_text() or ''
        print(f'\nPage {i+1}:')
        for pname, pat in patterns.items():
            hits = pat.findall(text)
            uniq = []
            for h in hits:
                s = (h if isinstance(h, str) else str(h)).strip()
                if s and s not in uniq:
                    uniq.append(s)
            print(f'  {pname}: {len(hits)} hits; sample={uniq[:6]}')
