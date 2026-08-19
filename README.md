# Virtual Partner

一个面向 macOS 的本地 AI 虚拟伙伴。目前提供环境检查和终端文本聊天原型。

## 当前能力

- 检查 Python、macOS 和处理器架构。
- 在终端中进行多轮文本聊天。
- 使用内置的 atosaac v0.27 角色配置。
- 从外部 Markdown 文件加载其他角色。
- 通过可替换的 `ReplyProvider` 使用 mock 或本地 Ollama 模型。

默认回复仍是本地 mock（模拟实现），不会访问网络。选择 Ollama 后，LLM
（大语言模型）会根据角色说明和对话上下文生成自然语言回复。

## 环境要求

- macOS
- Python 3.11
- [uv](https://docs.astral.sh/uv/) 环境和依赖管理工具

在仓库根目录安装开发依赖：

```bash
uv sync
```

`uv sync` 会根据 `pyproject.toml` 和 `uv.lock` 创建或更新项目的 `.venv`
虚拟环境，不需要手动运行 `pip install`。

## 开始调用

先检查本地环境：

```bash
uv run atosaac-virtual-partner health
```

正常情况下会输出类似信息：

```text
Virtual Partner
Python: 3.11.x
macOS: ...
Architecture: arm64
Status: ready
```

启动默认文本聊天：

```bash
uv run atosaac-virtual-partner chat
```

启动后直接输入文字并按回车。输入 `exit`、`quit` 或 `退出` 可以结束聊天。
在 macOS 终端等待输入时，按 `Control+C`（也常写作 `Ctrl+C`，不是
`Command+C`）或发送文件结束符会安全退出；模型正在生成时按 `Control+C`
只取消当前回复，然后可以继续聊天。

```text
atosaac: 你好！输入“退出”可以结束聊天。
You: 你好
atosaac: 我听到了：你好
You: 退出
atosaac: 下次见。
```

查看全部命令或聊天参数：

```bash
uv run atosaac-virtual-partner --help
uv run atosaac-virtual-partner chat --help
```

## 调用本地 LLM

项目通过 Ollama 的本地 Chat API 调用真实模型，不需要 API 密钥。macOS
推荐从 [Ollama 官方网站](https://ollama.com/download)安装 App，也可以使用无
formula 依赖的 Homebrew cask：

```bash
brew install --cask ollama-app
```

启动 Ollama App，或在一个单独的终端中保持服务运行：

```bash
ollama serve
```

然后在另一个终端中下载首个测试模型：

```bash
ollama pull qwen3:4b-instruct
```

`qwen3:4b-instruct` 下载体积约 2.5GB。请使用带 `-instruct` 的明确
标签；`qwen3:4b` 当前指向 thinking（思考）变体，可能把长推理过程一起输出，
不适合当前的低延迟角色聊天。Ollama 会把模型保存在自己的数据目录中，不会写入
本仓库。确认本地服务和模型可用：

```bash
ollama list
curl http://localhost:11434/api/tags
```

使用 Ollama 和默认 atosaac v0.27 性格开始聊天：

```bash
uv run atosaac-virtual-partner chat \
  --provider ollama \
  --model qwen3:4b-instruct
```

实验性主动对话默认关闭。需要测试“沉默后由 atosaac 主动开口”时，可以设置空闲
秒数，例如 60 秒：

```bash
uv run atosaac-virtual-partner chat \
  --provider ollama \
  --model qwen3:4b-instruct \
  --idle-initiative-seconds 60
```

达到空闲时间后最多主动回复一次；在用户再次输入前不会连续催促。用户输入后重新
开始计时。主动回复和触发它的应用事件会留在当前会话历史中，因此后续回答可以承接
她刚才提出的问题。该功能目前只影响文本，不会自动启用 TTS。

需要观察性能时，可以临时显示不含聊天正文的指标：

```bash
uv run atosaac-virtual-partner chat \
  --provider ollama \
  --model qwen3:4b-instruct \
  --show-metrics
```

每次完整回复后会显示类似：

```text
[指标] 首字 0.42s | 总耗时 1.50s | 输入 100 tokens | 输出 20 tokens | 生成 40.0 tokens/s
```

指标默认关闭，只保存在当前进程内；不会记录用户输入、模型回复或角色提示词。

如果 Ollama 运行在其他地址，可以显式指定服务根地址或 `/api` 地址：

```bash
uv run atosaac-virtual-partner chat \
  --provider ollama \
  --model qwen3:4b-instruct \
  --ollama-url http://127.0.0.1:11434
```

回复会随着 Ollama 生成逐段显示。连接失败、模型不存在、响应格式错误或流意外中断
时，聊天会显示可读错误并继续运行。只有收到完整结束标记后，当前轮次才会写入会话
历史；取消或失败的半截回复不会成为后续上下文。

## 加载其他角色

默认聊天会加载内置的 atosaac v0.27 角色配置。也可以临时加载其他 Markdown
角色文件：

```bash
uv run atosaac-virtual-partner chat \
  --character-file "/absolute/path/to/character.md"
```

推荐在文件开头使用带版本的一级标题：

```markdown
# atosaac v1.0

你是 atosaac。保持好奇、独立，并清楚地区分猜测和事实。
```

外部角色文件只在本次聊天中读取，不会被自动复制或修改。不要在角色文件中保存
API 密钥、私人聊天记录或其他敏感信息。

当前 mock 只用于验证聊天流程，因此不会真正表现角色性格；角色说明已经进入会话
上下文，使用 Ollama 等真实回复提供者后才会影响生成结果。

## 本地 TTS 实验（尚未定型）

TTS（文本转语音）把文字合成为可播放的语音。项目先通过可替换的
`SpeechSynthesizer` 接口接入 macOS 自带语音，验证完整音频链路，不需要下载模型：

```bash
# 直接使用系统中文音色播放
uv run atosaac-virtual-partner speak "你好，这是本地语音测试。"

# 调整音色与语速
uv run atosaac-virtual-partner speak "今天也一起加油吧。" \
  --voice Tingting --rate 210

# 保存为音频文件而不立即播放
uv run atosaac-virtual-partner speak "这是一条测试语音。" \
  --output /private/tmp/virtual-partner-test.aiff
```

使用 `say -v '?'` 可以查看这台 Mac 已安装的系统音色。系统音色只是零依赖回退方案，
不是角色音色克隆。后续会把 MLX-Audio 等本机推理服务放在独立环境中，通过同一接口
替换；原始录音、参考音频、训练数据和模型权重不进入 Git。

这部分明确属于 **TTS 尝试**：目前没有训练模型、没有克隆人物音色、没有接入聊天
自动朗读，也不代表最终语音架构。实验范围和接手说明见
[`docs/TTS_EXPERIMENT.md`](docs/TTS_EXPERIMENT.md)。

仓库边界也已经固定：这里仅保存通用 TTS 接口、服务客户端、系统回退和测试。安洁莉娜
桌宠专用的音色配置、运行接入及未来训练产物归 `angelina-macos-companion` 项目；大型
模型与原始录音只放该项目的本地忽略目录，不提交到 Git。

无论使用内置还是外部角色文件，应用都会额外提供一小段“当前运行事实”。它只声明
本次真正可用的记忆、工具和称呼偏好。当前版本没有持久记忆或天气工具，因此模型不应
声称记得未提供的往事、看过天气预报或擅自使用家长称呼。以后接入能力时由应用更新
事实声明，而不是让角色提示词猜测。

## 开发与测试

运行全部测试：

```bash
uv run pytest
```

显示每个测试名称：

```bash
uv run pytest -v
```

主要代码位于 `src/atosaac_virtual_partner/`，测试位于 `tests/`。项目背景和路线
记录在 `docs/PROJECT_CONTEXT.md`，角色系统设计记录在
`docs/CHARACTER_SYSTEM.md`。

## 当前限制与下一步

- 对话历史目前只保存在当前进程内，退出后不会持久化。
- macOS CLI 支持用 `Control+C` 取消当前流式回复；尚未接入语音或桌面界面的自动打断事件。
- 尚未接入天气等实时数据工具；未来模型只能通过受权限控制的工具接口发起查询。
- 角色 v0.27 已声明当前记忆和工具边界，但提示词不能从数学上保证模型永不犯错；
  合成行为案例会继续用于人工回归和后续自动评估。
- 空闲主动对话必须通过 `--idle-initiative-seconds` 显式启用；当前 CLI 没有安静
  时段、日程感知或桌面通知权限。
- 回复指标当前只在使用 `--show-metrics` 时显示，不会持久化或保存聊天内容。
- 尚未实现 ASR、正式 TTS、长期记忆、多模态和 Live2D；当前 `speak` 仅为 TTS 实验
  基线。

ASR（自动语音识别）把语音转换成文字；TTS（文本转语音）把角色回复合成为声音。
下一阶段将定义会话持久化的保留和删除规则，再决定哪些数据可以进入长期记忆。
