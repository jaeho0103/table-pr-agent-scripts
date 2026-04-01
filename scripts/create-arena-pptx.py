#!/usr/bin/env python3
"""
Arena reward announcement PPTX generator
Usage:
  python3 create-arena-pptx.py <chain> <type> <number> <start_block> <end_block> <total_prize> [rounds] [interval] [medals]

  chain       : Odin | Heimdall
  type        : Season | Championship
  number      : e.g. 16
  start_block : e.g. 17889224
  end_block   : e.g. 18040423
  total_prize : e.g. 500000
  rounds      : (Championship only) number of rounds, default 14
  interval    : (Championship only) blocks per round, default 10800
  medals      : (Championship only) medals required, default 60

Dates are auto-calculated from block numbers.
Current block and time are read from config or passed as env vars:
  CURRENT_BLOCK, CURRENT_TIME (ISO format)
"""

import sys, os, zipfile, copy
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PPTX = os.path.join(SCRIPT_DIR, '..', 'assets', 'arena', 'template.pptx')
OUTPUT_DIR    = os.path.join(SCRIPT_DIR, '..', 'output', 'arena')
CONFIG_PATH   = os.path.join(SCRIPT_DIR, '..', 'config', 'arena.json')

NS_P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
NS_A = 'http://schemas.openxmlformats.org/drawingml/2006/main'

SLIDE_MAP = {
    'Season':       'ppt/slides/slide3.xml',
    'Championship': 'ppt/slides/slide4.xml',
}

# ── Date helpers ───────────────────────────────────────────────────────────────

def load_anchor():
    """Load current_block / current_time from config or env."""
    import json
    block = int(os.environ.get('CURRENT_BLOCK', 0))
    t_str = os.environ.get('CURRENT_TIME', '')
    if not block and os.path.exists(CONFIG_PATH):
        cfg = json.load(open(CONFIG_PATH))
        block = int(cfg.get('current_block', 0))
        t_str = t_str or cfg.get('current_time', '')
    if not block:
        raise ValueError('CURRENT_BLOCK not set. Pass via env or config/arena.json.')
    dt = datetime.fromisoformat(t_str) if t_str else datetime.utcnow()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return block, dt


def block_to_datestr(target_block, anchor_block, anchor_time, rate=8):
    """Return 'April 3rd' style string from block number."""
    delta = (target_block - anchor_block) * rate
    dt = anchor_time + timedelta(seconds=delta)
    day = dt.day
    if 11 <= day <= 13:
        suffix = 'th'
    else:
        suffix = {1:'st', 2:'nd', 3:'rd'}.get(day % 10, 'th')
    return f'{dt.strftime("%B")} {day}{suffix}'


# ── Reward table calculation ───────────────────────────────────────────────────

CHAMPIONSHIP_GROUPS = [
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
    ("Rank 1 – 2",     2,   8),
    ("Rank 3 – 5",     3,   9),
    ("Rank 6 – 9",     4,   8),
    ("Rank 10 – 15",  16,  10),
    ("Rank 16 – 25",  10,  12),
    ("Rank 26 – 50",  25,  18),
    ("Rank 51 – 87",  37,  16),
    ("Rank 88 – 125", 38,  11),
    ("Rank 126 – 250",125,  5),
    ("Rank 251 – 500",250,  3),
]

def calc_table(groups, total_prize):
    """Calculate reward rows for given total prize."""
    rows = []
    for name, players, pct in groups:
        group_reward = total_prize * pct // 100
        bu = group_reward / players / 3
        rows.append({
            'name': name,
            'players': players,
            'pct': pct,
            'group_reward': group_reward,
            'basic': round(bu),
            'lvl2':  round(bu * 1.5),
            'lvl3':  round(bu * 2.0),
            'cp':    round(bu * 2.0),
            'cp2':   round(bu * 2.5),
            'cp3':   round(bu * 3.0),
        })
    return rows


def fmt(n):
    """Format number with commas."""
    return f"{int(n):,}"


# ── XML helpers ────────────────────────────────────────────────────────────────

