#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mid.midicn.com 维度分片生成器

输入：meta/catalog.json（随 midi-lib Release 的 meta 包下发；124,179 首 · 20 字段）
输出：data/dims/index.json（六维度入口）+ data/dims/<dim>/<key>.json（每值一分片）

维度
  composer   按作曲家 slug（c）聚合，显示名取 cn 众数；'-' 记为「佚名」
  region     中国民歌分省（特化视图）：仅认 chinafolk（r=中文省名白名单）与
             essen（r=拼音省名，经 PINYIN_TO_ZH 映射）；其余来源与非中国省名不计入
  genre/period/instrument  按 g/p/i 字段
  source     按 id 前缀（id.split('-')[0]；注意 catalog 的 v 字段是质量标记，不是来源）

分片行字段（精简 8 键）：id, t(显示名兜底), cn, du(int), l, z, f, c
  行内徽标 = 许可档位（z → C1/C2/C3），时长为纯文本 —— 不要把档位配色挪作他用。

自校验（失败 exit 2，让部署工作流变红）：
  ① 每维度 Σcount == 实际写盘行数  ② 全部分片可 json.load
  ③ 每行必含 id 与 f              ④ index.total == len(tracks)
  ⑤ 每行 z ∈ {main, piano-special, study}

用法
  python3 tools/gen_dims.py --meta meta --out .
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

CHUNK = 2000                    # 单分片行上限（超过则 <key>-<n>.json 二级切分）
# 分片保留字段。v1.23 起 catalog 多出 cnzh（作曲家中文名）等字段，
# 这里同步纳入 cnzh —— 中文用户先看到中文作曲家名。其余新字段（perf/alb/wk/vt）
# 属于 lib 详情页的演奏版语境，维度浏览不需要，故不入 SLIM 以控制分片体积。
SLIM = ('id', 't', 'cn', 'cnzh', 'du', 'l', 'z', 'f', 'c')
Z_TIER = {'main': 'C1', 'piano-special': 'C2', 'study': 'C3'}

# chinafolk 的 r 白名单（11 个中文省名，实测无杂质）
PROVINCE_ZH = {'江苏', '陕西', '河北', '广东', '河南', '海南', '吉林',
               '上海', '四川', '天津', '北京'}

# essen 中国卷的拼音省名 → 中文（覆盖 index-by-region 中的拼音键；非中国省名不映射）
PINYIN_TO_ZH = {
    'Anhui': '安徽', 'Beijing': '北京', 'Chongqing': '重庆', 'Fujian': '福建',
    'Gansu': '甘肃', 'Guangdong': '广东', 'Guangxi': '广西', 'Guizhou': '贵州',
    'Hainan': '海南', 'Hebei': '河北', 'Heilongjiang': '黑龙江', 'Henan': '河南',
    'Hubei': '湖北', 'Hunan': '湖南', 'Jiangsu': '江苏', 'Jiangxi': '江西',
    'Jilin': '吉林', 'Liaoning': '辽宁', 'Neimenggu': '内蒙古', 'Ningxia': '宁夏',
    'Qinghai': '青海', 'Shaanxi': '陕西', 'Shandong': '山东', 'Shanghai': '上海',
    'Shanxi': '山西', 'Sichuan': '四川', 'Tianjin': '天津', 'Xinjiang': '新疆',
    'Xizang': '西藏', 'Yunnan': '云南', 'Zhejiang': '浙江',
}

DIMS = ('composer', 'region', 'genre', 'period', 'instrument', 'source')
DIM_LABEL = {'composer': '作曲家', 'region': '中国民歌 · 分省', 'genre': '流派',
             'period': '时期', 'instrument': '乐器', 'source': '来源'}


def disp_title(t: dict) -> str:
    """无标题曲目的显示名合成（与 lib 站 tools/gen_shards.disp_title 口径一致）"""
    tt = (t.get('t') or '').strip()
    if tt:
        return tt
    cn = t.get('cn') or t.get('c') or ''
    op, no = t.get('opus'), t.get('no')
    parts = []
    if op:
        parts.append(f'Op. {op}')
    if no:
        parts.append(f'No. {no}')
    if cn and parts:
        return f'{cn} · ' + ' '.join(parts)
    if cn:
        return cn
    return ' / '.join(parts) or (t.get('id') or '')


