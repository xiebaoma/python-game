# 校园网络防线（Campus Cyber Guard）

一个使用 Python 与 Pygame 开发的轻量塔防游戏。玩家需要在校园网络拓扑图上部署扫描节点、防火墙和隔离沙箱，阻止异常数据包、僵尸进程、蠕虫病毒与勒索核心抵达服务器。

## 项目亮点

- 8 个递进波次、4 类敌人和基于路径进度的目标优先级。
- 3 类差异化防御节点：高速单体、范围伤害、减速控制。
- 完整的资源循环：部署、升级、出售、击杀奖励和波次奖励。
- 全网应急扫描技能、能量恢复、连击倍率与最高分存档。
- 菜单、帮助、暂停、胜负结算和自动演示模式。
- 代码绘制全部游戏画面，不依赖外部图片素材。

## 运行环境

- Python 3.9 或更高版本
- pygame-ce 2.5.6
- imageio / imageio-ffmpeg（仅录制演示视频时需要）

依赖下载地址：

- pygame-ce：https://pyga.me/ 或 https://pypi.org/project/pygame-ce/
- imageio：https://imageio.readthedocs.io/
- Python：https://www.python.org/downloads/

## 快速开始

macOS 双击 `run_game.command`。也可以在终端运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

首次运行会自动创建虚拟环境并安装依赖，因此需要网络。之后可离线启动。

## 操作说明

| 操作 | 功能 |
|---|---|
| 鼠标左键 | 选择节点、部署节点 |
| 数字键 1 / 2 / 3 | 选择扫描节点 / 防火墙 / 隔离沙箱 |
| U / X | 升级 / 出售当前选中的节点 |
| Space | 启动下一波入侵 |
| E | 消耗 60 能量发动全网应急扫描 |
| P / H / Esc | 暂停 / 帮助 / 取消或返回 |

建议先在路线前半段部署扫描节点，再在多段路线相邻的位置部署防火墙，最后使用隔离沙箱延长火力输出时间。

## 项目结构

```text
.
├── main.py                     # 命令行入口与演示录制入口
├── cyber_guard/
│   ├── config.py               # 数值、配色、路线和波次配置
│   ├── entities.py             # 敌人、塔、子弹和粒子实体
│   ├── game.py                 # 状态机、输入、规则、绘制和存档
│   └── ui.py                   # 字体、按钮、面板等 UI 组件
├── tests/test_game_logic.py    # 8 项逻辑回归测试
├── assets/screenshots/         # 自动生成的运行截图
├── requirements.txt
├── run_game.command            # macOS 一键启动脚本
├── 项目文档-校园网络防线.docx
├── 汇报PPT-校园网络防线.pptx
└── 演示视频-校园网络防线.mp4
```

## 自动演示与测试

```bash
# 自动演示
python main.py --demo

# 录制 52 秒 MP4，并保存关键帧
python main.py --record-demo demo.mp4 --duration 52 --fps 15 --screenshot-dir assets/screenshots

# 运行逻辑测试
python -m unittest discover -s tests -v
```

## 设计说明

主循环采用“输入处理 → 状态更新 → 画面绘制”的经典游戏循环。`Enemy` 沿折线路径分段移动，`Tower` 每帧根据攻击范围筛选目标，并优先锁定路径进度最高的敌人。配置数据与行为逻辑分离，方便调平衡；实体使用类封装，界面组件复用，文件职责清晰。

作者：谢宝玛（学号 1120233506）  
课程：软件工程基础训练
# python-game
