# 所有省份的描述（Descriptions for Every Province）：发布工程

这里把研究工程写好的省份介绍构建成 EU4 模组，装进本机游戏做实验，也从这里发布到创意工坊。模组目录名 `province_descriptions`，工坊条目 [3833082096](https://steamcommunity.com/sharedfiles/filedetails/?id=3833082096)，2026-11-04 由作者在 EU4 启动器建好（私密），中英文标题、描述和封面随后用 `tools/steam_page.py` 补齐；以后的更新不再开启动器，按下面「发布」第 4 步走。在桌面会话里跑 Steam 工具时用 `wscript` 包一层隐藏窗口（`Run ..., 0, True`），否则 Windows 终端会弹窗挡住游戏。正文、来源和写作规则都在研究工程，这里不改正文。

## 三处位置

| | 位置 | 管什么 |
|---|---|---|
| 研究工程 | Mac mini `~/personal/paradox-mods/eu4-provinces/research`（主副本，GitHub 私有库 `wangyufeng0615/eu4-province-gazetteer-research`）；MacBook 克隆在同一路径 | 3,272 个陆地省份的词条、资料、写作规则、批量写作调度器 |
| 发布工程 | 本目录，Windows `V:\paradox-mods\eu4-provinces\workshop`（本地 Git；公开库 GitHub `wangyufeng0615/eu4-province-descriptions`，Windows 连不上 GitHub，经 MacBook 推送） | 构建、装进游戏、以后的工坊文案和发布 |
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
python -B tools\build.py --install            :: 构建到 dist\dev，以「Descriptions for Every Province (dev)」装进 文档\Paradox Interactive\Europa Universalis IV\mod\province_descriptions_dev
python -B tools\build.py --install --debug    :: 提示框底部多一行中文模组检测结果
```

装好后要完全退出再重开 EU4 才会读到新文件。同步脚本会把新数据提交到本目录的 Git，方便回退。2026-11-04 起本机开发安装（`build.py --install`、`release.py --install`）一律装成开发副本：名字带 " (dev)"、目录 `province_descriptions_dev`、不带工坊编号；测试期的 `eu4_gazetteer_test` 和旧的同名本地副本 `province_descriptions` 已删除。播放集里开发副本和订阅版只启用一个。

**本地副本和订阅版不能同名共存**（2026-11-04 实测）：`mod` 目录里同时有本地 `province_descriptions.mod` 和订阅版 `ugc_3833082096.mod`、两者 `name` 都是 "Descriptions for Every Province" 时，播放集里只启用订阅版，游戏也一个文件都不加载（日志里省份窗口仍是原版定义，按钮不出现）；把本地登记文件挪出 `mod` 目录后订阅版立即正常。所以开发安装改成了带 " (dev)" 的名字（`build.py` 的 `dev_config`），不再生成同名副本。1.0.0 的 `descriptor.mod` 还缺 `remote_file_id`（建条目前打的包），1.0.1 补上了，但那不是按钮消失的原因。

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
5. **更新说明（agent 全程自动处理，作者不操作，2026-11-04 作者要求）**：`workshop/changenotes.*.txt` 第一行写版本号，同步改 `description.*.txt` 末尾的更新记录并用 `steam_page.py --descriptions` 提交。英文说明随 `steam_upload.py --notes-file` 提交；中文说明接口补不了，用 Claude in Chrome（作者的 Chrome 已登录 Steam）打开 `https://steamcommunity.com/sharedfiles/filedetails/changelog/3833082096`，点最新一条的「编辑」，语言选「简体中文」（地址带 `?language=6`）填 `changenotes.zh-CN.txt` 并保存，再用 `?l=schinese` 和 `?l=english` 分别核对。网页上没有删除，只能编辑；1.0.0 和 1.0.1 已合并为一条"1.0.1 首次公开发布"，另两条空记录（启动器上传、早期页面更新）留着。
6. **推到 GitHub**（2026-11-04 起公开）：Windows 连不上 GitHub，在 MacBook 上运行研究工程 `tools/push_public.sh`（把 Windows 的 main 打成 bundle、经本机快进推到 GitHub，再对齐 Windows 的 `origin/main`）；发版时加 `--tag <版本>`，推送 `v<版本>` 标签后 `.github/workflows/release.yml` 从该提交构建、核对，并把 ZIP 附到 GitHub Release（说明由 `tools/release_notes.py` 从 CHANGELOG 生成）。推送后核对 Release 里 ZIP 的文件哈希和本地构建回执一致。1.2.0 的 Release 是手动挂的工坊同款 ZIP（标签在 c13a0b6）。
7. **画廊**：`page.json` 的 `gallery` 列出要放进画廊的图（每张小于 1 MB），`steam_page.py --assets` 按文件名更新或新增。现有：中文封面、英文效果图 `gallery-en.jpg`（君士坦丁堡）、中文效果图 `gallery-zh-CN.jpg`（北京）。
8. **徽章**：描述标题下的 `[img]` 是 `workshop/assets/badges/` 的两张徽章（`render.py` 照搬 EU5 地块，英文"coverage 100% / Bigger UI compatible"，中文"覆盖率 100% / 支持语言 英文 + 简中"），用 `steam_page.py --host-badges` 存进 Steam 云并共享，直链记在 `page.json` 的 `description_badges`；不占画廊，云文件不要删。改了徽章要重新渲染、托管，再把描述里的直链换掉。

**还要作者确认的事**（不影响构建，但发布前要看）：小分辨率或界面放大时按钮会不会盖住关闭按钮（见研究工程 `tasks/todo.md`「小屏布局」）；工坊描述 2026-11-04 起用作者自己写的版本（中文为作者原稿，英文照它对应；资料来源一句是作者的原话"反复订正"），改文案时保留作者的写法和语气。全部 3,272 条已按新文风重写（亚洲、欧洲 1.1.0，其余 1.2.0），尚未按新标准重新审核。

## 文件

| 路径 | 内容 |
|---|---|
| `project.json` | 模组名（中英）、目录名、版本、游戏和工坊编号、`steam_api64.dll` 路径、标签、许可、中文模组显示名、按钮位置、原版底稿和它的哈希 |
| `data/entries.jsonl` | 研究工程导出的词条，一行一个省份：`id`、`status`、`en`、`zh`、`sources` |
| `data/wonders.jsonl` | 研究工程导出的奇观介绍，一行一座：`key`、`province`、`name_en`、`name_zh`、`status`、`en`、`zh`、`sources` |
| `assets/vanilla/provinceview.gui` | 原版省份窗口（游戏 v1.37.5.0），构建时在它上面加按钮；游戏更新后用 `--check --game-root` 核对 |
| `assets/eu4lg_button.dds` | 省份窗口里的卷轴按钮，`tools/draw_icon.py` 生成（`uv run --with pillow tools/draw_icon.py <游戏目录>/gfx/interface/button_history.dds assets/eu4lg_button`） |
| `tools/build.py` | 检查、构建、核对、装进游戏，只用标准库 |
| `tools/release.py` | 准备一个版本（升版本、CHANGELOG、全部检查、构建），两个发布工程相同 |
| `tools/steam_upload.py`、`tools/steam_page.py` | 更新已有工坊条目的内容和页面 |
| `tools/eu4zh.py` | 中文模组（工坊 2976470733）的文字编码，和研究工程里的同名文件一致，改一处要同步另一处 |
| `tools/cover.py` | 封面：`world` 从游戏地图画全世界四色省份图（纵向拉伸填满标题下方），拼成中英文母版；`derive` 导出封面和缩略图；`reference` 是 0.15.0 前不列颠群岛封面的参考图 |
| `workshop/` | 工坊页面中英文案（`description.*.txt`，BBCode）、更新说明、模组里附带的玩家说明 `player-readme.*.md`、`page.json` |
| `workshop/assets/` | 封面母版 `cover-master.*.png`（2026-11-04 起由 `cover.py world` 生成：世界地图 ＋ 固定素材 `title.*.png`、`languages.png`；这些素材裁自旧的生图母版，Codex 生图模型按不列颠参考图和 EU5 地块封面画成，提示词在 `cover-prompt.*.txt`）、导出的 `cover.jpg`、`cover.zh-CN.jpg`、`thumbnail.png` |
| `LICENSE`、`LICENSES/`、`CREDITS.md` | 工具 MIT、正文 CC BY-SA 4.0（照 EU5 地块模组的选择），署名和第三方说明；都会打进模组 |
| `CHANGELOG.md` | 版本记录，由 `release.py` 写 |
| `README.md`、`.github/workflows/` | GitHub 公开页的中英文说明；推送时检查构建（`check.yml`），推 `vX.Y.Z` 标签时发布 Release（`release.yml`） |
| `tools/release_notes.py` | GitHub Release 说明：CHANGELOG 条目 ＋ 安装步骤 ＋ ZIP 的 SHA-256 |

## 技术要点

- **不和界面模组抢文件**（2026-11-03 起）：`provinceview.gui` 整份覆盖、谁后加载用谁的，直接改它会和 Bigger UI（工坊 788906833）这类界面模组互相顶掉。所以不覆盖它，而是把原版省份窗口定义加上按钮写进 `interface/00_eu4lg_provinceview.gui`（`project.json` 的 `gui_file`）。游戏遇到同名窗口用先读到的定义，`00_` 排在前面；2026-11-03 探测版（`00_`、`zz_` 两份，按钮位置不同）在游戏里证实生效的是 `00_`。不写依赖，也不需要兼容补丁。代价：装了 Bigger UI 时它给省份窗口加的 20 个快捷键不生效（两边布局相同，只差这些快捷键、一个列表高度和一处编码）。兼容补丁的生成代码 2026-11-03 删掉了（用不上），要时从 Git 历史 `b1786e3` 找回。
- **字符**：EU4 英文只能显示 Windows-1252。游戏日志对 ō、ı、ā、ł 等报 "Couldn't find Latin1 character"（0.11 时 321 条英文正文、2,702 处），对 š、ž、弯引号、长破折号不报。`build.py` 的 `fold_latin1` 在生成时换成最接近的字母（ō→o、ł→l、ʻ→'），希腊文、汉字去掉；中文正文里夹的西文字母只能留 Latin-1（中文模组把码位大于 255 的都当汉字编码），由 `fold_latin_in_zh` 处理（2026-11-03 起中文里的扩展区生僻字也去掉，规则和研究工程 `entries.py` 的检查一致）。会让句子断开的情况由研究工程的检查报错、回那边改正文。
- **奇观**（2026-11-04 加，待进游戏确认）：研究工程导出 `data/wonders.jsonl`（139 座）。`build.py` 在奇观面板（`great_projects_window`）标题栏右端加小号卷轴按钮 `eu4lg_wonder_button`（28×28，`assets/eu4lg_button_small.dds` 由 `eu4lg_button.dds` 缩出；默认 264, 30，`project.json` 可用 `wonder_button_pos` 改），写在列表之后才画在上层。悬停显示这个省份全部奇观的介绍，一省两座时各带标题，按 `province_id` 分支。标题栏不随列表滚动，一座、两座都适用。做不到每座奇观各一个随列表滚动的按钮：行模板（`great_project_entry`）不在 `buildings_window` 之下，游戏不绑定脚本按钮（2026-11-04 实测没有提示框）；脚本也没有奇观作用域。没有 `data/wonders.jsonl` 时不加按钮。`--debug` 版提示框底部显示 `scope: [Root.GetName]`。
- **按钮不写 trigger**：`custom_button` 里写 `trigger = { always = yes }`，提示框底部会多出一行"✓ 总是"。
- 中英文都写进 `l_english`；用 `is_mod_active` 检测中文模组，启用时显示中文（2026-11-03 在游戏里证实可用：检测行显示 YES，故意写错名字的对照为 NO）。`zh_mods` 只写了实测过编码一致的 Chinese Language Mod for 1.37；中文模组随游戏版本改名（for 1.38）时要跟着加。
- 每个省份一条 `province_id = N` 的 `defined_text` 分支，只在悬停按钮时判断。
- **成就**：游戏校验和只算 `checksum_manifest.txt` 列出的目录里的 `.txt`、`.lua`（localisation、customizable_localization、interface、gfx 都不算），本模组在范围内的只有 `common/custom_gui` 的按钮定义。这个文件写成大写扩展名 `common/custom_gui/eu4lg.TXT`：游戏照样读，校验和和原版一致（2026-11-04 Windows 上用探针模组实测：主菜单校验和不变，提示框正常；同时试的 `.Txt`、`.yml`、无扩展名、`.txt_` 游戏都不读，对应按钮被隐藏）。不要改回小写。Mac 文件系统默认不分大小写，应该能读，没测过；Linux 区分大小写，可能读不到（按钮会被隐藏），没测过。待确认：开发版铁人新局成就图标可用；确认后把 README 和 `workshop/player-readme.*` 里"不兼容成就"改成"Windows 已验证兼容成就"，随 1.3.0 发布。