def slim_row(t: dict) -> dict:
    d = {k: t.get(k) for k in SLIM if t.get(k) not in (None, '')}
    if t.get('du') not in (None, ''):
        try:
            d['du'] = round(float(t['du']))
        except (TypeError, ValueError):
            pass
    d['t'] = disp_title(t)
    d['c'] = t.get('c') or '-'
    return d


def src_of(t: dict) -> str:
    return (t.get('id') or '').split('-')[0]


def region_key(t: dict):
    """中国民歌分省视图的键；不纳入分省视图的返回 None"""
    src = src_of(t)
    r = (t.get('r') or '').strip()
    if src == 'chinafolk':
        return r if r in PROVINCE_ZH else '未分省'
    if src == 'essen':
        return PINYIN_TO_ZH.get(r)      # 非中国省名 → None（排除）
    return None


def build_rows(tracks: list) -> tuple[dict, dict, dict]:
    rows = {d: defaultdict(list) for d in DIMS}
    counts = {d: Counter() for d in DIMS}
    cn_mode: dict = defaultdict(Counter)
    for t in tracks:
        s = slim_row(t)
        comp = t.get('c') or '-'
        rows['composer'][comp].append(s)
        counts['composer'][comp] += 1
        if t.get('cn'):
            cn_mode[comp][t['cn']] += 1
        for dim, field in (('genre', 'g'), ('period', 'p'), ('instrument', 'i')):
            k = (t.get(field) or '').strip()
            if k:
                rows[dim][k].append(s)
                counts[dim][k] += 1
        sv = src_of(t)
        if sv:
            rows['source'][sv].append(s)
            counts['source'][sv] += 1
        rk = region_key(t)
        if rk:
            rows['region'][rk].append(s)
            counts['region'][rk] += 1
    return rows, counts, cn_mode


def write_shards(out: Path, dim: str, rows_map: dict, labels: dict) -> tuple[int, int]:
    """写分片；返回 (文件数, 行数)"""
    n_files = n_rows = 0
    (out / 'data' / 'dims' / dim).mkdir(parents=True, exist_ok=True)
    for key, items in sorted(rows_map.items()):
        parts = [items[i:i + CHUNK] for i in range(0, len(items), CHUNK)]
        for i, part in enumerate(parts):
            name = f'{key}.json' if len(parts) == 1 else f'{key}-{i}.json'
            payload = {'dim': dim, 'key': key, 'label': labels.get(key, key),
                       'total': len(items), 'count': len(part),
                       'part': i, 'parts': len(parts), 'rows': part}
            fp = out / 'data' / 'dims' / dim / name
            fp.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
                          encoding='utf-8')
            n_files += 1
            n_rows += len(part)
    return n_files, n_rows


def build_index(version: str, total: int, counts: dict, cn_mode: dict,
                idx_composer: dict | None, labels: dict) -> dict:
    dims = {}
    # composer：显示名 = cn 众数；'-' → 佚名
    vals = []
    for slug, n in counts['composer'].most_common():
        label = (cn_mode.get(slug, Counter()).most_common(1)[0][0] if cn_mode.get(slug)
                 else ('佚名' if slug == '-' else slug))
        vals.append({'k': slug, 'label': label, 'count': n})
    dims['composer'] = {'label': DIM_LABEL['composer'], 'values': vals}
    # region
    vals = [{'k': k, 'label': labels.get(k, k), 'count': n}
            for k, n in counts['region'].most_common()]
    dims['region'] = {'label': DIM_LABEL['region'], 'values': vals}
    # genre/period/instrument/source
    field = {'genre': 'g', 'period': 'p', 'instrument': 'i', 'source': 'src'}
    for dim in ('genre', 'period', 'instrument', 'source'):
        vals = []
        for k, n in counts[dim].most_common():
            label = k
            if dim == 'source':
                label = k
            vals.append({'k': k, 'label': label, 'count': n})
        dims[dim] = {'label': DIM_LABEL[dim], 'values': vals}
    return {'version': version, 'total': total,
            'generated': datetime.date.today().isoformat(),
            'note': 'mid.midicn.com 维度分片入口 · 由 tools/gen_dims.py 生成',
            'dims': dims}


