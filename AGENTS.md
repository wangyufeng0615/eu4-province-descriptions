# 所有省份的描述（Descriptions for Every Province）：发布工程

这里把研究工程写好的省份介绍构建成 EU4 模组，装进本机游戏做实验，也从这里发布到创意工坊。模组目录名 `province_descriptions`，工坊条目还没建（`project.json` 的 `publishedfileid` 为 null）。正文、来源和写作规则都在研究工程，这里不改正文。

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

只在 Windows 上重新构建并装进游戏（不更新数据）：

```bat
cd /d V:\paradox-mods\eu4-provinces\workshop
python -B tools\build.py --install            :: 构建到 dist\dev 并装进 文档\Paradox Interactive\Europa Universalis IV\mod
python -B tools\build.py --install --debug    :: 提示框底部多一行中文模组检测结果
```

装好后要完全退出再重开 EU4 才会读到新文件。同步脚本会把新数据提交到本目录的 Git，方便回退。2026-11-03 起模组目录名从测试期的 `eu4_gazetteer_test` 改为 `province_descriptions`；旧的测试副本还在模组目录里，播放集里不要两个同时启用。

## 检查与构建

```bat
python -B -m unittest discover -s tests -v
python -B tools\build.py --check [--game-root "D:\SteamLibrary\steamapps\common\Europa Universalis IV"]
python -B tools\build.py --output dist\<新目录>
python -B tools\build.py --verify dist\<新目录>
```

只用 Python 标准库（3.10+）。`--check` 校验数据（每条要有中英文正文和资料来源）、配置和生成结果（英文全部能用 Windows-1252 显示、本地化行格式、条数、缩略图），带 `--game-root` 时再核对原版省份窗口有没有随游戏更新变化。正式构建输出模组文件夹、ZIP（顶层附 `province_descriptions.mod`，玩家整个解压进 mod 目录即可）和 `build_receipt.json`；输出目录必须是新的。

## 发布

