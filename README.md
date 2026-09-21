# mid.midicn.com · 维度浏览实验站

按「作曲家 / 中国民歌分省 / 流派 / 时期 / 乐器 / 来源」六种维度浏览
[midicn-lib](https://github.com/midicn/midi-lib) 的 **124,179** 首 MIDI。实验性质。

- 音乐库（播放 / 详情 / 使用方式分包下载）：<https://lib.midicn.com>
- 来源台账（每个地址的取得方式与校验值）：<https://lib.midicn.com/provenance.html>

## 形态（重要）

- **全部查询字符串形态**：页面只有一个模板 `dim.html?d=<维度>&s=<值>`；不生成任何静态维度页
- **站点独立运转**：样式与数据自持；**MIDI 文件与播放/详情深链直接使用 lib.midicn.com**
  （行内「下载」= `lib.midicn.com/<f>` 直链；「详情 / 播放」= `lib.midicn.com/detail.html?id=…`）
- 行内徽标为**许可档位**（C1 可商用 / C2 非商用 / C3 学习研究），与 lib 全站口径一致

## 数据机制（仓库不含数据）

部署工作流从 midi-lib 的 Release 下载 `midicn-lib-<VER>-meta.zip`（官方目录
`catalog.json`，124,179 条）→ 现场运行 [`tools/gen_dims.py`](tools/gen_dims.py)
切出维度分片（`data/dims/…`）→ 部署 GitHub Pages。lib 发新版本后，改本仓
`deploy.yml` 顶部 `RELEASE_TAG` 重新部署即自动跟随。

生成器内置自校验（计数对账 / JSON 可解析 / 行字段完整），失败即部署变红。

## 本地复现

```bash
python3 tools/gen_dims.py --meta <含 catalog.json 的目录> --out .
python3 -m http.server 8000    # 打开 http://localhost:8000
```

## 已知限制

- 作曲家维度按 `c` 字段聚合（9,920 个键，含「佚名」兜底）；长尾署名未逐一考证
- 「中国民歌 · 分省」仅统计 chinafolk（中文省名）与 essen 中国卷（拼音省名映射），
  其余来源不计入；essen 非中国省名自动排除
- 实验版纯中文；文案集中于 `assets/site.js` 的 STR/DISPLAY_MAP，后续可扩展双语
