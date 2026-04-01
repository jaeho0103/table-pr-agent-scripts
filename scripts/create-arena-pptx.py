#!/usr/bin/env python3
"""
Arena reward announcement PPTX generator.
Generates a 2-slide PPTX: [1] Odin Championship  [2] Heimdall Season

Usage:
  python3 create-arena-pptx.py \\
    <odin_champ_num> <odin_start> <odin_end> <odin_prize> <odin_cur_block> \\
    <heim_season_num> <heim_start> <heim_end> <heim_prize> <heim_cur_block> \\
    [rounds] [interval] [medals]

Example:
  python3 create-arena-pptx.py \\
    21 17889224 18040423 500000 17862624 \\
    21 9412781 9563980 400000 9365492
"""

import sys, os, re, copy, zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PPTX = os.path.join(SCRIPT_DIR, '..', 'assets', 'arena', 'template.pptx')
OUTPUT_DIR    = os.path.join(SCRIPT_DIR, '..', 'output', 'arena')

NS_P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
NS_A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
NS_R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

# Slide paths in template
SLIDE_CHAMPIONSHIP = 'ppt/slides/slide4.xml'
SLIDE_SEASON       = 'ppt/slides/slide3.xml'
SLIDE_CHAMP_RELS   = 'ppt/slides/_rels/slide4.xml.rels'
SLIDE_SEASON_RELS  = 'ppt/slides/_rels/slide3.xml.rels'

# ─── Date helpers ─────────────────────────────────────────────────────────────

REF_TIME = datetime(2026, 4, 1, 5, 58, 0, tzinfo=timezone.utc)

def block_to_date(target, ref_block, ref_time=REF_TIME, rate=8):
    dt = ref_time + timedelta(seconds=(target - ref_block) * rate)
    d = dt.day
    sfx = 'th' if 11 <= d <= 13 else {1:'st',2:'nd',3:'rd'}.get(d % 10, 'th')
    return f'{dt.strftime("%B")} {d}{sfx}'

# ─── Reward tables ────────────────────────────────────────────────────────────

CHAMP_GROUPS = [
    # Championship (1000 players) — update when confirmed
    ("Rank 1 – 5",     5,  10),
    ("Rank 6 – 10",    5,   8),
    ("Rank 11 – 17",   7,   9),
    ("Rank 18 – 30",  13,  12),
    ("Rank 31 – 50",  20,  12),
    ("Rank 51 – 100", 50,  15),
    ("Rank 101 – 175",75,  15),
    ("Rank 176 – 250",75,  13),
    ("Rank 251 – 500",250,  4),
    ("Rank 501 – 1000",500, 2),
]
SEASON_GROUPS = [
    # Season (500 players) — verified against Championship 16 season data
    ("Rank 1 – 2",    2,   8),
    ("Rank 3 – 5",    3,   9),
    ("Rank 6 – 9",    4,   8),
    ("Rank 10 – 15",  6,  10),   # fixed: was 16
    ("Rank 16 – 25", 10,  12),
    ("Rank 26 – 50", 25,  18),
    ("Rank 51 – 87", 37,  16),
    ("Rank 88 – 125",38,  11),
    ("Rank 126 – 250",125, 5),
    ("Rank 251 – 500",250, 3),
]

# Staking/courage reward multipliers (relative to base unit):
#   None=÷3.2, lv2=×1.5, lv3=×2.0, courage=×2.2, lv2+cp=×2.7, Full(lv3+cp)=×3.2
# Full = group_reward / players  (i.e. bu × 3.2 = g / players)
def calc_table(groups, prize):
    rows = []
    for name, players, pct in groups:
        g = prize * pct / 100
        bu = g / players / 3.2
        rows.append(dict(
            name=name, players=players, pct=pct, group=round(g),
            none=round(bu),
            lvl2=round(bu * 1.5),
            lvl3=round(bu * 2.0),
            cp  =round(bu * 2.2),
            cp2 =round(bu * 2.7),
            full=round(bu * 3.2),
        ))
    return rows

def fmt(n): return f"{int(n):,}"

# ─── Namespace-safe XML modification ─────────────────────────────────────────

def _register_ns(xml_bytes):
    """Register all namespaces found in document so ET preserves prefixes."""
    for m in re.finditer(rb'xmlns:(\w+)=["\']([^"\']+)["\']', xml_bytes):
        try: ET.register_namespace(m.group(1).decode(), m.group(2).decode())
        except: pass

def _restore_root_ns(original_bytes, new_xml_str):
    """Replace ET-generated root element tag with original to restore all xmlns declarations."""
    orig = original_bytes.decode('utf-8')
    # Extract original root tag (everything from <p:sld to first >)
    m_orig = re.search(r'<p:sld[^>]*>', orig, re.DOTALL)
    m_new  = re.search(r'<p:sld[^>]*>', new_xml_str, re.DOTALL)
    if m_orig and m_new:
        return new_xml_str[:m_new.start()] + m_orig.group(0) + new_xml_str[m_new.end():]
    return new_xml_str

