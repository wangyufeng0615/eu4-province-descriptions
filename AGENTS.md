# EU4 省份地方志：发布工程

这里把研究工程写好的省份介绍构建成 EU4 模组，装进本机游戏做实验，以后也从这里发布到创意工坊。正文、来源和写作规则都在研究工程，这里不改正文。

## 三处位置

| | 位置 | 管什么 |
|---|---|---|
| 研究工程 | Mac mini `~/personal/paradox-mods/eu4-provinces/research`（主副本，GitHub 私有库 `wangyufeng0615/eu4-province-gazetteer-research`）；MacBook 克隆在同一路径 | 3,272 个陆地省份的词条、资料、写作规则、批量写作调度器 |
| 发布工程 | 本目录，Windows `V:\paradox-mods\eu4-provinces\workshop`（本地 Git，暂无远端） | 构建、装进游戏、以后的工坊文案和发布 |
| 旧原型 | `V:\paradox-mods\eu4-provinces\archive\eu4-gazetteer-prototype` | 0.1—0.7 原型期的脚本，已被研究工程取代，只作追溯 |

## 数据怎么流动

只单向：研究工程 `tools/export_workshop.py` 导出 `revised`、`final` 词条到本目录的 `data/entries.jsonl`，这里只读不改。改正文回研究工程改，再重新同步。

日常在 MacBook 上一步做完（MacBook 能同时连 Mac mini 和 Windows）：

```bash
cd ~/personal/paradox-mods/eu4-provinces/research && tools/sync_workshop.sh          # 导出、拷到这里、构建、装进游戏
tools/sync_workshop.sh --debug                                                        # 提示框底部多一行中文模组检测结果
```

只在 Windows 上重新构建（不更新数据）：

```bat
cd /d V:\paradox-mods\eu4-provinces\workshop
python -B tools\build.py --install
```

装好后要完全退出再重开 EU4 才会读到新文件。同步脚本会把新数据提交到本目录的 Git，方便回退。

## 文件

| 路径 | 内容 |
|---|---|
| `project.json` | 模组名、目录名、版本、依赖、中文模组的显示名、按钮位置、底稿 GUI 路径 |
| `data/entries.jsonl` | 研究工程导出的词条，一行一个省份：`id`、`en`、`zh`、`status` |
| `tools/build.py` | 构建与安装，只用标准库 |
| `tools/eu4zh.py` | 中文模组（工坊 2976470733）的文字编码，和研究工程里的同名文件一致，改一处要同步另一处 |
| `assets/eu4lg_button.dds` | 省份窗口里的地方志按钮，`tools/draw_icon.py` 生成（`uv run --with pillow tools/draw_icon.py <游戏目录>/gfx/interface/button_history.dds assets/eu4lg_button`） |

## 技术要点

- 按钮加在 Bigger UI（工坊 788906833）的 `provinceview.gui` 上，`project.json` 的 `base_gui` 指向它；正式发布要另做原版界面一份，并说明加载顺序。
- 中英文都写进 `l_english`；用 `is_mod_active` 检测中文模组，启用时显示中文。`zh_mods` 发布前要补齐常见中文模组的显示名。
- 每个省份一条 `province_id = N` 的 `defined_text` 分支，只在悬停按钮时判断。
- 加了 `common/custom_gui`，会改变校验码，铁人模式拿不到成就；不改校验码的路线 0.1 已证实走不通。

## 还没做

工坊页面文案、截图、封面、版本号和更新日志的规矩、原版界面版本、GitHub 公开仓库。真要发布时照 EU5 地块发布工程（`V:\paradox-mods\eu5-locations\workshop`）补齐。