def register_ns():
    namespaces = [
        ('a',   'http://schemas.openxmlformats.org/drawingml/2006/main'),
        ('p',   'http://schemas.openxmlformats.org/presentationml/2006/main'),
        ('r',   'http://schemas.openxmlformats.org/officeDocument/2006/relationships'),
        ('mc',  'http://schemas.openxmlformats.org/markup-compatibility/2006'),
    ]
    for prefix, uri in namespaces:
        ET.register_namespace(prefix, uri)


def set_para_text(para, new_text):
    """Replace all runs in paragraph with a single run, preserving first run's rPr."""
    runs = para.findall(f'{{{NS_A}}}r')
    if not runs:
        return
    rPr = copy.deepcopy(runs[0].find(f'{{{NS_A}}}rPr'))
    for r in list(runs):
        para.remove(r)
    for br in list(para.findall(f'{{{NS_A}}}br')):
        para.remove(br)
    new_r = ET.SubElement(para, f'{{{NS_A}}}r')
    if rPr is not None:
        new_r.insert(0, rPr)
    t = ET.SubElement(new_r, f'{{{NS_A}}}t')
    t.text = new_text
    if new_text and (new_text[0] == ' ' or new_text[-1] == ' '):
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')


def get_cell_text(cell):
    return ''.join(t.text or '' for t in cell.iter(f'{{{NS_A}}}t'))


def set_cell_text(cell, new_text):
    """Update text of a table cell."""
    for txBody in cell.findall(f'{{{NS_A}}}txBody'):
        for para in txBody.findall(f'{{{NS_A}}}p'):
            if para.findall(f'{{{NS_A}}}r'):
                set_para_text(para, new_text)
                return


# ── Main slide updater ─────────────────────────────────────────────────────────

def update_slide(xml_bytes, chain, arena_type, number,
                 start_block, start_date, end_block, end_date,
                 total_prize, rounds=14, interval=10800, medals=60):

    register_ns()
    root = ET.fromstring(xml_bytes)

    title_text = f'[ {chain}\u00a0] Arena {arena_type} {number}\u00a0Rewards'
    block_text = (
        f'Start Block : {fmt(start_block)} (Est. {start_date})    '
        f'End Block : {fmt(end_block)} (Est. {end_date})'
    )

    if arena_type == 'Championship':
        ticket_line1 = f'You need to collect {medals} Medals during the Season to be eligible'
        ticket_line2 = f'{rounds} rounds per Championship, each round lasts about 24 hours ({interval:,} block interval)'
    else:
        ticket_line1 = 'You can buy up to 24 tickets during the entire Season'
        ticket_line2 = 'You can buy up to 4 extra tickets during each session (each refresh, or about 24 hours).'

    # ── Update text shapes ──
    for sp in root.iter(f'{{{NS_P}}}sp'):
        all_t = [t.text for t in sp.iter(f'{{{NS_A}}}t') if t.text]
        combined = ''.join(all_t)

        txBody = sp.find(f'{{{NS_P}}}txBody')
        if txBody is None:
            continue
        paras = txBody.findall(f'{{{NS_A}}}p')

        if 'Arena Season' in combined or 'Arena Championship' in combined:
            for p in paras:
                pt = ''.join(t.text or '' for t in p.iter(f'{{{NS_A}}}t'))
                if any(k in pt for k in ['Arena Season', 'Arena Championship', 'Odin', 'Heimdall', 'Rewards']):
                    set_para_text(p, title_text)
                    break

        elif 'Start Block' in combined:
            for p in paras:
                pt = ''.join(t.text or '' for t in p.iter(f'{{{NS_A}}}t'))
                if 'Start Block' in pt:
                    set_para_text(p, block_text)
                    break

        elif 'buy up to' in combined or 'Medals' in combined or 'medals' in combined or 'rounds' in combined:
            for p in paras:
                pt = ''.join(t.text or '' for t in p.iter(f'{{{NS_A}}}t'))
                if 'buy up to' in pt or 'Medals' in pt or 'rounds' in pt:
                    set_para_text(p, ticket_line1)
                    break
            # second line
            for i, p in enumerate(paras):
                pt = ''.join(t.text or '' for t in p.iter(f'{{{NS_A}}}t'))
                if 'session' in pt or 'refresh' in pt or 'interval' in pt:
                    set_para_text(p, ticket_line2)
                    break

    # ── Update reward table ──
    groups = CHAMPIONSHIP_GROUPS if arena_type == 'Championship' else SEASON_GROUPS
    reward_rows = calc_table(groups, total_prize)

    tbl = root.find(f'.//{{{NS_A}}}tbl')
    if tbl is not None:
        tr_list = tbl.findall(f'{{{NS_A}}}tr')
        data_rows = tr_list[1:-1]  # skip header and sum rows

        for i, (tr, rdata) in enumerate(zip(data_rows, reward_rows)):
            cells = tr.findall(f'{{{NS_A}}}tc')
            if len(cells) >= 10:
                set_cell_text(cells[0], rdata['name'])
                set_cell_text(cells[1], fmt(rdata['players']))
                set_cell_text(cells[2], str(rdata['pct']))
                set_cell_text(cells[3], fmt(rdata['group_reward']))
                set_cell_text(cells[4], fmt(rdata['basic']))
                set_cell_text(cells[5], fmt(rdata['lvl2']))
                set_cell_text(cells[6], fmt(rdata['lvl3']))
                set_cell_text(cells[7], fmt(rdata['cp']))
                set_cell_text(cells[8], fmt(rdata['cp2']))
                set_cell_text(cells[9], fmt(rdata['cp3']))

        # Update sum row
        sum_row = tr_list[-1]
        sum_cells = sum_row.findall(f'{{{NS_A}}}tc')
        if len(sum_cells) >= 4:
            total_players = sum(r['players'] for r in reward_rows)
            set_cell_text(sum_cells[1], fmt(total_players))
            set_cell_text(sum_cells[3], fmt(total_prize))

    xml_str = ET.tostring(root, encoding='unicode')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + xml_str).encode('utf-8')


