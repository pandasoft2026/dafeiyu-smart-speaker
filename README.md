# 大肥鱼 · 把智能音箱改造成本地 ASR + AI 对话助手

把一台闲置的安卓智能音箱（京鱼座 i8 Pro / SD-DP02，MT8167S，Android 8.1，1GB RAM）
改造成带唤醒词、本地离线语音识别、DeepSeek 问答和本地 TTS 的语音助手。

整个项目跑在音箱上。**不需要一直开着电脑。**

## 它能做什么

- 唤醒词「肥鱼肥鱼」，灭屏状态下也能唤醒并点亮屏幕
- 触摸按钮唤醒；10 分钟无操作自动息屏，唤醒服务继续运行
- 本地离线 ASR（Vosk），识别不上云
- 全程设备端 TTS，用微软 Edge 朗读服务的流式协议，电脑不参与
- 两套人设：大肥鱼（甜美女声）／梁圣（年轻霸总男声），语音指令可切换
- 自绘音量条，音量固定 20%；看门狗崩溃自愈、断电重启自恢复

## 架构

```
麦克风 → tinycap (4 通道) → Vosk 本地识别 → 意图分流
                                              ├─ 人设切换 → 本地 TTS 播报
                                              └─ DeepSeek API → 设备端 TTS → 播放
```

设备端三个常驻进程：

| 进程 | 作用 |
|---|---|
| `service.py` | 主服务，HTTP `127.0.0.1:8899`，含 ASR / 唤醒 / TTS / API |
| `voicebot_watchdog.sh` | 每 30 秒检查进程和端口，异常自动拉起 |
| `dafeiyu_boot.sh` | 开机自启：音量、息屏策略、ADB 端口、启动服务 |

前端是 WebView 加载的单页 `apk/assets/index.html`，通过 HTTP 和本地服务通信。

## 目录

```
asr/
  service.py           主服务（ASR / 唤醒 / TTS / API）
  edge_tts_lite.py     纯标准库实现的 Edge TTS WebSocket 客户端
  sec_ms_gec.py        微软 Sec-MS-GEC 请求签名
  ctl.py               命令行调试工具
  py.sh                Termux Python 启动器
  *.py                 各类诊断/自测脚本
apk/
  src/.../MainActivity.java   桌面应用
  assets/index.html           界面与交互逻辑
boot/
  dafeiyu_boot.sh      开机自启
  voicebot_watchdog.sh 看门狗
  voicebot_guard.sh    ADB 端口持久化
  perf.sh              性能模式
tools/                 部署与诊断脚本
docs/自测报告.md        完整的实测记录
```

## 部署

### 前置条件

- 一台已 root、装了 Termux 的安卓 8.1 音箱（armv7 / arm64 均可）
- `adb connect <音箱IP>:5555` 能连上
- 一个 DeepSeek API key

### 依赖（本仓库不含，需自行下载）

| 依赖 | 说明 |
|---|---|
| Vosk 中文小模型 | `vosk-model-small-cn`，放到设备的 `model/` |
| `libvosk_android.so` | 对应架构的 Vosk 原生库 |
| Termux Python 3 | 设备端解释器 |
| Android SDK 8.1 | 仅重新编译桌面 APK 时需要 |

第三方二进制不随本仓库分发，避免许可证冲突和仓库体积爆炸。

### 配置

1. 在所有脚本里把 `SPEAKER_IP` 环境变量设成你的音箱 IP。
   `ah.sh` / `cdp.sh` 等默认值为示例地址 `192.168.1.50`，直接用会连不上。
2. 在设备上创建 `/data/local/tmp/voicebot/api_key.conf`，内容只有一行 DeepSeek key。
   **这个文件绝不要提交到 git**（已在 `.gitignore` 中）。
3. 按 `tools/` 下各脚本的注释把服务和开机脚本推到设备对应目录。

### 常用调试

```sh
./ah.sh shell "su -c 'tail -f /data/local/tmp/voicebot/svc.log'"   # 看服务日志
sh py.sh ctl.py health                                            # 健康检查
sh py.sh ctl.py mode fish                                         # 切人设
```

## TTS 的实现说明

微软 Edge 朗读服务是 WebSocket 协议，官方 `edge-tts` 依赖 aiohttp，
在这台 armv7 的 Python 3.14 上装不了。所以 `edge_tts_lite.py` 用标准库
手写了 TLS + WebSocket 客户端，直接从服务收 mp3。

关键实现点：

- `Sec-MS-GEC` 签名算法见 `asr/sec_ms_gec.py`。微软在标准 SHA-256 上改了
  初始状态、轮常量和消息扩展，还混了自定义摘要，不能直接用标准库算。
- 建连时对多个 IP 并发竞速：某些网络下 Bing 的两个 A 记录有一个不通，
  顺序尝试会吃满超时（实测 20 秒）。
- 合成结果缓存在 `/dev`（tmpfs），同一句话第二次约 10ms。
- DeepSeek 流式输出，第一句生成完就推给前端开播（实测首句 660ms）
- 前端按句切分、用单一队列顺序播放，新句子只入队不打断当前播放
- TTS WebSocket 连接复用池：同一条连接连续合成多句，后续句省掉握手
- 固定话术开机预合成，问候语命中缓存零等待

## 许可

MIT，见 [LICENSE](LICENSE)。

注意：本项目不包含任何第三方二进制、固件镜像或模型文件，
这些资源的许可证由各自所有者规定。