def _set_para_text(para, text):
    """Collapse all runs in paragraph to one, preserving first run's rPr."""
    runs = para.findall(f'{{{NS_A}}}r')
    if not runs: return
    rPr = copy.deepcopy(runs[0].find(f'{{{NS_A}}}rPr'))
    for r in list(runs): para.remove(r)
    for br in list(para.findall(f'{{{NS_A}}}br')): para.remove(br)
    r = ET.SubElement(para, f'{{{NS_A}}}r')
    if rPr is not None: r.insert(0, rPr)
    t = ET.SubElement(r, f'{{{NS_A}}}t')
    t.text = text
    if text and (text[0]==' ' or text[-1]==' '):
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')

def _set_cell_text(cell, text):
    for txBody in cell.findall(f'{{{NS_A}}}txBody'):
        for p in txBody.findall(f'{{{NS_A}}}p'):
            if p.findall(f'{{{NS_A}}}r'):
                _set_para_text(p, text)
                return

# ─── Core slide modifier ──────────────────────────────────────────────────────

def modify_slide(xml_bytes, chain, arena_type, number,
                 start_block, start_date, end_block, end_date,
                 prize, rounds=14, interval=10800, medals=60):

    _register_ns(xml_bytes)
    root = ET.fromstring(xml_bytes)

    title  = f'[ {chain}\u00a0] Arena {arena_type} {number}\u00a0Rewards'
    blocks = (f'Start Block : {fmt(start_block)} (Est. {start_date})    '
              f'End Block : {fmt(end_block)} (Est. {end_date})')

    if arena_type == 'Championship':
        tkt1 = f'You need to collect {medals} Medals during the Season to be eligible'
        tkt2 = f'{rounds} rounds per Championship, each round lasts about 24 hours ({interval:,} block interval)'
    else:
        tkt1 = 'You can buy up to 24 tickets during the entire Season'
        tkt2 = 'You can buy up to 4 extra tickets during each session (each refresh, or about 24 hours).'

    # Update text shapes
    for sp in root.iter(f'{{{NS_P}}}sp'):
        all_t = ''.join(x.text or '' for x in sp.iter(f'{{{NS_A}}}t'))
        txBody = sp.find(f'{{{NS_P}}}txBody')
        if not txBody: continue
        paras = txBody.findall(f'{{{NS_A}}}p')

        if 'Arena Season' in all_t or 'Arena Championship' in all_t:
            for p in paras:
                pt = ''.join(x.text or '' for x in p.iter(f'{{{NS_A}}}t'))
                if any(k in pt for k in ['Arena', 'Odin', 'Heimdall', 'Rewards']):
                    _set_para_text(p, title); break

        elif 'Start Block' in all_t:
            for p in paras:
                pt = ''.join(x.text or '' for x in p.iter(f'{{{NS_A}}}t'))
                if 'Start Block' in pt:
                    _set_para_text(p, blocks); break

        elif 'buy up to' in all_t or 'Medals' in all_t or 'rounds per' in all_t:
            tgt1_done = False
            for p in paras:
                pt = ''.join(x.text or '' for x in p.iter(f'{{{NS_A}}}t'))
                if not tgt1_done and ('buy up to' in pt or 'Medals' in pt or 'rounds' in pt or 'eligible' in pt):
                    _set_para_text(p, tkt1); tgt1_done = True
                elif tgt1_done and ('session' in pt or 'refresh' in pt or 'interval' in pt or 'extra' in pt):
                    _set_para_text(p, tkt2); break

    # Update reward table
    groups = CHAMP_GROUPS if arena_type == 'Championship' else SEASON_GROUPS
    reward_rows = calc_table(groups, prize)
    tbl = root.find(f'.//{{{NS_A}}}tbl')
    if tbl:
        tr_list = tbl.findall(f'{{{NS_A}}}tr')
        for tr, rd in zip(tr_list[1:-1], reward_rows):
            cells = tr.findall(f'{{{NS_A}}}tc')
            if len(cells) >= 10:
                _set_cell_text(cells[0], rd['name'])
                _set_cell_text(cells[1], fmt(rd['players']))
                _set_cell_text(cells[2], str(rd['pct']))
                _set_cell_text(cells[3], fmt(rd['group']))
                _set_cell_text(cells[4], fmt(rd['none']))   # Each Player Gets (None)
                _set_cell_text(cells[5], fmt(rd['lvl2']))   # staking lv2
                _set_cell_text(cells[6], fmt(rd['lvl3']))   # staking lv3
                _set_cell_text(cells[7], fmt(rd['cp']))     # couragepass
                _set_cell_text(cells[8], fmt(rd['cp2']))    # staking lv2 + courage
                _set_cell_text(cells[9], fmt(rd['full']))   # Full: staking lv3 + courage
        # Sum row
        sc = tr_list[-1].findall(f'{{{NS_A}}}tc')
        if len(sc) >= 4:
            _set_cell_text(sc[1], fmt(sum(r['players'] for r in reward_rows)))
            _set_cell_text(sc[3], fmt(prize))

    new_xml = ET.tostring(root, encoding='unicode')
    new_xml = _restore_root_ns(xml_bytes, new_xml)
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + new_xml).encode('utf-8')