# ── Entry point ────────────────────────────────────────────────────────────────

def generate(chain, arena_type, number, start_block, end_block, total_prize,
             rounds=14, interval=10800, medals=60):

    anchor_block, anchor_time = load_anchor()
    start_date = block_to_datestr(start_block, anchor_block, anchor_time)
    end_date   = block_to_datestr(end_block,   anchor_block, anchor_time)

    slide_path = SLIDE_MAP.get(arena_type)
    if not slide_path:
        raise ValueError(f'Unknown type: {arena_type}')

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_file = os.path.join(OUTPUT_DIR, f'arena_{chain}_{arena_type}_{number}.pptx')

    with zipfile.ZipFile(TEMPLATE_PPTX, 'r') as zin, \
         zipfile.ZipFile(out_file, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == slide_path:
                data = update_slide(
                    data, chain, arena_type, number,
                    start_block, start_date, end_block, end_date,
                    total_prize, rounds, interval, medals
                )
            zout.writestr(item, data)

    print(f'[{chain}] Arena {arena_type} {number}')
    print(f'  Start: {fmt(start_block)} (Est. {start_date})')
    print(f'  End:   {fmt(end_block)} (Est. {end_date})')
    print(f'  Prize: {fmt(total_prize)} NCG')
    print(f'  Saved: {out_file}')
    return out_file


def main():
    if len(sys.argv) < 7:
        print(__doc__)
        sys.exit(1)

    chain       = sys.argv[1]
    arena_type  = sys.argv[2].capitalize()
    number      = int(sys.argv[3])
    start_block = int(sys.argv[4])
    end_block   = int(sys.argv[5])
    total_prize = int(sys.argv[6])
    rounds      = int(sys.argv[7]) if len(sys.argv) > 7 else 14
    interval    = int(sys.argv[8]) if len(sys.argv) > 8 else 10800
    medals      = int(sys.argv[9]) if len(sys.argv) > 9 else 60

    generate(chain, arena_type, number, start_block, end_block, total_prize,
             rounds, interval, medals)


if __name__ == '__main__':
    main()