1. **更新数据**：研究工程质量流程跑完后，在 MacBook 上 `tools/sync_workshop.sh` 导出最新正文并装进游戏，进游戏抽看几省（中英文各看、开关 Bigger UI 各看）。
2. **准备版本**：`python -B tools\release.py 1.0.0 --note "First public release." --install --commit`。它升版本号、写 `CHANGELOG.md`、跑测试和检查、构建到 `dist\release-1.0.0\`、核对、装进游戏并提交。失败会把版本号和 CHANGELOG 改回去。`--dry-run` 只检查和构建。
3. **第一次上传（作者做）**：工坊条目要由作者建：EU4 启动器 → 模组 → 上传模组，选本机的 `Descriptions for Every Province`（就是第 2 步装进 mod 目录的那份），可见性先选私密或仅好友，标题和描述照 `workshop/description.*.txt`，封面用 `workshop/assets/cover.jpg`。建好后把条目编号填进 `project.json` 的 `publishedfileid` 并提交；之后的构建会在 `descriptor.mod` 里写 `remote_file_id`。
4. **之后的更新**：先 `release.py <新版本>`，再在登录了 Steam 的桌面会话里 `python -B tools\steam_upload.py <版本> --upload --notes-file workshop\changenotes.en.txt --output dist\upload-<版本>.json`；页面文案和封面用 `tools\steam_page.py`。这两个工具改自 EU5 地块发布工程，只更新已有条目，不建条目、不改可见性、不接受条款。远程触发的办法（计划任务借用桌面会话）见 EU5 地块发布工程 `docs/PUBLISHING.md`。
5. **更新说明**：`workshop/changenotes.*.txt` 第一行写版本号；中文更新说明要在网页上补（EU5 地块的经验：接口只提交一种语言）。

**还要作者确认的事**（不影响构建，但发布前要看）：小分辨率或界面放大时按钮会不会盖住关闭按钮（见研究工程 `tasks/todo.md`「小屏布局」）；工坊页面写了"逐条审阅订正过"，要等研究工程的审查修复流程跑完再发。

## 文件

| 路径 | 内容 |
|---|---|
| `project.json` | 模组名（中英）、目录名、版本、游戏和工坊编号、`steam_api64.dll` 路径、标签、许可、中文模组显示名、按钮位置、原版底稿和它的哈希 |
| `data/entries.jsonl` | 研究工程导出的词条，一行一个省份：`id`、`status`、`en`、`zh`、`sources` |
| `assets/vanilla/provinceview.gui` | 原版省份窗口（游戏 v1.37.5.0），构建时在它上面加按钮；游戏更新后用 `--check --game-root` 核对 |
| `assets/eu4lg_button.dds` | 省份窗口里的卷轴按钮，`tools/draw_icon.py` 生成（`uv run --with pillow tools/draw_icon.py <游戏目录>/gfx/interface/button_history.dds assets/eu4lg_button`） |
| `tools/build.py` | 检查、构建、核对、装进游戏，只用标准库 |
| `tools/release.py` | 准备一个版本（升版本、CHANGELOG、全部检查、构建），两个发布工程相同 |
| `tools/steam_upload.py`、`tools/steam_page.py` | 更新已有工坊条目的内容和页面 |
| `tools/eu4zh.py` | 中文模组（工坊 2976470733）的文字编码，和研究工程里的同名文件一致，改一处要同步另一处 |
| `tools/cover.py` | 封面：`reference` 从游戏地图画不列颠群岛的四色参考图，`derive` 从生图母版导出封面和缩略图 |
| `workshop/` | 工坊页面中英文案（`description.*.txt`，BBCode）、更新说明、模组里附带的玩家说明 `player-readme.*.md`、`page.json` |
| `workshop/assets/` | 封面母版 `cover-master.*.png`（Codex 生图模型按 `map-reference.png` 和 EU5 地块封面画成，提示词在 `cover-prompt.*.txt`）、导出的 `cover.jpg`、`cover.zh-CN.jpg`、`thumbnail.png` |
| `LICENSE`、`LICENSES/`、`CREDITS.md` | 工具 MIT、正文 CC BY-SA 4.0（照 EU5 地块模组的选择），署名和第三方说明；都会打进模组 |
| `CHANGELOG.md` | 版本记录，由 `release.py` 写 |

## 技术要点

- **不和界面模组抢文件**（2026-11-03 起）：`provinceview.gui` 整份覆盖、谁后加载用谁的，直接改它会和 Bigger UI（工坊 788906833）这类界面模组互相顶掉。所以不覆盖它，而是把原版省份窗口定义加上按钮写进 `interface/00_eu4lg_provinceview.gui`（`project.json` 的 `gui_file`）。游戏遇到同名窗口用先读到的定义，`00_` 排在前面；2026-11-03 探测版（`00_`、`zz_` 两份，按钮位置不同）在游戏里证实生效的是 `00_`。不写依赖，也不需要兼容补丁。代价：装了 Bigger UI 时它给省份窗口加的 20 个快捷键不生效（两边布局相同，只差这些快捷键、一个列表高度和一处编码）。兼容补丁的生成代码 2026-11-03 删掉了（用不上），要时从 Git 历史 `b1786e3` 找回。
- **字符**：EU4 英文只能显示 Windows-1252。游戏日志对 ō、ı、ā、ł 等报 "Couldn't find Latin1 character"（0.11 时 321 条英文正文、2,702 处），对 š、ž、弯引号、长破折号不报。`build.py` 的 `fold_latin1` 在生成时换成最接近的字母（ō→o、ł→l、ʻ→'），希腊文、汉字去掉；中文正文里夹的西文字母只能留 Latin-1（中文模组把码位大于 255 的都当汉字编码），由 `fold_latin_in_zh` 处理（2026-11-03 起中文里的扩展区生僻字也去掉，规则和研究工程 `entries.py` 的检查一致）。会让句子断开的情况由研究工程的检查报错、回那边改正文。
- **按钮不写 trigger**：`custom_button` 里写 `trigger = { always = yes }`，提示框底部会多出一行"✓ 总是"。
- 中英文都写进 `l_english`；用 `is_mod_active` 检测中文模组，启用时显示中文（2026-11-03 在游戏里证实可用：检测行显示 YES，故意写错名字的对照为 NO）。`zh_mods` 只写了实测过编码一致的 Chinese Language Mod for 1.37；中文模组随游戏版本改名（for 1.38）时要跟着加。
- 每个省份一条 `province_id = N` 的 `defined_text` 分支，只在悬停按钮时判断。
- 加了 `common/custom_gui`，会改变校验码，铁人模式拿不到成就；不改校验码的路线 0.1 已证实走不通。