# ─── Presentation XML / rels trimmer ──────────────────────────────────────────

def trim_presentation(prs_bytes, keep_rids):
    """Remove all slides from sldIdLst except those in keep_rids."""
    _register_ns(prs_bytes)
    root = ET.fromstring(prs_bytes)
    ns = NS_P
    lst = root.find(f'.//{{{ns}}}sldIdLst')
    if lst is not None:
        for sldId in list(lst):
            rid = sldId.attrib.get(f'{{{NS_R}}}id', '')
            if rid not in keep_rids:
                lst.remove(sldId)
    new_xml = ET.tostring(root, encoding='unicode')
    new_xml = _restore_root_ns(prs_bytes, new_xml)
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + new_xml).encode('utf-8')

def trim_prs_rels(rels_bytes, keep_rids):
    """Keep only the rels in keep_rids (plus non-slide rels)."""
    _register_ns(rels_bytes)
    root = ET.fromstring(rels_bytes)
    for rel in list(root):
        t = rel.attrib.get('Type','').split('/')[-1]
        if t == 'slide' and rel.attrib.get('Id','') not in keep_rids:
            root.remove(rel)
    return (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            + ET.tostring(root, encoding='unicode').encode('utf-8'))

# ─── Main generator ───────────────────────────────────────────────────────────

def generate(
    odin_num, odin_start, odin_end, odin_prize, odin_cur,
    heim_num, heim_start, heim_end, heim_prize, heim_cur,
    rounds=14, interval=10800, medals=60
):
    odin_start_date = block_to_date(odin_start, odin_cur)
    odin_end_date   = block_to_date(odin_end,   odin_cur)
    heim_start_date = block_to_date(heim_start, heim_cur)
    heim_end_date   = block_to_date(heim_end,   heim_cur)

    print(f'[Odin] Championship {odin_num}: {fmt(odin_start)} ({odin_start_date}) ~ {fmt(odin_end)} ({odin_end_date}), Prize={fmt(odin_prize)}')
    print(f'[Heimdall] Season {heim_num}: {fmt(heim_start)} ({heim_start_date}) ~ {fmt(heim_end)} ({heim_end_date}), Prize={fmt(heim_prize)}')

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_file = os.path.join(OUTPUT_DIR, f'arena_Odin_Championship{odin_num}_Heimdall_Season{heim_num}.pptx')

    # Determine which rIds correspond to slide3 and slide4
    CHAMP_RIDS = {'rId9'}   # slide4
    SEASON_RIDS = {'rId8'}  # slide3
    KEEP_RIDS = CHAMP_RIDS | SEASON_RIDS

    with zipfile.ZipFile(TEMPLATE_PPTX, 'r') as zin, \
         zipfile.ZipFile(out_file, 'w', zipfile.ZIP_DEFLATED) as zout:

        for item in zin.infolist():
            fn = item.filename
            data = zin.read(fn)

            if fn == SLIDE_CHAMPIONSHIP:
                data = modify_slide(data, 'Odin', 'Championship', odin_num,
                                    odin_start, odin_start_date,
                                    odin_end,   odin_end_date,
                                    odin_prize, rounds, interval, medals)

            elif fn == SLIDE_SEASON:
                data = modify_slide(data, 'Heimdall', 'Season', heim_num,
                                    heim_start, heim_start_date,
                                    heim_end,   heim_end_date,
                                    heim_prize)

            elif fn == 'ppt/presentation.xml':
                data = trim_presentation(data, KEEP_RIDS)

            elif fn == 'ppt/_rels/presentation.xml.rels':
                data = trim_prs_rels(data, KEEP_RIDS)

            # Skip other slides entirely
            elif re.match(r'ppt/slides/slide(\d+)\.xml', fn):
                slide_num = int(re.search(r'\d+', fn.split('/')[-1]).group())
                if slide_num not in (3, 4): continue
            elif re.match(r'ppt/slides/_rels/slide(\d+)\.xml\.rels', fn):
                slide_num = int(re.search(r'\d+', fn.split('/')[-1]).group())
                if slide_num not in (3, 4): continue
            elif re.match(r'ppt/notesSlides/', fn): continue

            zout.writestr(item, data)

    print(f'✅ Saved: {out_file}')
    return out_file


def main():
    args = sys.argv[1:]
    if len(args) < 10:
        print(__doc__)
        sys.exit(1)
    (odin_num, odin_start, odin_end, odin_prize, odin_cur,
     heim_num, heim_start, heim_end, heim_prize, heim_cur) = [int(a) for a in args[:10]]
    rounds   = int(args[10]) if len(args) > 10 else 14
    interval = int(args[11]) if len(args) > 11 else 10800
    medals   = int(args[12]) if len(args) > 12 else 60
    generate(odin_num, odin_start, odin_end, odin_prize, odin_cur,
             heim_num, heim_start, heim_end, heim_prize, heim_cur,
             rounds, interval, medals)

if __name__ == '__main__':
    main()