def self_check(out: Path, tracks: list, rows: dict, counts: dict) -> None:
    errs = []
    for dim in DIMS:
        written = sum(len(items) for items in rows[dim].values())
        counted = sum(counts[dim].values())
        if written != counted:
            errs.append(f'{dim}: 写盘行 {written} ≠ 计数 {counted}')
    # 逐文件对账：Σ(每文件 count) == 该维度计数（防分块语义错误）
    per_dim = Counter()
    for fp in sorted((out / 'data' / 'dims').rglob('*.json')):
        if fp.name == 'index.json':
            continue
        try:
            payload = json.loads(fp.read_text(encoding='utf-8'))
        except Exception as e:                                   # noqa: BLE001
            errs.append(f'{fp.name} 不可解析: {e}')
            continue
        per_dim[payload['dim']] += payload['count']
        for r in payload.get('rows', []):
            if not r.get('id') or not r.get('f'):
                errs.append(f'{fp.name} 行缺 id/f')
                break
            if r.get('z') not in Z_TIER:
                errs.append(f'{fp.name} 行 z 非法: {r.get("z")}')
                break
    for dim in DIMS:
        if per_dim.get(dim) != sum(counts[dim].values()):
            errs.append(f'{dim}: 分片 count 合计 {per_dim.get(dim)} ≠ {sum(counts[dim].values())}')
    if sum(counts['composer'].values()) != len(tracks):
        errs.append(f'composer 覆盖 {sum(counts["composer"].values())} ≠ {len(tracks)}')
    for fp in sorted((out / 'data' / 'dims').rglob('*.json')):
        try:
            payload = json.loads(fp.read_text(encoding='utf-8'))
        except Exception as e:                                   # noqa: BLE001
            errs.append(f'{fp.name} 不可解析: {e}')
            continue
        for r in payload.get('rows', []):
            if not r.get('id') or not r.get('f'):
                errs.append(f'{fp.name} 行缺 id/f')
                break
            if r.get('z') not in Z_TIER:
                errs.append(f'{fp.name} 行 z 非法: {r.get("z")}')
                break
    if errs:
        print('✗ 自校验失败：', file=sys.stderr)
        for e in errs[:20]:
            print('   ', e, file=sys.stderr)
        sys.exit(2)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description='mid.midicn.com 维度分片生成器')
    ap.add_argument('--meta', default='meta', help='含 catalog.json 的目录')
    ap.add_argument('--out', default='.', help='站点根（生成 data/dims/）')
    args = ap.parse_args(argv[1:])

    meta = Path(args.meta)
    cat_path = meta / 'catalog.json'
    if not cat_path.exists():
        print(f'✗ 找不到 {cat_path}', file=sys.stderr)
        return 2
    cat = json.loads(cat_path.read_text(encoding='utf-8'))
    tracks = cat['tracks'] if isinstance(cat, dict) else cat
    version = str(cat.get('version', '')) if isinstance(cat, dict) else ''
    print(f'载入 catalog：{len(tracks):,} 首 · version {version}')

    idx_composer = None
    idx_path = meta / 'index-by-composer.json'
    if idx_path.exists():
        try:
            idx_composer = json.loads(idx_path.read_text(encoding='utf-8'))
        except Exception:                                     # noqa: BLE001
            idx_composer = None

    rows, counts, cn_mode = build_rows(tracks)

    # 显示名表：composer 用 cn 众数；region 用省中文名；其余维度前端有 DISPLAY_MAP
    labels: dict = {}
    for slug in rows['composer']:
        labels[slug] = (cn_mode.get(slug, Counter()).most_common(1)[0][0]
                        if cn_mode.get(slug) else ('佚名' if slug == '-' else slug))
    for k in rows['region']:
        labels[k] = k

    out = Path(args.out)
    n_files = n_rows = 0
    for dim in DIMS:
        f_cnt, r_cnt = write_shards(out, dim, rows[dim], labels)
        n_files += f_cnt
        n_rows += r_cnt
        print(f'  {dim:12s} {len(rows[dim]):>6,d} 值 · {r_cnt:>7,d} 行 · {f_cnt:>5,d} 文件')

    index = build_index(version, len(tracks), counts, cn_mode, idx_composer, labels)
    ip = out / 'data' / 'dims' / 'index.json'
    ip.write_text(json.dumps(index, ensure_ascii=False, separators=(',', ':')),
                  encoding='utf-8')
    print(f'  index.json   {len(index["dims"]):>6d} 维度 · total {index["total"]:,}')

    self_check(out, tracks, rows, counts)
    print(f'✓ 完成：{n_files} 个分片 · {n_rows:,} 行 · 自校验通过')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
