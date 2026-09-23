/* mid.midicn.com · 站点逻辑（实验版 · 纯中文）
   依赖：assets/style.css（复制自 lib.midicn.com，自包含）。
   链接约定：详情/播放 → lib.midicn.com/detail.html?id=…（自带播放器与 loc.json 兜底）
             下载     → lib.midicn.com/<f>（.mid 文件直链，实测可下） */
'use strict';

const LIB = 'https://lib.midicn.com/';
const DIMS_ORDER = ['composer', 'region', 'genre', 'period', 'instrument', 'source'];
const DIM_LABEL = {
  composer: '作曲家', region: '中国民歌 · 分省', genre: '流派',
  period: '时期', instrument: '乐器', source: '来源'
};

/* 维度值显示名（未知码回退为原码） */
const DISPLAY_MAP = {
  genre: { classical: '古典', folk: '民谣', hymn: '赞美诗', drum: '鼓点', pop: '流行',
           christmas: '圣诞', game: '游戏', jazz: '爵士', atonal: '无调性',
           ragtime: '拉格泰姆', soundtrack: '影视原声', blues: '蓝调', rock: '摇滚' },
  instrument: { piano: '钢琴', melody: '旋律', organ: '管风琴', voice: '人声',
                ensemble: '合奏', voice_piano: '声乐与钢琴', drums: '打击乐', guitar: '吉他' },
  period: { traditional: '传统', romantic: '浪漫', classical: '古典', modern: '现代',
            contemporary: '当代', baroque: '巴洛克', renaissance: '文艺复兴', impressionist: '印象派' },
  source: { aria: 'Aria-MIDI', thesession: 'The Session', cyberhymnal: 'Cyber Hymnal',
            chinafolk: '中国民间歌曲集成', essen: 'ESAC 民歌档案', giantmidi: 'GiantMIDI-Piano',
            lakh: 'Lakh MIDI（过滤）', norbeck: 'Norbeck ABC', m21: 'music21 语料库',
            mutopia: 'Mutopia Project', abcmisc: 'ABC Misc', openscore: 'OpenScore Lieder',
            maestro: 'MAESTRO v3', groove: 'Groove MIDI', emopia: 'EMOPIA v2.2',
            nottingham: 'Nottingham 曲集', wikifonia: 'Wikifonia（PD 子集）',
            oga: 'OpenGameArt', musicnet: 'MusicNet' }
};

/* 许可档位：z 字段 → 徽标（全站统一的 C1/C2/C3 视觉语言） */
function tierOf(z) {
  if (z === 'main') return { code: 'C1', cls: 'c1', zh: '可商用' };
  if (z === 'piano-special') return { code: 'C2', cls: 'c2', zh: '非商用' };
  if (z === 'study') return { code: 'C3', cls: 'c3', zh: '学习研究' };
  return { code: (z || '—').toUpperCase(), cls: 'plain', zh: z || '—' };
}

const esc = s => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

const detailUrl = id => LIB + 'detail.html?id=' + encodeURIComponent(id);
const fileUrl = f => LIB + f.replace(/^\/+/, '');
const shardUrl = (d, k) => 'data/dims/' + d + '/' + encodeURIComponent(k) + '.json';

function fmtDur(s) {
  if (s == null || s === '') return '';
  const n = Math.round(Number(s)); if (!isFinite(n) || n <= 0) return '';
  return Math.floor(n / 60) + ':' + String(n % 60).padStart(2, '0');
}

/* fetch 简单重试（境内网络抖动） */
async function fetchT(url, tries) {
  tries = tries || 3;
  let last = null;
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return await r.json();
    } catch (e) { last = e; await new Promise(res => setTimeout(res, 400 * (i + 1))); }
  }
  throw last || new Error('fetch failed');
}

/* 维度值显示名 */
function dimValueLabel(d, k) {
  if (d === 'composer') return k === '-' ? '佚名' : k;
  if (d === 'region') return k;
  const m = DISPLAY_MAP[d];
  return (m && m[k]) || k;
}

/* 行 HTML（dim.html 用） */
function rowHTML(row, compNames) {
  const title = esc(row.t || row.cn || row.id);
  // v1.23：catalog 新增 cnzh（作曲家中文名）→ 中文界面优先用它
  const comp = esc(row.cnzh || (compNames && compNames.get(row.c)) || row.c || '');
  const dur = fmtDur(row.du);
  const tier = tierOf(row.z);
  return '<div class="dimrow">' +
    '<div class="dr-main">' +
      '<a class="dr-t" href="' + esc(detailUrl(row.id)) + '" target="_blank" rel="noopener">' + title + '</a>' +
      '<span class="dr-sub">' + (comp ? esc(comp) + ' · ' : '') + (dur ? esc(dur) + ' · ' : '') +
        '<span class="addr">' + esc(row.id) + '</span></span>' +
    '</div>' +
    '<div class="dr-side">' +
      '<span class="lic ' + tier.cls + '" title="' + esc(tier.zh) + '">' + tier.code + '</span>' +
      '<a class="dr-dl" href="' + esc(fileUrl(row.f)) + '" download title="下载 MIDI（lib.midicn.com）">下载 ⭳</a>' +
    '</div>' +
  '</div>';
}

/* 档位聚合（分片 rows → C1/C2/C3 计数） */
function tierAgg(rows) {
  const c = { C1: 0, C2: 0, C3: 0 };
  (rows || []).forEach(r => { const t = tierOf(r.z); if (c[t.code] != null) c[t.code]++; });
  return c;
}

/* 错误提示（写进页面，绝不留白页） */
function showErr(el, msg) {
  if (!el) { console.error(msg); return; }
  el.innerHTML = '<div class="note">加载出错：' + esc(msg) + ' —— 请刷新重试，或前往 ' +
    '<a href="' + LIB + '">lib.midicn.com</a></div>';
}
