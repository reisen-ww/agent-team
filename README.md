# Agent Team

一个自包含的 Codex Skill：从 PM 与技术经理对齐，到小组/多部门协作，再到证据验收和异常恢复。版本 0.6.0，AGPL-3.0-or-later。

将此 agent-team 文件夹放入当前 Codex 环境实际使用的 skills 目录，然后调用 `$agent-team`。无需另装 PM Skill，不依赖特定模型提供商、私人路由或固定工作目录。安装位置和实际工具以你的宿主配置为准。

可以用它对齐新需求、组织长任务、恢复已有工作，或只讨论/修改团队规则。明确的小任务直接处理；调用 Skill 不自动创建团队、额外付费请求、自动化或公开发布。

SKILL.md 是单一入口，references/ 按阶段载入。人类决定目标与授权；AI 角色可合并。Astra/Sol/Terra/DS 仅是可选角色映射，可替换为你批准的可用模型。默认员工自查、主管审查与约定验证；需要独立复核时按任务安排。

支持完整四层、部门主管→组负责人→执行者、组负责人→执行者及单会话。最上层现有成员承接用户对齐和整体交付责任。从下往上的综合判断与协调能力要求提高，日常调用减少；具体模型按任务验证，价格不等于智力。

这是一套协作协议，不是已经实现的 agent 调度服务器或安全沙箱。实际权限、并发控制、计费上限和后台触发需要宿主支持。完整流程不会保证覆盖所有未知环境；未覆盖情况按明确的权限/影响/负责人规则处理。

如需报告问题，请给出可复现的请求、预期与实际行为、Skill 版本及已脱敏的必要证据，勿提交密钥、私人聊天或账号资料。

## 从一个小团队开始

先读 [一个主管与两个执行者的完整样例](examples/small-team/README.md)。它提供输入、工作包、验收脚本、需求变更、重复消息与暂停恢复步骤；所有预置运行记录均为虚构演练，不是模型实测。无需模型即可从本目录运行：

```sh
python -B scripts/check_run.py examples/small-team/records/01-accepted-r1.json
python -B scripts/check_run.py examples/small-team/records/02-impact-pending.json
python -B scripts/check_run.py examples/small-team/records/03-accepted-r2.json
python -B -m unittest discover -s tests -v
```

要求 Python 3.10+，仅使用标准库。检查器只读记录、不执行消息或工具；通过仅表示已检查字段内部一致，不证明真正执行、正确授权、费用准确或操作系统隔离。已有任务系统无需迁移；[记录格式](references/run-record.md) 是可选适配。

## 版本与迁移

0.6.0 增加 [方向与产出](references/direction.md)：区分 PM 目标、技术方法与假设；分层检查任务拆分；用实际成果/新证据定义阶段；辅助工作有退出条件，重复无进展时收敛。包括 [通用行为验证](examples/direction-check/README.md)，覆盖编码、研究与审查。规则和测试不保证任意长任务始终正确，也不自动运行真实团队。

新旧团队或版本交接见 [记录与通信](references/coordination.md)。在首次工作包中给出有效规则及原需求入口，核实旧执行状态与资源归属后再接管；不能把更新 Skill 当成已经部署到所有会话。

0.5.0 补充动作去重、需求变化导致的验收复核、循环等待裁决、轻量度量及可复现演练。运行开始记录 Skill 版本/源码提交或包指纹；在途成员不会因文件更新自动加载新规则。升级在明确交接点核对，保留原记录，不自行重派或解除暂停。

早期 0.4.0 存在 MIT 分发包与后续 AGPL 仓库快照；引用历史时同时记录来源和指纹，不只写版本号。各版本单独分发，不覆盖旧 ZIP 或把旧证据改写为新版本通过。

## 许可证

Copyright (C) 2026 agent-team contributors。许可证为 [GNU Affero General Public License v3.0 或更新版本](LICENSE)（SPDX: AGPL-3.0-or-later），与此前声明中的“or any later version”保持一致。LICENSE 附完整官方正文。

允许商业使用；复制、修改和分发应遵守许可证条件。修改后的受覆盖程序若支持用户通过网络与其交互，须按第 13 节向这些用户提供获取对应源码的机会。具体义务以正文为准，不概括成一切“闭源商用都禁止”。

本许可覆盖本仓库内容；使用 Skill 产生的独立项目并不因调用本 Skill 就被本 README 宣告适用 AGPL。若向项目复制受许可内容，或形成受覆盖的修改/组合，应另行判断适用条款。参见 GNU [AGPL 常见问题](https://www.gnu.org/licenses/gpl-faq.html#UnreleasedModsAGPL) 与许可证第 2、13 节。
