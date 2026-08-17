# Virtual Partner

一个面向 macOS 的本地 AI 虚拟伙伴。目前提供环境检查和终端文本聊天原型。

## 当前能力

- 检查 Python、macOS 和处理器架构。
- 在终端中进行多轮文本聊天。
- 使用内置的 atosaac v0.25 角色配置。
- 从外部 Markdown 文件加载其他角色。
- 通过可替换的 `ReplyProvider` 接入未来的本地或云端模型。

当前默认回复仍是本地 mock（模拟实现），不会访问网络，也不会调用真实 LLM。
LLM（大语言模型）负责根据角色说明和对话上下文生成自然语言回复。

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

启动后直接输入文字并按回车。输入 `exit`、`quit` 或 `退出` 可以结束聊天，
按 `Ctrl+C` 或发送文件结束符也会安全退出。

```text
Virtual Partner: 你好！输入“退出”可以结束聊天。
You: 你好
Virtual Partner: 我听到了：你好
You: 退出
Virtual Partner: 下次见。
```

查看全部命令或聊天参数：

```bash
uv run atosaac-virtual-partner --help
uv run atosaac-virtual-partner chat --help
```

## 加载其他角色

默认聊天会加载内置的 atosaac v0.25 角色配置。也可以临时加载其他 Markdown
角色文件：

```bash
uv run atosaac-virtual-partner chat \
  --character-file "/absolute/path/to/character.md"
```

推荐在文件开头使用带版本的一级标题：

```markdown
# Nova v1.0

你是 Nova。保持好奇、独立，并清楚地区分猜测和事实。
```

外部角色文件只在本次聊天中读取，不会被自动复制或修改。不要在角色文件中保存
API 密钥、私人聊天记录或其他敏感信息。

当前 mock 只用于验证聊天流程，因此不会真正表现角色性格；角色说明已经进入会话
上下文，接入真实回复提供者后才会影响生成结果。

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
- 尚未连接真实 LLM，因此还不能评估角色表现。
- 尚未实现 ASR、TTS、长期记忆、多模态和 Live2D。

ASR（自动语音识别）把语音转换成文字；TTS（文本转语音）把角色回复合成为声音。
下一阶段将先接入可配置的真实回复提供者，再增加流式输出和取消机制，为语音打断
打好基础。
